from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    PreTrainedTokenizerFast,
)

from .assertions import attach_assertions
from .candidates import CandidateResolver
from .detector import detect_entities
from .resources import load_lexicon
from .schema import Entity, entities_from_json
from .validator import validate_entities


TEACHER_LABEL_MAP = {
    "ten_benh": "CHẨN_ĐOÁN",
    "trieu_chung_benh": "TRIỆU_CHỨNG",
    "bien_phap_chan_doan": "TÊN_XÉT_NGHIỆM",
}

_GENERIC = {
    "bệnh",
    "bệnh nội khoa",
    "bệnh lý",
    "bệnh lý mãn tính",
    "bệnh lý mạn tính",
    "chẩn đoán",
    "chẩn đoán khác",
    "khám",
    "khám thực thể",
    "kết quả",
    "triệu chứng",
    "triệu chứng hiện tại",
    "xét nghiệm",
}
_NOISY_PHRASE = re.compile(
    r"\b(?:bệnh\s+nhân|người\s+bệnh|được|xuất\s+hiện|cảm\s+thấy|"
    r"cho\s+thấy|ghi\s+nhận|liên\s+quan|khởi\s+phát|kéo\s+dài|"
    r"nhập\s+viện|đánh\s+giá|thực\s+hiện|vị\s+trí)\b",
    re.IGNORECASE,
)
_BAD_ACTION_SPAN = re.compile(
    r"^\s*(?:truyền|điều\s+trị|dẫn\s+lưu|gây\s+dính|nạo\s+vét|"
    r"phẫu\s+thuật|đặt\s+stent|bypass|can\s+thiệp)\b",
    re.IGNORECASE,
)


def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _load_fast_tokenizer(checkpoint: str | Path) -> Any:
    try:
        return AutoTokenizer.from_pretrained(str(checkpoint), use_fast=True)
    except ValueError as exc:
        # BamiBERT's current card was saved by Transformers 5 with the
        # TokenizersBackend marker, while the competition runtime uses
        # Transformers 4.x. The tokenizer.json itself is compatible.
        if "TokenizersBackend" not in str(exc):
            raise
        return PreTrainedTokenizerFast.from_pretrained(
            str(checkpoint),
            tokenizer_file=str(Path(checkpoint) / "tokenizer.json"),
            bos_token="<s>",
            eos_token="</s>",
            cls_token="<s>",
            sep_token="</s>",
            pad_token="<pad>",
            unk_token="<unk>",
            mask_token="<mask>",
        )


def _line_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        end = cursor + len(line.rstrip("\r\n"))
        if text[cursor:end].strip():
            ranges.append((cursor, end))
        cursor += len(line)
    if cursor < len(text) and text[cursor:].strip():
        ranges.append((cursor, len(text)))
    return ranges


def _decode_teacher_line(
    line: str,
    base_offset: int,
    encoded: Any,
    probabilities: torch.Tensor,
    id2label: dict[int, str],
) -> list[Entity]:
    # Average tokens duplicated by sliding-window overlap.
    accumulated: dict[tuple[int, int], list[torch.Tensor]] = {}
    for feature_index in range(probabilities.shape[0]):
        for token_index, (start, end) in enumerate(
            encoded["offset_mapping"][feature_index].tolist()
        ):
            if start == end:
                continue
            accumulated.setdefault((start, end), []).append(
                probabilities[feature_index, token_index]
            )
    tokens: list[tuple[int, int, str, float]] = []
    for (start, end), values in sorted(accumulated.items()):
        mean = torch.stack(values).mean(0)
        label_id = int(mean.argmax())
        tokens.append((start, end, id2label[label_id], float(mean[label_id])))

    output: list[Entity] = []
    current_kind: str | None = None
    current_start = current_end = 0
    current_scores: list[float] = []

    def flush() -> None:
        nonlocal current_kind, current_scores
        if current_kind not in TEACHER_LABEL_MAP:
            current_kind = None
            current_scores = []
            return
        start, end = current_start, current_end
        while start < end and line[start].isspace():
            start += 1
        while end > start and (line[end - 1].isspace() or line[end - 1] in ",;:()"):
            end -= 1
        mention = line[start:end]
        if mention and mention.casefold() not in _GENERIC:
            kind = TEACHER_LABEL_MAP[current_kind]
            output.append(
                Entity(
                    text=mention,
                    type=kind,
                    position=(base_offset + start, base_offset + end),
                    candidates=[] if kind == "CHẨN_ĐOÁN" else None,
                    confidence=sum(current_scores) / max(1, len(current_scores)),
                    source="bami_teacher",
                )
            )
        current_kind = None
        current_scores = []

    for start, end, label, confidence in tokens:
        if label == "O" or "-" not in label:
            flush()
            continue
        prefix, raw_kind = label.split("-", 1)
        if raw_kind not in TEACHER_LABEL_MAP:
            flush()
            continue
        gap = line[current_end:start] if current_kind else ""
        continues = (
            prefix == "I"
            and raw_kind == current_kind
            and not re.search(r"[.!?;]", gap)
        )
        if not continues:
            flush()
            current_kind = raw_kind
            current_start, current_end = start, end
            current_scores = [confidence]
        else:
            current_end = max(current_end, end)
            current_scores.append(confidence)
    flush()
    return output


