from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .assertions import attach_assertions
from .candidates import CandidateResolver
from .normalize import normalize_key
from .proposals import Proposal, dump_proposals
from .schema import Entity
from .validator import validate_entities


DEFAULT_MODEL = (
    "/Users/mac/.cache/huggingface/hub/"
    "models--leduckhai--VietMed-NER/snapshots/"
    "cccffb7de14423114f7d4bafc9f736b9d866e446/"
    "xlm-roberta-base-VietMed-NER"
)

LABEL_TO_TYPE = {
    "DRUGCHEMICAL": "THUỐC",
    "DIAGNOSTICS": "TÊN_XÉT_NGHIỆM",
    "AGE": "THÔNG_TIN_BỆNH_NHÂN",
    "GENDER": "THÔNG_TIN_BỆNH_NHÂN",
}

# These are annotation labels/headings or fragments that the public VietMed
# model systematically mistakes for a medical mention in this corpus.
GENERIC_NOISE = {
    "benh",
    "chan doan",
    "trieu chung",
    "dau hieu",
    "xet nghiem",
    "ket qua",
    "dieu tri",
    "nhập",
    "nhap",
    "nhap vien",
    "xuat vien",
    "gang suc",
    "benh nhan",
    "theo doi",
}

DIAGNOSIS_SECTIONS = re.compile(
    r"(?:^|\n)\s*(?:chẩn\s*đoán|đánh\s*giá|bệnh\s*kèm|"
    r"tiền\s*sử\s*bệnh|bệnh\s*lý|vấn\s*đề)\s*:?",
    re.IGNORECASE,
)
SYMPTOM_SECTIONS = re.compile(
    r"(?:^|\n)\s*(?:triệu\s*chứng|lý\s*do\s*(?:vào|nhập)\s*viện|"
    r"bệnh\s*sử\s*hiện\s*tại|than\s*phiền)\s*:?",
    re.IGNORECASE,
)
DIAGNOSIS_CUES = re.compile(
    r"\b(?:chẩn\s*đoán|mắc|bị|bệnh|hội\s*chứng|viêm|nhiễm|"
    r"suy|ung\s*thư|u\s+|rối\s*loạn|tăng\s+huyết\s*áp|đái\s*tháo\s*đường|"
    r"đột\s*quỵ|nhồi\s*máu|xuất\s*huyết)\b",
    re.IGNORECASE,
)
SYMPTOM_CUES = re.compile(
    r"\b(?:đau|ho|sốt|khó\s*thở|buồn\s*nôn|nôn|chóng\s*mặt|"
    r"mệt|yếu|tê|phù|ngứa|chảy\s*máu|đánh\s*trống\s*ngực|"
    r"mất\s*ngủ|lo\s*âu|sụt\s*cân|tiêu\s*chảy|táo\s*bón)\b",
    re.IGNORECASE,
)
RESULT_VALUE = re.compile(
    r"^(?:[<>~=]?\s*)?\d+(?:[.,]\d+)?"
    r"(?:\s*(?:-|–|/)\s*\d+(?:[.,]\d+)?)?"
    r"(?:\s*(?:%|mg/dl|mmol/l|g/dl|u/l|iu/l|mmhg|bpm|cm|mm))?$",
    re.IGNORECASE,
)
DRUG_TAIL = re.compile(
    r"""
    (?:\s+
       (?:
         \d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?\s*
           (?:mg|mcg|µg|g|ml|mL|đơn\s*vị|units?|%)
         |po|iv|im|sc|sl|pr|inh
         |uống|tiêm|tĩnh\s*mạch|bắp|dưới\s*da|dưới\s*lưỡi|khí\s*dung
         |daily|bid|tid|qid|qam|qpm|qhs|q\d+h|prn
         |\d+\s*lần(?:/ngày)?
       )
    )+
    (?:\s*:\s*prn)?
    """,
    re.IGNORECASE | re.VERBOSE,
)
DRUG_FALSE_POSITIVE = re.compile(
    r"^(?:ca|caffeine|cà\s*phê|rượu|bia|thuốc\s*lá|oxy|o2)$",
    re.IGNORECASE,
)


@dataclass
class RawSpan:
    start: int
    end: int
    label: str
    confidence: float


