from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .schema import Entity, entities_from_json
from .validator import validate_entities


FIELD_ORDER = ("text", "type", "candidates", "assertions", "position")


def dumps_btc(values: Iterable[dict[str, Any]]) -> str:
    """Serialize entities using the visual layout in the organiser sample."""

    rows = list(values)
    if not rows:
        return "[]\n"
    lines = ["["]
    for row_index, row in enumerate(rows):
        lines.append("  {")
        fields = [name for name in FIELD_ORDER if name in row]
        for field_index, name in enumerate(fields):
            value = json.dumps(
                row[name],
                ensure_ascii=False,
                separators=(", ", ": "),
            )
            comma = "," if field_index < len(fields) - 1 else ""
            key = json.dumps(name, ensure_ascii=False)
            lines.append(f"    {key}: {value}{comma}")
        comma = "," if row_index < len(rows) - 1 else ""
        lines.append(f"  }}{comma}")
    lines.append("]")
    return "\n".join(lines) + "\n"


def format_directory_btc(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_dir)
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    records = sorted(input_path.glob("*.txt"), key=lambda path: int(path.stem))
    entities_total = 0
    errors: list[dict[str, str]] = []
    for text_path in records:
        try:
            text = text_path.read_text(encoding="utf-8")
            source_values = json.loads(
                (source_path / f"{text_path.stem}.json").read_text(encoding="utf-8")
            )
            entities: list[Entity] = entities_from_json(source_values)
            validate_entities(entities, text)
            values = [entity.to_dict() for entity in entities]
            serialized = dumps_btc(values)
            if json.loads(serialized) != values:
                raise ValueError("BTC serialization changed JSON values")
            (output_path / f"{text_path.stem}.json").write_text(
                serialized,
                encoding="utf-8",
            )
            entities_total += len(entities)
        except Exception as exc:
            errors.append({"record": text_path.stem, "error": str(exc)})
    return {
        "records": len(records),
        "entities": entities_total,
        "errors": errors,
        "source": str(source_path),
        "output": str(output_path),
        "layout": "BTC sample: inline short arrays",
    }
