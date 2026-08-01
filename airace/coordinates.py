from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import Entity
from .serialization import dumps_btc
from .validator import validate_entities


def lf_to_crlf_offset(text: str, offset: int) -> int:
    if not 0 <= offset <= len(text):
        raise ValueError(f"offset outside LF text: {offset}")
    return offset + text.count("\n", 0, offset)


def project_entity_to_crlf(text: str, entity: Entity) -> Entity:
    projected = Entity.from_dict(entity.to_dict())
    projected.position = (
        lf_to_crlf_offset(text, entity.position[0]),
        lf_to_crlf_offset(text, entity.position[1]),
    )
    return projected


def project_directory_to_crlf(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs = Path(input_dir)
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    shifted = 0
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            entities = [
                Entity.from_dict(value)
                for value in json.loads(
                    (source / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            projected = [project_entity_to_crlf(text, entity) for entity in entities]
            validate_entities(projected, text, position_mode="crlf")
            shifted += sum(
                before.position != after.position
                for before, after in zip(entities, projected)
            )
            counts.update(entity.type for entity in projected)
            (output / f"{path.stem}.json").write_text(
                dumps_btc([entity.to_dict() for entity in projected]) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "source": str(source),
        "output": str(output),
        "position_mode": "crlf",
        "shifted_entities": shifted,
        "entity_counts": dict(counts),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
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