class BamiTeacher:
    """Vietnamese biomedical span teacher, run line-by-line to avoid bleed."""

    def __init__(self, checkpoint: str | Path) -> None:
        self.tokenizer = _load_fast_tokenizer(checkpoint)
        if not self.tokenizer.is_fast:
            raise ValueError("Bami teacher requires its fast tokenizer")
        self.model = AutoModelForTokenClassification.from_pretrained(str(checkpoint))
        self.device = _device()
        self.model.to(self.device)
        self.model.eval()
        self.id2label = {
            int(index): label for index, label in self.model.config.id2label.items()
        }

    def predict(
        self, text: str, max_length: int = 128, stride: int = 32
    ) -> list[Entity]:
        ranges = _line_ranges(text)
        if not ranges:
            return []
        lines = [text[start:end] for start, end in ranges]
        encoded = self.tokenizer(
            lines,
            truncation=True,
            max_length=max_length,
            stride=stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
            return_tensors="pt",
        )
        probability_batches: list[torch.Tensor] = []
        with torch.no_grad():
            for batch_start in range(0, encoded["input_ids"].shape[0], 16):
                batch_end = batch_start + 16
                result = self.model(
                    input_ids=encoded["input_ids"][batch_start:batch_end].to(
                        self.device
                    ),
                    attention_mask=encoded["attention_mask"][
                        batch_start:batch_end
                    ].to(self.device),
                )
                probability_batches.append(torch.softmax(result.logits, dim=-1).cpu())
        probabilities = torch.cat(probability_batches, dim=0)
        sample_mapping = encoded["overflow_to_sample_mapping"].tolist()
        entities: list[Entity] = []
        for line_index, (start, _) in enumerate(ranges):
            feature_indexes = [
                index
                for index, sample_index in enumerate(sample_mapping)
                if sample_index == line_index
            ]
            if not feature_indexes:
                continue
            entities.extend(
                _decode_teacher_line(
                    lines[line_index],
                    start,
                    {
                        "offset_mapping": encoded["offset_mapping"][
                            feature_indexes
                        ]
                    },
                    probabilities[feature_indexes],
                    self.id2label,
                )
            )
        return entities


def _overlap(left: Entity, right: Entity) -> int:
    return max(
        0,
        min(left.position[1], right.position[1])
        - max(left.position[0], right.position[0]),
    )


def _overlap_ratio(left: Entity, right: Entity) -> float:
    intersection = _overlap(left, right)
    return intersection / max(
        1,
        min(
            left.position[1] - left.position[0],
            right.position[1] - right.position[0],
        ),
    )


def _compact(entity: Entity) -> bool:
    words = entity.text.split()
    # Long anatomical diagnoses are common in these notes (e.g. a ten-word
    # spinal stenosis finding). Above fourteen words, Qwen proposals are much
    # more often full prose clauses than concepts.
    if not (1 <= len(words) <= 14):
        return False
    if entity.text.casefold().strip(" :-") in _GENERIC:
        return False
    if _NOISY_PHRASE.search(entity.text):
        return False
    if "\n" in entity.text:
        return False
    if len(entity.text.strip()) < 3:
        known_short = {
            str(value).casefold()
            for value, kind in load_lexicon().get("symptoms", {}).items()
            if kind == "TRIỆU_CHỨNG"
        }
        if entity.text.casefold().strip() not in known_short:
            return False
    return True


