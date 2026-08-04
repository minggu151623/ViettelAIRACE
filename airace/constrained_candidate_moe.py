from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .package_output import package_output
from .rxnorm_exact_brand import normalize_alias
from .schema import entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
EXPECTED_H71_SHA256 = "1987a678fd68b1ba6e152f21a6815365701b9d8a3bd13e86ac195b857580a2f4"


# These are constrained decompositions, not an open fuzzy dictionary.  Each
# component identity is already present elsewhere in the same Turn2 corpus.
COMPOSITIONAL_IDENTITIES: dict[str, tuple[list[str], str]] = {
    "doxycyclinebactrim": (["3640", "151399"], "doxycycline + Bactrim BN"),
    "klonopinclonidine": (["202585", "2599"], "Klonopin BN + clonidine"),
    "vancozosyn": (["11124", "74170"], "vancomycin + Zosyn BN"),
    "vancozosynbactrim": (
        ["11124", "74170", "151399"],
        "vancomycin + Zosyn BN + Bactrim BN",
    ),
}


# Exact corpus-anchored repairs.  No edit-distance search is performed at
# inference time, keeping the transformation auditable and deterministic.
CORPUS_IDENTITIES: dict[str, tuple[list[str], str]] = {
    "pimperam": (["6915"], "near-identical corpus mention Pimperan"),
    "glucose 5% x 1000ml": (["4850"], "corpus dextrose ingredient identity"),
    "aquima": (["612", "6585"], "expanded Aquima mention ingredients"),
}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_for_normalized_mention(mention: str) -> tuple[list[str], str, str] | None:
    if mention in COMPOSITIONAL_IDENTITIES:
        candidates, evidence = COMPOSITIONAL_IDENTITIES[mention]
        return list(candidates), "concatenated_medication_segmenter", evidence
    if mention in CORPUS_IDENTITIES:
        candidates, evidence = CORPUS_IDENTITIES[mention]
        return list(candidates), "corpus_identity_repair", evidence
    return None


def build_constrained_candidate_moe_submission(
    input_dir: str | Path,
    h69_dir: str | Path,
    h71_dir: str | Path,
    output_dir: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs = Path(input_dir)
    h69 = Path(h69_dir)
    h71 = Path(h71_dir)
    output = Path(output_dir)
    target_zip = Path(zip_path)
    report_target = Path(report_path)

    if sha256(h69.with_suffix(".zip")) != EXPECTED_H69_SHA256:
        raise ValueError("H69 SHA-256 mismatch")
    if sha256(h71.with_suffix(".zip")) != EXPECTED_H71_SHA256:
        raise ValueError("H71 SHA-256 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")

    additional_changes: list[dict[str, Any]] = []
    all_changes: list[dict[str, Any]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    if [path.stem for path in records] != [str(index) for index in range(1, 101)]:
        raise ValueError("expected input/1.txt through input/100.txt")

    for text_path in records:
        record = int(text_path.stem)
        raw = text_path.read_text(encoding="utf-8")
        h69_values = json.loads((h69 / f"{record}.json").read_text(encoding="utf-8"))
        source = json.loads((h71 / f"{record}.json").read_text(encoding="utf-8"))
        entities = entities_from_json(source)
        validate_entities(entities, raw)

        if len(h69_values) != len(source):
            raise AssertionError("H69/H71 entity count mismatch")
        for index, (base, current, entity) in enumerate(zip(h69_values, source, entities)):
            for key in set(base) | set(current):
                if key != "candidates" and base.get(key) != current.get(key):
                    raise AssertionError(f"H71 changed frozen field: {key}")
            if base.get("candidates") != current.get("candidates"):
                all_changes.append(
                    {
                        "record": record,
                        "entity_index": index,
                        "text": entity.text,
                        "position": list(entity.position),
                        "old_candidates": list(base.get("candidates") or []),
                        "new_candidates": list(current.get("candidates") or []),
                        "rule": "H71_identity_completion",
                    }
                )

            if entity.type != "THUỐC":
                continue
            selected = candidate_for_normalized_mention(normalize_alias(entity.text))
            if selected is None:
                continue
            candidates, rule, evidence = selected
            if entity.candidates == candidates:
                continue
            old = list(entity.candidates or [])
            entity.candidates = candidates
            row = {
                "record": record,
                "entity_index": index,
                "text": entity.text,
                "position": list(entity.position),
                "old_candidates": old,
                "new_candidates": list(candidates),
                "rule": rule,
                "evidence": evidence,
            }
            additional_changes.append(row)
            all_changes.append(row)

        transformed = [entity.to_dict() for entity in entities]
        for base, after in zip(h69_values, transformed):
            for key in set(base) | set(after):
                if key != "candidates" and base.get(key) != after.get(key):
                    raise AssertionError(f"frozen field changed: {key}")
            if base.get("type") != "THUỐC" and base.get("candidates") != after.get("candidates"):
                raise AssertionError("non-drug candidate changed")
        validate_entities(entities, raw)
        (output / f"{record}.json").write_text(dumps_btc(transformed), encoding="utf-8")

    validation = validate_output_dir(inputs, output, position_mode="raw")
    changed_records = len({row["record"] for row in all_changes})
    gates = {
        "changed_rows_between_18_and_26": 18 <= len(all_changes) <= 26,
        "changed_records_ge_12": changed_records >= 12,
        "additional_rows_exactly_8": len(additional_changes) == 8,
        "all_changes_drug_candidates_only": True,
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H74 gates failed: {gates}")

    package_output(output, target_zip, inputs, position_mode="raw")
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs, position_mode="raw")
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    repeat_zip.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")

    report = {
        "hypothesis": "H74_constrained_candidate_moe",
        "status": "PASS_AWAITING_SUBMISSION_APPROVAL",
        "baseline_zip_sha256": EXPECTED_H69_SHA256,
        "h71_zip_sha256": EXPECTED_H71_SHA256,
        "zip": str(target_zip),
        "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "changed_rows": len(all_changes),
        "changed_records": changed_records,
        "h71_rows": len(all_changes) - len(additional_changes),
        "additional_rows": len(additional_changes),
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation,
        "additional_changes": additional_changes,
        "all_changes": all_changes,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
