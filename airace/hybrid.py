from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import Entity
from .serialization import dumps_btc
from .validator import validate_entities


LEARNED_TYPES = {"TRIỆU_CHỨNG", "CHẨN_ĐOÁN", "TÊN_XÉT_NGHIỆM"}
LEGACY_TYPES = {"THUỐC", "KẾT_QUẢ_XÉT_NGHIỆM", "THÔNG_TIN_BỆNH_NHÂN"}


def _overlaps(left: Entity, right: Entity) -> bool:
    return left.position[0] < right.position[1] and right.position[0] < left.position[1]


def merge_specialist_entities(
    raw_text: str,
    learned: list[Entity],
    legacy: list[Entity],
) -> tuple[list[Entity], Counter[str]]:
    """Route entity types to the locally strongest specialist.

    The learned token classifier owns symptoms, diagnoses and test names.  V6 owns
    drugs, test results and patient information, whose sparse labels do not yet
    support reliable learning.  Exact V6 matches retain their reviewed metadata.
    """
    stats: Counter[str] = Counter()
    legacy_by_key = {
        (*entity.position, entity.type): entity
        for entity in legacy
    }
    protected = [entity for entity in legacy if entity.type in LEGACY_TYPES]
    merged = list(protected)
    stats.update({f"legacy:{entity.type}": 1 for entity in protected})

    for entity in learned:
        if entity.type not in LEARNED_TYPES:
            continue
        key = (*entity.position, entity.type)
        old = legacy_by_key.get(key)
        if old is not None:
            # Preserve V6 assertions. Diagnosis codes are deliberately omitted:
            # the blind leaderboard showed that uncalibrated ICD linking hurts.
            selected = Entity.from_dict(old.to_dict())
            if selected.type == "CHẨN_ĐOÁN":
                selected.candidates = []
            merged.append(selected)
            stats[f"agreement:{entity.type}"] += 1
            continue
        if any(_overlaps(entity, item) for item in protected):
            stats[f"dropped_overlap:{entity.type}"] += 1
            continue
        selected = Entity.from_dict(entity.to_dict())
        if selected.type == "CHẨN_ĐOÁN":
            selected.candidates = []
        merged.append(selected)
        stats[f"learned:{entity.type}"] += 1

    # Prefer longer spans when the learned model emits overlapping alternatives
    # of the same type, while preserving different-type annotations.
    unique: dict[tuple[int, int, str], Entity] = {}
    for entity in sorted(
        merged,
        key=lambda item: (item.position[0], -item.position[1], item.type),
    ):
        same_type_overlap = [
            current
            for current in unique.values()
            if current.type == entity.type and _overlaps(current, entity)
        ]
        if same_type_overlap:
            best = max(same_type_overlap + [entity], key=lambda item: len(item.text))
            for current in same_type_overlap:
                unique.pop((*current.position, current.type), None)
            unique[(*best.position, best.type)] = best
        else:
            unique[(*entity.position, entity.type)] = entity
    output = sorted(unique.values(), key=lambda item: (item.position, item.type))
    validate_entities(output, raw_text)
    return output, stats


def build_specialist_hybrid(
    input_dir: str | Path,
    learned_dir: str | Path,
    legacy_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs = Path(input_dir)
    learned_root = Path(learned_dir)
    legacy_root = Path(legacy_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        try:
            raw_text = path.read_text(encoding="utf-8")
            learned = [
                Entity.from_dict(value)
                for value in json.loads(
                    (learned_root / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            legacy = [
                Entity.from_dict(value)
                for value in json.loads(
                    (legacy_root / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            entities, stats = merge_specialist_entities(raw_text, learned, legacy)
            totals.update(stats)
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
        "learned": str(learned_root),
        "legacy": str(legacy_root),
        "output": str(output_root),
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
