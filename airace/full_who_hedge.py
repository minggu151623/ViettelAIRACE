"""Corpus-wide same-family WHO parent hedge for H44."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .package_output import package_output
from .schema import entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir
from .who_icd_rebuild import load_who_icd10


EXPECTED_SOURCE_ZIP_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _eligible_parent(value: dict[str, Any], who: dict[str, str]) -> str | None:
    if value.get("type") != "CHẨN_ĐOÁN":
        return None
    candidates = [str(code) for code in value.get("candidates", [])]
    if len(candidates) != 1:
        return None
    code = candidates[0]
    compact = re.sub(r"[^A-Z0-9]", "", code.upper())
    parent = code[:3]
    if len(compact) <= 3 or parent not in who or parent == code or parent in candidates:
        return None
    return parent


def build_full_who_hedge(
    *,
    input_dir: str | Path,
    source_dir: str | Path,
    source_zip: str | Path,
    output_dir: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    if _sha256(Path(source_zip)) != EXPECTED_SOURCE_ZIP_SHA256:
        raise ValueError("frozen H38 source ZIP hash mismatch")
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    who = load_who_icd10()
    changes: list[dict[str, Any]] = []
    affected_records: set[str] = set()
    entity_count = 0
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        record_id = input_path.stem
        raw = input_path.read_text(encoding="utf-8")
        source_rows = json.loads((source / f"{record_id}.json").read_text(encoding="utf-8"))
        output_rows = json.loads(json.dumps(source_rows, ensure_ascii=False))
        entity_count += len(output_rows)
        for index, (before, after) in enumerate(zip(source_rows, output_rows, strict=True)):
            parent = _eligible_parent(before, who)
            if parent is not None:
                specific = str(before["candidates"][0])
                after["candidates"] = [parent, specific]
                affected_records.add(record_id)
                changes.append(
                    {
                        "record_id": record_id,
                        "entity_index": index,
                        "text": before["text"],
                        "position": before["position"],
                        "before": [specific],
                        "after": [parent, specific],
                        "parent_title": who[parent],
                    }
                )
            frozen_before = {k: v for k, v in before.items() if k != "candidates"}
            frozen_after = {k: v for k, v in after.items() if k != "candidates"}
            if frozen_before != frozen_after:
                raise ValueError("non-candidate field changed")
            if before.get("type") == "THUỐC" and before.get("candidates", []) != after.get("candidates", []):
                raise ValueError("drug candidate changed")
        entities = entities_from_json(output_rows)
        validate_entities(entities, raw)
        (output / f"{record_id}.json").write_text(
            dumps_btc(entity.to_dict() for entity in entities), encoding="utf-8"
        )

    validation = validate_output_dir(inputs, output, "raw")
    gates = {
        "exactly_611_rows": len(changes) == 611,
        "exactly_97_records": len(affected_records) == 97,
        "all_3226_entities": entity_count == 3226,
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
        "all_changes_parent_specific": all(
            row["after"] == [row["before"][0][:3], row["before"][0]] for row in changes
        ),
    }
    report = {
        "hypothesis": "H44_full_who_family_hedge",
        "source_zip_sha256": _sha256(Path(source_zip)),
        "changed_rows": len(changes),
        "affected_records": len(affected_records),
        "entities": entity_count,
        "validation": validation,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "changes": changes,
    }
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["decision"] != "PASS":
        raise ValueError(json.dumps(gates))
    return report


def build_and_package_full_who_hedge(
    *,
    output_dir: str | Path = "turn2/output_v12_full_who_family_hedge",
    repeat_dir: str | Path = "turn2/output_v12_full_who_family_hedge_repeat",
    zip_path: str | Path = "turn2/output_v12_full_who_family_hedge.zip",
    repeat_zip_path: str | Path = "turn2/output_v12_full_who_family_hedge_repeat.zip",
    report_path: str | Path = "experiments/H44_full_who_family_hedge/results/build_report.json",
) -> dict[str, Any]:
    first = build_full_who_hedge(
        input_dir="turn2/input", source_dir="turn2/output_v10_multiview_consensus",
        source_zip="turn2/output_v10_multiview_consensus.zip", output_dir=output_dir,
        report_path=report_path,
    )
    second = build_full_who_hedge(
        input_dir="turn2/input", source_dir="turn2/output_v10_multiview_consensus",
        source_zip="turn2/output_v10_multiview_consensus.zip", output_dir=repeat_dir,
        report_path=Path(report_path).with_name("repeat_report.json"),
    )
    package_output(output_dir, zip_path, "turn2/input", "raw")
    package_output(repeat_dir, repeat_zip_path, "turn2/input", "raw")
    first_hash, second_hash = _sha256(Path(zip_path)), _sha256(Path(repeat_zip_path))
    if first_hash != second_hash:
        Path(zip_path).unlink(missing_ok=True)
        raise ValueError("repeat ZIP bytes differ")
    first["repeat_build_equal"] = first["changes"] == second["changes"]
    first["zip_sha256"] = first_hash
    first["gates"]["repeat_build_equal"] = first["repeat_build_equal"]
    first["gates"]["repeat_zip_equal"] = first_hash == second_hash
    first["decision"] = "PASS" if all(first["gates"].values()) else "FAIL"
    Path(report_path).write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return first
