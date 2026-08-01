from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from transformers import AutoModelForTokenClassification

from .assertions import attach_assertions
from .schema import Entity
from .serialization import dumps_btc
from .train import _device, _load_fast_tokenizer, predict_token_entities
from .validator import validate_entities


MEDICAL_LABEL_MAP = {
    "ten_benh": "CHẨN_ĐOÁN",
    "trieu_chung_benh": "TRIỆU_CHỨNG",
    "bien_phap_chan_doan": "TÊN_XÉT_NGHIỆM",
}
MIN_CONFIDENCE = {
    "CHẨN_ĐOÁN": 0.97,
    "TRIỆU_CHỨNG": 0.98,
    "TÊN_XÉT_NGHIỆM": 0.98,
}
NON_DIAGNOSTIC_PROCEDURE = re.compile(
    r"\b(?:đặt\s+)?(?:ống nội khí quản|truyền dịch|tips|catheter|stent|"
    r"dẫn lưu|phẫu thuật|điều trị)\b",
    re.IGNORECASE,
)


def _overlap_ratio(left: tuple[int, int], right: tuple[int, int]) -> float:
    intersection = max(0, min(left[1], right[1]) - max(left[0], right[0]))
    return intersection / max(1, min(left[1] - left[0], right[1] - right[0]))


def _consensus_additions(
    text: str,
    teacher: list[Entity],
    student: list[Entity],
    baseline: list[Entity],
) -> tuple[list[Entity], Counter[str]]:
    additions: list[Entity] = []
    stats: Counter[str] = Counter()
    for entity in teacher:
        mapped_type = MEDICAL_LABEL_MAP.get(entity.type)
        if mapped_type is None:
            continue
        if entity.confidence < MIN_CONFIDENCE[mapped_type]:
            stats[f"below_threshold:{mapped_type}"] += 1
            continue
        if len(entity.text.strip()) < 2:
            stats[f"fragment:{mapped_type}"] += 1
            continue
        if mapped_type == "CHẨN_ĐOÁN" and len(entity.text.split()) < 2:
            stats[f"fragment:{mapped_type}"] += 1
            continue
        if mapped_type == "TÊN_XÉT_NGHIỆM" and (
            len(entity.text.strip()) < 4
            or NON_DIAGNOSTIC_PROCEDURE.search(entity.text)
        ):
            stats[f"semantic_filter:{mapped_type}"] += 1
            continue
        if not any(
            candidate.type == mapped_type
            and _overlap_ratio(entity.position, candidate.position) >= 0.5
            for candidate in student
        ):
            stats[f"no_student_agreement:{mapped_type}"] += 1
            continue
        # Do not alter a baseline annotation or introduce nested alternatives.
        # This ensemble is an evidence-gated recall expansion only.
        if any(
            _overlap_ratio(entity.position, candidate.position) > 0
            for candidate in baseline
        ):
            stats[f"baseline_overlap:{mapped_type}"] += 1
            continue
        additions.append(
            Entity(
                text=text[entity.position[0] : entity.position[1]],
                type=mapped_type,
                position=entity.position,
                candidates=[] if mapped_type == "CHẨN_ĐOÁN" else None,
                confidence=entity.confidence,
                source="medical_teacher+weighted_student",
            )
        )
        stats[f"accepted:{mapped_type}"] += 1

    # Sliding windows can still propose nested versions. Keep the longest
    # high-confidence boundary for each same-type overlap.
    kept: list[Entity] = []
    for entity in sorted(
        additions,
        key=lambda item: (-item.confidence, -len(item.text), item.position),
    ):
        if any(
            current.type == entity.type
            and _overlap_ratio(current.position, entity.position) > 0
            for current in kept
        ):
            stats[f"deduplicated:{entity.type}"] += 1
            continue
        kept.append(entity)
    attach_assertions(kept, text)
    return kept, stats


def build_teacher_student_ensemble(
    input_dir: str | Path,
    student_dir: str | Path,
    baseline_dir: str | Path,
    teacher_checkpoint: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs = Path(input_dir)
    student_root = Path(student_dir)
    baseline_root = Path(baseline_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    tokenizer = _load_fast_tokenizer(teacher_checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(teacher_checkpoint))
    device = _device()
    model.to(device)
    model.eval()
    totals: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            student = [
                Entity.from_dict(value)
                for value in json.loads(
                    (student_root / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            baseline = [
                Entity.from_dict(value)
                for value in json.loads(
                    (baseline_root / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            teacher = predict_token_entities(
                text,
                model=model,
                tokenizer=tokenizer,
                device=device,
                max_length=1024,
                stride=128,
            )
            additions, stats = _consensus_additions(text, teacher, student, baseline)
            totals.update(stats)
            entities = sorted(
                baseline + additions,
                key=lambda item: (item.position, item.type),
            )
            validate_entities(entities, text)
            totals.update(f"output:{entity.type}" for entity in entities)
            (output_root / f"{path.stem}.json").write_text(
                dumps_btc([entity.to_dict() for entity in entities]) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "device": str(device),
        "teacher_checkpoint": str(teacher_checkpoint),
        "student": str(student_root),
        "baseline": str(baseline_root),
        "thresholds": MIN_CONFIDENCE,
        "stats": dict(totals),
        "errors": errors,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
