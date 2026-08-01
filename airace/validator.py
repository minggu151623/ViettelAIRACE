from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .schema import ASSERTIONS, CANDIDATE_TYPES, ENTITY_TYPES, Entity, entities_from_json


class ValidationError(ValueError):
    pass


def validate_entity(
    entity: Entity, raw_text: str, position_mode: str = "raw"
) -> None:
    if position_mode not in {"raw", "crlf"}:
        raise ValidationError(f"unknown position mode: {position_mode}")
    coordinate_text = (
        raw_text if position_mode == "raw" else raw_text.replace("\n", "\r\n")
    )
    start, end = entity.position
    if entity.type not in ENTITY_TYPES:
        raise ValidationError(f"unknown type: {entity.type}")
    if any(a not in ASSERTIONS for a in entity.assertions):
        raise ValidationError(f"unknown assertion in {entity}")
    if not (0 <= start < end <= len(coordinate_text)):
        raise ValidationError(f"invalid position {entity.position}")
    if coordinate_text[start:end] != entity.text:
        raise ValidationError(
            f"text/position mismatch: {entity.text!r} != {coordinate_text[start:end]!r}"
        )
    if entity.type not in CANDIDATE_TYPES and entity.candidates not in (None, []):
        raise ValidationError(f"candidates are not allowed for {entity.type}")


def validate_entities(
    entities: list[Entity], raw_text: str, position_mode: str = "raw"
) -> None:
    previous = (-1, -1)
    seen: set[tuple[int, int, str]] = set()
    for entity in entities:
        validate_entity(entity, raw_text, position_mode)
        if entity.position < previous:
            raise ValidationError("entities are not sorted by position")
        key = (*entity.position, entity.type)
        if key in seen:
            raise ValidationError(f"duplicate entity: {key}")
        seen.add(key)
        previous = entity.position


def validate_output_dir(
    input_dir: str | Path,
    output_dir: str | Path,
    position_mode: str = "raw",
) -> dict[str, Any]:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    errors: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    expected = sorted((p.stem for p in input_path.glob("*.txt")), key=lambda x: int(x))
    found = sorted((p.stem for p in output_path.glob("*.json")), key=lambda x: int(x))
    if expected != found:
        errors.append({"kind": "file_set", "detail": f"expected={expected}, found={found}"})
    for stem in expected:
        if stem not in found:
            continue
        try:
            import json

            raw = (input_path / f"{stem}.txt").read_text(encoding="utf-8")
            values = json.loads((output_path / f"{stem}.json").read_text(encoding="utf-8"))
            entities = entities_from_json(values)
            validate_entities(entities, raw, position_mode)
            counts.update(e.type for e in entities)
        except Exception as exc:
            errors.append({"kind": "record", "record": stem, "detail": str(exc)})
    return {
        "ok": not errors,
        "errors": errors,
        "records": len(expected),
        "position_mode": position_mode,
        "counts": dict(counts),
    }