def _clone(entity: Entity, source: str, confidence: float | None = None) -> Entity:
    return Entity(
        text=entity.text,
        type=entity.type,
        assertions=list(entity.assertions),
        position=entity.position,
        candidates=list(entity.candidates) if entity.candidates is not None else None,
        confidence=confidence if confidence is not None else entity.confidence,
        source=source,
    )


def build_consensus(
    text: str,
    qwen_entities: list[Entity],
    rule_entities: list[Entity],
    teacher_entities: list[Entity],
) -> tuple[list[Entity], Counter[str]]:
    """Build conservative silver labels from three independent proposal sources."""

    selected: list[Entity] = []
    sources: Counter[str] = Counter()
    consumed_teacher: set[int] = set()
    consumed_rules: set[int] = set()

    for qwen in qwen_entities:
        same_rules = [
            (index, rule)
            for index, rule in enumerate(rule_entities)
            if rule.type == qwen.type and _overlap_ratio(qwen, rule) >= 0.7
        ]
        same_teachers = [
            (index, teacher)
            for index, teacher in enumerate(teacher_entities)
            if teacher.type == qwen.type and _overlap_ratio(qwen, teacher) >= 0.65
        ]
        if qwen.type == "THUỐC" and not same_rules:
            drug_evidence = bool(
                re.search(
                    r"\b(?:mg|mcg|g|ml|po|iv|im|sc|bid|tid|qid|prn|uống|"
                    r"tiêm|khí\s+dung)\b",
                    qwen.text,
                    re.IGNORECASE,
                )
            )
            if not drug_evidence and (
                _BAD_ACTION_SPAN.search(qwen.text) or len(qwen.text.split()) > 3
            ):
                sources["drug_without_evidence"] += 1
                continue
        if qwen.type == "TÊN_XÉT_NGHIỆM" and _BAD_ACTION_SPAN.search(qwen.text):
            sources["action_as_test_removed"] += 1
            continue
        if qwen.type in {"CHẨN_ĐOÁN", "TÊN_XÉT_NGHIỆM"} and _BAD_ACTION_SPAN.search(
            qwen.text
        ):
            sources["action_as_concept_removed"] += 1
            continue
        if same_rules:
            index, rule = max(
                same_rules,
                key=lambda item: (
                    item[1].confidence,
                    item[1].position[1] - item[1].position[0],
                ),
            )
            selected.append(_clone(rule, "consensus_rule_qwen", 0.98))
            consumed_rules.add(index)
            sources["rule+qwen"] += 1
        elif same_teachers and (
            _NOISY_PHRASE.search(qwen.text) or len(qwen.text.split()) > 14
        ):
            index, teacher = max(
                same_teachers, key=lambda item: item[1].confidence
            )
            # The teacher is used specifically to tighten generated prose spans.
            selected.append(_clone(teacher, "consensus_teacher_qwen", 0.94))
            consumed_teacher.add(index)
            sources["teacher+qwen"] += 1
        elif _compact(qwen):
            selected.append(_clone(qwen, "qwen_compact", 0.72))
            sources["qwen_compact"] += 1

    for index, rule in enumerate(rule_entities):
        if index in consumed_rules:
            continue
        if rule.type in {
            "THUỐC",
            "TÊN_XÉT_NGHIỆM",
            "KẾT_QUẢ_XÉT_NGHIỆM",
        } and rule.confidence >= 0.8:
            selected.append(_clone(rule, "rule_high_precision", 0.9))
            sources["rule_only"] += 1

    # Teacher-only concepts are deliberately not admitted. On this corpus the
    # teacher is strong at boundaries but still confuses headings/procedures;
    # it is a corrective signal for a Qwen proposal, not a recall source.

    # Exact duplicates are harmless in proposal sources but poisonous as BIO
    # supervision. Prefer agreement, then confidence, then tighter spans.
    by_key: dict[tuple[int, int, str], Entity] = {}
    for entity in selected:
        key = (entity.position[0], entity.position[1], entity.type)
        if key not in by_key or entity.confidence > by_key[key].confidence:
            by_key[key] = entity
    ranked = sorted(
        by_key.values(),
        key=lambda entity: (
            -entity.confidence,
            entity.position[1] - entity.position[0],
            entity.position[0],
        ),
    )
    non_overlapping: list[Entity] = []
    for entity in ranked:
        if any(_overlap(entity, accepted) for accepted in non_overlapping):
            sources["overlap_removed"] += 1
            continue
        non_overlapping.append(entity)
    non_overlapping.sort(key=lambda entity: entity.position)
    attach_assertions(non_overlapping, text)
    resolver = CandidateResolver()
    for entity in non_overlapping:
        resolver.resolve(entity, text)
    validate_entities(non_overlapping, text)
    return non_overlapping, sources


