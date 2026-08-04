from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .package_output import package_output
from .schema import entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
EXPECTED_H73_SHA256 = "e2f51f2b1a6a802dbc84d92bd82a1d3853bcf0edbb6654745617aef0e64c8e57"
TARGET_TYPES = {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(entity: dict[str, Any]) -> tuple[str, tuple[int, int], str]:
    return entity["type"], tuple(entity["position"]), entity["text"]


def _overlaps_same_type(candidate: dict[str, Any], entities: list[dict[str, Any]]) -> bool:
    start, end = candidate["position"]
    return any(
        entity["type"] == candidate["type"]
        and max(start, entity["position"][0]) < min(end, entity["position"][1])
        for entity in entities
    )


def select_disjoint_additions(
    baseline: list[dict[str, Any]], challenger: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline_keys = {_identity(entity) for entity in baseline}
    return [
        entity
        for entity in challenger
        if entity["type"] in TARGET_TYPES
        and _identity(entity) not in baseline_keys
        and not _overlaps_same_type(entity, baseline)
    ]


def build_additive_consensus_rescue(
    input_dir: str | Path,
    h69_dir: str | Path,
    h73_dir: str | Path,
    output_dir: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs, h69, h73 = Path(input_dir), Path(h69_dir), Path(h73_dir)
    output, target_zip, report_target = Path(output_dir), Path(zip_path), Path(report_path)
    if sha256(h69.with_suffix(".zip")) != EXPECTED_H69_SHA256:
        raise ValueError("H69 SHA-256 mismatch")
    if sha256(h73.with_suffix(".zip")) != EXPECTED_H73_SHA256:
        raise ValueError("H73 SHA-256 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")

    additions: list[dict[str, Any]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for text_path in records:
        record = int(text_path.stem)
        raw = text_path.read_text(encoding="utf-8")
        baseline = json.loads((h69 / f"{record}.json").read_text(encoding="utf-8"))
        challenger = json.loads((h73 / f"{record}.json").read_text(encoding="utf-8"))
        selected = select_disjoint_additions(baseline, challenger)
        for entity in selected:
            additions.append({"record": record, **entity})
        transformed = baseline + selected
        transformed.sort(
            key=lambda entity: (
                entity["position"][0],
                entity["position"][1],
                entity["type"],
                entity["text"],
            )
        )
        # Every baseline dictionary must survive byte-equivalent as an object.
        remaining = list(transformed)
        for entity in baseline:
            remaining.remove(entity)
        if sorted(remaining, key=_identity) != sorted(selected, key=_identity):
            raise AssertionError("H69 entity preservation failed")
        validate_entities(entities_from_json(transformed), raw)
        (output / f"{record}.json").write_text(dumps_btc(transformed), encoding="utf-8")

    changed_records = len({row["record"] for row in additions})
    additions_by_type = dict(sorted(Counter(row["type"] for row in additions).items()))
    validation = validate_output_dir(inputs, output, position_mode="raw")
    gates = {
        "exact_additions_79": len(additions) == 79,
        "exact_changed_records_34": changed_records == 34,
        "additions_by_type_exact": additions_by_type
        == {"CHẨN_ĐOÁN": 31, "TRIỆU_CHỨNG": 48},
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H76 promotion gates failed: {gates}")

    package_output(output, target_zip, inputs, position_mode="raw")
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs, position_mode="raw")
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    repeat_zip.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")

    report = {
        "hypothesis": "H76_additive_consensus_rescue",
        "status": "PASS_HIGH_VARIANCE_FINAL_SLOT_AWAITING_USER_SUBMISSION",
        "zip": str(target_zip),
        "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "additions": len(additions),
        "changed_records": changed_records,
        "additions_by_type": additions_by_type,
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation,
        "changes": additions,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