def _line_spans(text: str) -> list[tuple[int, str]]:
    """Return non-empty lines with their absolute character start."""
    result: list[tuple[int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        value = line.rstrip("\r\n")
        if value.strip():
            result.append((cursor, value))
        cursor += len(line)
    if text and not text.endswith(("\n", "\r")) and not result:
        result.append((0, text))
    return result


def _bio_parts(label: str) -> tuple[str, str]:
    if label in {"0", "O"} or "-" not in label:
        return "O", ""
    prefix, kind = label.split("-", 1)
    return prefix, kind


def _decode_line(
    line: str,
    absolute_start: int,
    offsets: Iterable[tuple[int, int]],
    label_ids: Iterable[int],
    probabilities: Iterable[float],
    id2label: dict[int, str],
) -> list[RawSpan]:
    spans: list[RawSpan] = []
    active: RawSpan | None = None
    for (start, end), label_id, probability in zip(offsets, label_ids, probabilities):
        if start == end:
            continue
        prefix, kind = _bio_parts(id2label[int(label_id)])
        if prefix == "O":
            if active is not None:
                spans.append(active)
                active = None
            continue
        token_start, token_end = absolute_start + int(start), absolute_start + int(end)
        if active is not None:
            gap = line[active.end - absolute_start:int(start)]
            # Some checkpoints output B/B for two sentencepiece fragments of
            # the same word. Merge only zero-width fragments here. Medication
            # dose/form pieces are merged separately with an explicit grammar.
            continuation = kind == active.label and (
                prefix == "I" or (prefix == "B" and gap == "")
            )
            if continuation:
                old_length = max(1, active.end - active.start)
                token_length = max(1, token_end - token_start)
                active.confidence = (
                    active.confidence * old_length + float(probability) * token_length
                ) / (old_length + token_length)
                active.end = token_end
                continue
            spans.append(active)
        active = RawSpan(token_start, token_end, kind, float(probability))
    if active is not None:
        spans.append(active)
    return spans


def _recent_section(text: str, start: int) -> str:
    before = text[:start]
    line_start = before.rfind("\n")
    current = before[line_start + 1:]
    if ":" in current:
        return current.split(":", 1)[0].strip().casefold()
    previous = before[:line_start].splitlines()[-4:]
    for line in reversed(previous):
        stripped = line.strip()
        if stripped and (stripped.endswith(":") or len(stripped.split()) <= 6):
            return stripped.rstrip(":").casefold()
    return ""


def _overlap_ratio(a: tuple[int, int], b: tuple[int, int]) -> float:
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    return overlap / max(1, min(a[1] - a[0], b[1] - b[0]))


def _disease_type(
    text: str,
    span: RawSpan,
    reference: list[Entity],
) -> tuple[str, str]:
    for entity in reference:
        if entity.type not in {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}:
            continue
        if _overlap_ratio((span.start, span.end), entity.position) >= 0.65:
            return entity.type, "qwen_overlap"
    mention = text[span.start:span.end]
    section = _recent_section(text, span.start)
    if DIAGNOSIS_SECTIONS.search("\n" + section):
        return "CHẨN_ĐOÁN", "diagnosis_section"
    if SYMPTOM_SECTIONS.search("\n" + section):
        return "TRIỆU_CHỨNG", "symptom_section"
    left = text[max(0, span.start - 45):span.start]
    if re.search(r"(?:chẩn\s*đoán|tiền\s*sử|mắc|bị)\s*:?\s*$", left, re.IGNORECASE):
        return "CHẨN_ĐOÁN", "local_diagnosis_cue"
    if SYMPTOM_CUES.search(mention):
        return "TRIỆU_CHỨNG", "symptom_lexical"
    if DIAGNOSIS_CUES.search(mention):
        return "CHẨN_ĐOÁN", "diagnosis_lexical"
    # The source VietMed label is named DISEASESYMTOM and in practice contains
    # many complaints. Symptom is the safer default: a wrong type is penalized
    # as two unmatched entities by the organiser.
    return "TRIỆU_CHỨNG", "symptom_default"


def _extend_drug(text: str, span: RawSpan) -> RawSpan:
    line_end = text.find("\n", span.end)
    if line_end < 0:
        line_end = len(text)
    match = DRUG_TAIL.match(text, span.end, line_end)
    if match:
        span.end = match.end()
    return span


def _clean_entity(entity: Entity, text: str) -> Entity | None:
    start, end = entity.position
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    while end > start and text[end - 1] in ",;:":
        end -= 1
    if start >= end:
        return None
    entity.position = (start, end)
    entity.text = text[start:end]
    key = normalize_key(entity.text).strip(" .,:;()[]")
    if not key or key in GENERIC_NOISE or len(key) == 1:
        return None
    if entity.type == "THUỐC" and DRUG_FALSE_POSITIVE.fullmatch(key):
        return None
    if entity.type == "THÔNG_TIN_BỆNH_NHÂN" and not re.search(
        r"(?:\d+\s*tuổi|\b(?:nam|nữ)\b)", entity.text, re.IGNORECASE
    ):
        return None
    return entity


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    result: list[Entity] = []
    for entity in sorted(
        entities,
        key=lambda item: (item.position[0], -(item.position[1] - item.position[0])),
    ):
        duplicate = next(
            (
                other
                for other in result
                if other.type == entity.type
                and _overlap_ratio(other.position, entity.position) >= 0.85
            ),
            None,
        )
        if duplicate is None:
            result.append(entity)
        elif entity.confidence > duplicate.confidence:
            result.remove(duplicate)
            result.append(entity)
    return sorted(result, key=lambda item: item.position)


class VietMedDetector:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL, device: str = "auto") -> None:
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "VietMed-NER requires torch and transformers. "
                "Run this command with /opt/anaconda3/bin/python."
            ) from exc
        path = str(model_path)
        if not Path(path).exists():
            raise FileNotFoundError(f"Local VietMed-NER checkpoint not found: {path}")
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForTokenClassification.from_pretrained(
            path, local_files_only=True
        )
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
        self.id2label = {
            int(key): value for key, value in self.model.config.id2label.items()
        }

    def predict_raw(
        self, text: str, batch_size: int = 16, min_confidence: float = 0.55
    ) -> list[RawSpan]:
        lines = _line_spans(text)
        result: list[RawSpan] = []
        for batch_start in range(0, len(lines), batch_size):
            batch = lines[batch_start:batch_start + batch_size]
            values = [line for _, line in batch]
            encoded = self.tokenizer(
                values,
                padding=True,
                truncation=True,
                max_length=512,
                return_offsets_mapping=True,
                return_tensors="pt",
            )
            offsets = encoded.pop("offset_mapping")
            model_inputs = {key: value.to(self.device) for key, value in encoded.items()}
            with self.torch.inference_mode():
                logits = self.model(**model_inputs).logits
                probs = logits.softmax(dim=-1)
                confidence, labels = probs.max(dim=-1)
            for row, (absolute_start, line) in enumerate(batch):
                decoded = _decode_line(
                    line,
                    absolute_start,
                    offsets[row].tolist(),
                    labels[row].cpu().tolist(),
                    confidence[row].cpu().tolist(),
                    self.id2label,
                )
                result.extend(span for span in decoded if span.confidence >= min_confidence)
        return result

    def detect(
        self,
        text: str,
        reference: list[Entity] | None = None,
        batch_size: int = 16,
        min_confidence: float = 0.55,
        resolver: CandidateResolver | None = None,
    ) -> tuple[list[Entity], Counter[str]]:
        reference = reference or []
        counts: Counter[str] = Counter()
        entities: list[Entity] = []
        for span in self.predict_raw(text, batch_size, min_confidence):
            if span.label == "DISEASESYMTOM":
                kind, reason = _disease_type(text, span, reference)
                counts[f"disease_type:{reason}"] += 1
            else:
                kind = LABEL_TO_TYPE.get(span.label, "")
            if not kind:
                counts[f"ignored:{span.label}"] += 1
                continue
            if kind == "THUỐC":
                span = _extend_drug(text, span)
            entity = Entity(
                text=text[span.start:span.end],
                type=kind,
                assertions=[],
                position=(span.start, span.end),
                candidates=[] if kind in {"CHẨN_ĐOÁN", "THUỐC"} else None,
                confidence=span.confidence,
                source="vietmed_ner",
            )
            entity = _clean_entity(entity, text)
            if entity is None:
                counts["filtered_noise"] += 1
                continue
            entities.append(entity)
        entities = _deduplicate(entities)
        attach_assertions(entities, text)
        resolver = resolver or CandidateResolver()
        for entity in entities:
            resolver.resolve(entity, text)
        validate_entities(entities, text)
        counts.update(f"output:{entity.type}" for entity in entities)
        return entities, counts


