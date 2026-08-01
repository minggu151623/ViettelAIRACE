from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .schema import Entity
from .v6_rebuild import (
    DRUG_ACTION_PREFIX,
    DRUG_GLUE_SUFFIX,
    DRUG_INDICATION_SUFFIX,
)
from .validator import validate_entities


def _embedded_short_symptoms(
    text: str, entities: list[Entity], stats: Counter[str]
) -> list[Entity]:
    kept: list[Entity] = []
    for entity in entities:
        if entity.type == "TRIỆU_CHỨNG" and len(entity.text.strip()) <= 4:
            start, end = entity.position
            left = text[start - 1:start] if start else ""
            right = text[end:end + 1]
            if (left and (left.isalnum() or left == "_")) or (
                right and (right.isalnum() or right == "_")
            ):
                stats["removed:embedded_short_symptom"] += 1
                continue
        kept.append(entity)
    return kept


def _drug_boundaries(
    text: str, entities: list[Entity], stats: Counter[str]
) -> list[Entity]:
    for entity in entities:
        if entity.type != "THUỐC":
            continue
        prefix = DRUG_ACTION_PREFIX.match(entity.text)
        if prefix:
            start = entity.position[0] + prefix.end()
            entity.position = (start, entity.position[1])
            entity.text = text[start:entity.position[1]]
            stats["trimmed:drug_action_prefix"] += 1
        suffix = DRUG_INDICATION_SUFFIX.search(entity.text)
        if suffix:
            end = entity.position[0] + suffix.start()
            entity.text = text[entity.position[0]:end].rstrip()
            entity.position = (entity.position[0], entity.position[0] + len(entity.text))
            stats["trimmed:drug_indication_suffix"] += 1
        glued = DRUG_GLUE_SUFFIX.search(entity.text)
        if glued:
            end = entity.position[0] + glued.start()
            entity.text = text[entity.position[0]:end]
            entity.position = (entity.position[0], end)
            stats["trimmed:drug_glued_history_suffix"] += 1
    return entities


def run_ablation(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    mode: str,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Apply exactly one post-processing intervention to a V6 output."""
    if mode not in {"assertion_only", "boundary_only", "drug_boundary_only"}:
        raise ValueError(f"unsupported ablation mode: {mode}")
    started = time.perf_counter()
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda p: int(p.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            entities = [
                Entity.from_dict(value)
                for value in json.loads((source / f"{path.stem}.json").read_text(encoding="utf-8"))
            ]
            if mode == "assertion_only":
                attach_assertions(entities, text)
            elif mode == "boundary_only":
                entities = _embedded_short_symptoms(text, entities, stats)
            else:
                entities = _drug_boundaries(text, entities, stats)
            entities.sort(key=lambda entity: entity.position)
            validate_entities(entities, text)
            stats["output_entities"] += len(entities)
            (output / f"{path.stem}.json").write_text(
                json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "mode": mode,
        "source": str(source),
        "output": str(output),
        "stats": dict(stats),
        "errors": errors,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