def prepare_silver_labels(
    input_dir: str | Path,
    qwen_dir: str | Path,
    output_path: str | Path,
    teacher_checkpoint: str | Path,
    report_path: str | Path | None = None,
    consensus_output_dir: str | Path | None = None,
    holdout_labels_path: str | Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_path = Path(input_dir)
    qwen_path = Path(qwen_dir)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    consensus_path = Path(consensus_output_dir) if consensus_output_dir else None
    if consensus_path:
        consensus_path.mkdir(parents=True, exist_ok=True)

    teacher = BamiTeacher(teacher_checkpoint)
    holdout_ids: set[str] = set()
    if holdout_labels_path and Path(holdout_labels_path).exists():
        holdout_ids = {
            str(json.loads(line).get("record_id"))
            for line in Path(holdout_labels_path)
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        }
    rows: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    records = sorted(input_path.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        if path.stem in holdout_ids:
            continue
        text = path.read_text(encoding="utf-8")
        qwen_file = qwen_path / f"{path.stem}.json"
        qwen = (
            entities_from_json(json.loads(qwen_file.read_text(encoding="utf-8")))
            if qwen_file.exists()
            else []
        )
        rules = detect_entities(text, load_lexicon(), profile="baseline")
        teacher_values = teacher.predict(text)
        entities, sources = build_consensus(text, qwen, rules, teacher_values)
        source_counts.update(sources)
        type_counts.update(entity.type for entity in entities)
        values = [entity.to_dict() for entity in entities]
        rows.append({"record_id": path.stem, "text": text, "entities": values})
        if consensus_path:
            (consensus_path / f"{path.stem}.json").write_text(
                json.dumps(values, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    target.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    report = {
        "records": len(rows),
        "holdout_records": len(holdout_ids),
        "holdout_labels_path": str(holdout_labels_path) if holdout_ids else None,
        "entities": sum(type_counts.values()),
        "entity_counts": dict(type_counts),
        "source_counts": dict(source_counts),
        "labels_path": str(target),
        "consensus_output_dir": str(consensus_path) if consensus_path else None,
        "teacher": str(teacher_checkpoint),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if report_path:
        report_target = Path(report_path)
        report_target.parent.mkdir(parents=True, exist_ok=True)
        report_target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def assemble_consensus_output(
    input_dir: str | Path,
    consensus_dir: str | Path,
    holdout_labels_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Materialize a full 100-record candidate without model-only inference."""

    started = time.perf_counter()
    input_path = Path(input_dir)
    consensus_path = Path(consensus_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    holdout = {
        str(json.loads(line)["record_id"]): json.loads(line).get("entities", [])
        for line in Path(holdout_labels_path)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    resolver = CandidateResolver()
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(input_path.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            if path.stem in holdout:
                values = holdout[path.stem]
            else:
                source = consensus_path / f"{path.stem}.json"
                values = json.loads(source.read_text(encoding="utf-8"))
            entities = entities_from_json(values)
            attach_assertions(entities, text)
            for entity in entities:
                resolver.resolve(entity, text)
            validate_entities(entities, text)
            counts.update(entity.type for entity in entities)
            (output_path / f"{path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in entities],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
            (output_path / f"{path.stem}.json").write_text("[]\n", encoding="utf-8")
    report = {
        "records": len(records),
        "entity_counts": dict(counts),
        "errors": errors,
        "holdout_records": len(holdout),
        "source": str(consensus_path),
        "output": str(output_path),
        "offline": True,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