def _load_reference(path: Path) -> list[Entity]:
    if not path.exists():
        return []
    return [Entity.from_dict(value) for value in json.loads(path.read_text(encoding="utf-8"))]


def infer_vietmed_directory(
    input_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    model_path: str | Path = DEFAULT_MODEL,
    reference_dir: str | Path | None = "output_v5_precision_btc",
    batch_size: int = 16,
    min_confidence: float = 0.55,
    device: str = "auto",
    proposal_dir: str | Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs, outputs = Path(input_dir), Path(output_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    proposal_root = Path(proposal_dir) if proposal_dir else None
    if proposal_root:
        proposal_root.mkdir(parents=True, exist_ok=True)
    reference_root = Path(reference_dir) if reference_dir else None
    detector = VietMedDetector(model_path, device)
    resolver = CandidateResolver()
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for index, path in enumerate(records, 1):
        try:
            text = path.read_text(encoding="utf-8")
            reference = (
                _load_reference(reference_root / f"{path.stem}.json")
                if reference_root
                else []
            )
            entities, row_counts = detector.detect(
                text, reference, batch_size, min_confidence, resolver
            )
            counts.update(row_counts)
            (outputs / f"{path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in entities],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if proposal_root:
                dump_proposals(
                    [Proposal.from_entity(entity) for entity in entities],
                    proposal_root / f"{path.stem}.json",
                )
            print(
                f"[{index:03d}/{len(records):03d}] {path.name}: "
                f"{len(entities)} entities",
                flush=True,
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
            print(
                f"[{index:03d}/{len(records):03d}] {path.name}: ERROR {exc}",
                flush=True,
            )
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "device": str(detector.device),
        "model": str(model_path),
        "reference_dir": str(reference_dir) if reference_dir else None,
        "min_confidence": min_confidence,
        "counts": dict(counts),
        "errors": errors,
        "offline": True,
        "proposal_dir": str(proposal_root) if proposal_root else None,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
