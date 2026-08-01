from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .schema import entities_from_json
from .validator import validate_entities


def preserve_qwen_with_current_assertions(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Copy Qwen spans/types/candidates and refresh only local assertions.

    This is deliberately conservative: candidate lists and offsets are never
    resolved or rewritten. It isolates assertion changes from detector and
    linker changes so a leaderboard submission is auditable.
    """

    started = time.perf_counter()
    input_path = Path(input_dir)
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    changed_assertions = 0
    changed_records = 0
    errors: list[dict[str, str]] = []
    records = sorted(input_path.glob("*.txt"), key=lambda path: int(path.stem))
    for text_path in records:
        try:
            text = text_path.read_text(encoding="utf-8")
            values = json.loads(
                (source_path / f"{text_path.stem}.json").read_text(encoding="utf-8")
            )
            entities = entities_from_json(values)
            before = [tuple(entity.assertions) for entity in entities]
            attach_assertions(entities, text)
            after = [tuple(entity.assertions) for entity in entities]
            if before != after:
                changed_records += 1
                changed_assertions += sum(a != b for a, b in zip(before, after))
            # No candidate resolver here by design.
            validate_entities(entities, text)
            counts.update(entity.type for entity in entities)
            (output_path / f"{text_path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in entities],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": text_path.stem, "error": str(exc)})
            (output_path / f"{text_path.stem}.json").write_text("[]\n", encoding="utf-8")
    report = {
        "records": len(records),
        "entity_counts": dict(counts),
        "changed_records": changed_records,
        "changed_assertions": changed_assertions,
        "errors": errors,
        "source": str(source_path),
        "output": str(output_path),
        "preserved_fields": ["text", "type", "position", "candidates"],
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
