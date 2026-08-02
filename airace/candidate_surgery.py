"""Fail-closed candidate-only contradiction surgery for H43."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .normalize import normalize_key
from .package_output import package_output
from .schema import entities_from_json
from .turn2_llm_rebuild import _FORCE_KEEP, _SAFE_REPLACEMENTS
from .validator import validate_entities


EXPECTED_SOURCE_ZIP_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"
EXPECTED_PRIOR_REVIEW_SHA256 = "ead9269954882395b5d841e2cf40a605e704767cebd2b8f0474989e34c19232b"
EXPECTED_REVIEW_UNITS = 621


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tuple(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row["type"]), normalize_key(str(row["mention"])), str(row["candidate"])


def _safe_controls() -> set[tuple[str, str, str]]:
    controls = set(_FORCE_KEEP)
    for (kind, mention), codes in _SAFE_REPLACEMENTS.items():
        controls.update((kind, mention, str(code)) for code in codes)
    return controls


def _drop_keys(review: dict[str, Any]) -> tuple[set[tuple[str, str, str]], dict[str, Any]]:
    entries = review.get("entries", [])
    if len(entries) != EXPECTED_REVIEW_UNITS:
        raise ValueError(f"expected {EXPECTED_REVIEW_UNITS} review units, found {len(entries)}")
    keys = [_tuple(row) for row in entries]
    if len(set(keys)) != EXPECTED_REVIEW_UNITS:
        raise ValueError("review contains duplicate type/mention/code units")
    valid_actions = {"KEEP", "DROP"}
    agreed = 0
    proposed: set[tuple[str, str, str]] = set()
    for row in entries:
        left = row.get("pass_1", {})
        right = row.get("pass_2", {})
        if left.get("action") not in valid_actions or right.get("action") not in valid_actions:
            raise ValueError("review has an invalid or missing action")
        agreed += left["action"] == right["action"]
        if row.get("decision") != (
            "DROP"
            if left["action"] == right["action"] == "DROP"
            and min(float(left.get("confidence", 0)), float(right.get("confidence", 0))) >= 0.80
            else "KEEP"
        ):
            raise ValueError("review decision does not match frozen dual-pass rule")
        if row.get("decision") == "DROP":
            unknown = row.get("title") == "UNKNOWN_LOCAL_DESCRIPTION"
            obvious_false_drug = (
                row["type"] == "THUỐC" and normalize_key(row["mention"]) == normalize_key("hiến máu")
            )
            if not unknown or obvious_false_drug:
                proposed.add(_tuple(row))
    agreement = agreed / len(entries)
    return proposed - _safe_controls(), {
        "review_units": len(entries),
        "exact_action_agreement": agreement,
        "dual_drop_units_before_controls": sum(row.get("decision") == "DROP" for row in entries),
        "eligible_drop_units_after_controls": len(proposed - _safe_controls()),
    }


def build_candidate_surgery(
    *,
    input_dir: str | Path,
    source_dir: str | Path,
    source_zip: str | Path,
    review_path: str | Path,
    prior_review_path: str | Path,
    output_dir: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs = Path(input_dir)
    source = Path(source_dir)
    output = Path(output_dir)
    review_file = Path(review_path)
    prior_file = Path(prior_review_path)
    if _sha256(Path(source_zip)) != EXPECTED_SOURCE_ZIP_SHA256:
        raise ValueError("frozen H38 source ZIP hash mismatch")
    if _sha256(prior_file) != EXPECTED_PRIOR_REVIEW_SHA256:
        raise ValueError("frozen prior-review hash mismatch")
    review = json.loads(review_file.read_text(encoding="utf-8"))
    drops, review_stats = _drop_keys(review)
    prior = json.loads(prior_file.read_text(encoding="utf-8"))
    hazards = {
        _tuple(row)
        for row in prior.get("entries", [])
        if row.get("decision") == "DROP" and row.get("title") != "UNKNOWN_LOCAL_DESCRIPTION"
    }

    output.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    removed_rows: list[dict[str, Any]] = []
    safe = _safe_controls()
    observed_safe_before: Counter[tuple[str, str, str]] = Counter()
    observed_safe_after: Counter[tuple[str, str, str]] = Counter()
    hazard_uses_before = hazard_uses_removed = 0
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        record_id = input_path.stem
        raw = input_path.read_text(encoding="utf-8")
        source_rows = json.loads((source / f"{record_id}.json").read_text(encoding="utf-8"))
        output_rows = json.loads(json.dumps(source_rows, ensure_ascii=False))
        for source_row, output_row in zip(source_rows, output_rows, strict=True):
            before = [str(code) for code in source_row.get("candidates", [])]
            for code in before:
                key = (source_row["type"], normalize_key(source_row["text"]), code)
                observed_safe_before[key] += key in safe
                hazard_uses_before += key in hazards
            after: list[str] = []
            for code in before:
                key = (source_row["type"], normalize_key(source_row["text"]), code)
                if key in drops:
                    stats["candidate_uses_removed"] += 1
                    hazard_uses_removed += key in hazards
                    removed_rows.append(
                        {
                            "record_id": record_id,
                            "text": source_row["text"],
                            "type": source_row["type"],
                            "candidate": code,
                        }
                    )
                else:
                    after.append(code)
                    observed_safe_after[key] += key in safe
            if "candidates" in output_row:
                output_row["candidates"] = after
            source_without = {k: v for k, v in source_row.items() if k != "candidates"}
            output_without = {k: v for k, v in output_row.items() if k != "candidates"}
            if source_without != output_without or not set(after).issubset(before):
                raise ValueError("candidate-only invariant failed")
        entities = entities_from_json(output_rows)
        validate_entities(entities, raw)
        stats["records"] += 1
        stats["entities"] += len(output_rows)
        (output / f"{record_id}.json").write_text(
            json.dumps(output_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if observed_safe_after != observed_safe_before:
        raise ValueError("curated safe-alias positive control was removed")
    package = package_output(output, zip_path, inputs, "raw")
    removal_count = stats["candidate_uses_removed"]
    hazard_rate = hazard_uses_removed / max(1, hazard_uses_before)
    gates = {
        "all_review_units_complete": review_stats["review_units"] == EXPECTED_REVIEW_UNITS,
        "review_agreement_at_least_0_90": review_stats["exact_action_agreement"] >= 0.90,
        "safe_alias_controls_retained": observed_safe_after == observed_safe_before,
        "hazard_removal_rate_at_least_0_80": hazard_rate >= 0.80,
        "candidate_removals_between_50_and_350": 50 <= removal_count <= 350,
        "zero_candidate_additions": True,
        "all_entities_candidate_only": stats["entities"] == 3226,
        "all_records_validate": stats["records"] == 100,
    }
    report = {
        "hypothesis": "H43_candidate_contradiction_surgery",
        "source_zip_sha256": _sha256(Path(source_zip)),
        "review_sha256": _sha256(review_file),
        "review": review_stats,
        "stats": dict(stats),
        "positive_control_uses": sum(observed_safe_before.values()),
        "registered_hazard_uses": hazard_uses_before,
        "registered_hazard_uses_removed": hazard_uses_removed,
        "registered_hazard_removal_rate": hazard_rate,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "zip": package,
        "zip_sha256": _sha256(Path(zip_path)),
        "removed": removed_rows,
    }
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["decision"] != "PASS":
        Path(zip_path).unlink(missing_ok=True)
    return report
