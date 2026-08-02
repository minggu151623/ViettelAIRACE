from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import Entity, entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir
from .who_icd_rebuild import load_who_icd10


FROZEN_FIELDS = ("text", "type", "position", "assertions")


def _freeze_view(value: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(json.dumps(value.get(key, []), ensure_ascii=False, sort_keys=True) for key in FROZEN_FIELDS)


def build_candidate_semantic_ablation(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    *,
    minimum_changes: int = 20,
) -> dict[str, Any]:
    """Add same-family WHO parents to singleton ICD-10-CM candidates.

    H23 intentionally leaves every non-candidate field and every drug mapping
    untouched. Multi-code diagnoses are quarantined because adding all parents
    would violate the preregistered two-candidate maximum.
    """

    inputs = Path(input_dir)
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    who = load_who_icd10()
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    changes: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for text_path in records:
        raw_text = text_path.read_text(encoding="utf-8")
        source_path = source / f"{text_path.stem}.json"
        values = json.loads(source_path.read_text(encoding="utf-8"))
        before = json.loads(json.dumps(values, ensure_ascii=False))

        for index, value in enumerate(values):
            if value.get("type") != "CHẨN_ĐOÁN":
                continue
            candidates = list(value.get("candidates") or [])
            eligible = [
                code
                for code in candidates
                if code not in who and code[:3] in who and code[:3] not in candidates
            ]
            if not eligible:
                continue
            if len(candidates) != 1 or len(eligible) != 1:
                quarantine.append(
                    {
                        "record": text_path.stem,
                        "entity_index": index,
                        "text": value["text"],
                        "position": value["position"],
                        "candidates": candidates,
                        "eligible_parents": sorted({code[:3] for code in eligible}),
                        "reason": "multi-code row would exceed the two-candidate limit",
                    }
                )
                continue

            specific = eligible[0]
            parent = specific[:3]
            value["candidates"] = [parent, specific]
            changes.append(
                {
                    "record": text_path.stem,
                    "entity_index": index,
                    "text": value["text"],
                    "position": value["position"],
                    "old_candidates": candidates,
                    "new_candidates": value["candidates"],
                    "reason": "same-family WHO parent hedge for ICD-10-CM-specific code",
                    "evidence": {
                        "parent": parent,
                        "who_2019_title": who[parent],
                        "specific_preserved": specific,
                    },
                }
            )

        if len(before) != len(values):
            raise ValueError(f"{source_path}: entity count changed")
        for index, (old, new) in enumerate(zip(before, values)):
            if _freeze_view(old) != _freeze_view(new):
                raise ValueError(f"{source_path}: frozen field changed at entity {index}")
            if old.get("type") == "THUỐC" and old.get("candidates", []) != new.get("candidates", []):
                raise ValueError(f"{source_path}: drug candidate changed at entity {index}")

        entities: list[Entity] = entities_from_json(values)
        validate_entities(entities, raw_text)
        rendered = dumps_btc(entity.to_dict() for entity in entities)
        (output / f"{text_path.stem}.json").write_text(rendered, encoding="utf-8")
        counts.update(entity.type for entity in entities)

    if len(changes) < minimum_changes:
        raise ValueError(f"only {len(changes)} changes; minimum is {minimum_changes}")
    validation = validate_output_dir(inputs, output)
    if not validation["ok"]:
        raise ValueError(json.dumps(validation, ensure_ascii=False))

    report: dict[str, Any] = {
        "hypothesis": "H23_candidate_only_semantic",
        "source": str(source),
        "output": str(output),
        "records": len(records),
        "changed_rows": len(changes),
        "quarantined_rows": len(quarantine),
        "changes": changes,
        "quarantine": quarantine,
        "entity_counts": dict(sorted(counts.items())),
        "frozen_fields": list(FROZEN_FIELDS),
        "drug_candidates_frozen": True,
        "validation": validation,
    }
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
