from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import Entity
from .serialization import dumps_btc
from .validator import validate_entities, validate_entity, validate_output_dir


def _is_calibration_dummy(entity: Entity, raw_text: str) -> bool:
    """Identify synthetic unmatched rows without relying on a record id."""

    start, end = entity.position
    return entity.text == "x" and start >= len(raw_text) and end > start


def reconstruct_pseudo_labels(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    *,
    expected_kept: int | None = 3168,
    expected_dropped: int | None = 940,
) -> dict[str, Any]:
    """Build submission JSON from valid pseudo-label rows only.

    Any malformed row that is not an explicit out-of-range calibration dummy
    aborts the build.  This fail-closed behavior prevents genuine annotation
    errors from being silently discarded together with the synthetic rows.
    """

    inputs = Path(input_dir)
    source = Path(source_dir)
    output = Path(output_dir)
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    if not records:
        raise ValueError(f"no numbered text records found in {inputs}")

    output.mkdir(parents=True, exist_ok=True)
    kept = 0
    dropped = 0
    counts: Counter[str] = Counter()
    assertion_counts: Counter[str] = Counter()
    candidate_rows = 0

    for text_path in records:
        raw_text = text_path.read_text(encoding="utf-8")
        source_path = source / f"{text_path.stem}.json"
        if not source_path.is_file():
            raise ValueError(f"missing pseudo-label file: {source_path}")
        values = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError(f"{source_path}: top-level value must be a list")

        entities: list[Entity] = []
        for index, value in enumerate(values):
            entity = Entity.from_dict(value)
            if _is_calibration_dummy(entity, raw_text):
                dropped += 1
                continue
            try:
                validate_entity(entity, raw_text)
            except Exception as exc:
                raise ValueError(f"{source_path}: invalid real row {index}: {exc}") from exc
            entities.append(entity)

        entities.sort(key=lambda item: (item.position[0], item.position[1], item.type, item.text))
        validate_entities(entities, raw_text)
        rendered = dumps_btc(entity.to_dict() for entity in entities)
        (output / f"{text_path.stem}.json").write_text(rendered, encoding="utf-8")

        kept += len(entities)
        counts.update(entity.type for entity in entities)
        for entity in entities:
            assertion_counts.update(entity.assertions)
            candidate_rows += bool(entity.candidates)

    if expected_kept is not None and kept != expected_kept:
        raise ValueError(f"expected {expected_kept} real rows, found {kept}")
    if expected_dropped is not None and dropped != expected_dropped:
        raise ValueError(f"expected {expected_dropped} calibration rows, found {dropped}")

    validation = validate_output_dir(inputs, output)
    if not validation["ok"]:
        raise ValueError(json.dumps(validation, ensure_ascii=False))

    report: dict[str, Any] = {
        "hypothesis": "H22_calibrated_pseudo_reconstruction",
        "records": len(records),
        "kept_real_rows": kept,
        "dropped_calibration_rows": dropped,
        "counts": dict(sorted(counts.items())),
        "assertions": dict(sorted(assertion_counts.items())),
        "rows_with_candidates": candidate_rows,
        "validation": validation,
        "output": str(output),
    }
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
