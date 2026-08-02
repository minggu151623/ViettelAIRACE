"""Pre-result decomposition of H44 into H23-seen and H23-novel families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .exposure_concentration import _canonical_change, sha256, summarize, write_report


H23_CANDIDATE_DELTA = 0.3441
H23_CHANGED_ROWS = 144


def _keys(changes: list[dict[str, Any]]) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    canonical = [_canonical_change(change) for change in changes]
    return (
        {row[2] for row in canonical},
        {row[3] for row in canonical},
        {(row[1], row[3]) for row in canonical},
    )


def _stratum_summary(changes: list[dict[str, Any]], total_rows: int, total_families: int) -> dict[str, Any]:
    result = summarize(changes)
    result["row_share_of_h44"] = round(result["changed_rows"] / total_rows, 6)
    result["family_share_of_h44"] = round(result["unique_parent_families"] / total_families, 6)
    candidate_delta = result["changed_rows"] * H23_CANDIDATE_DELTA / H23_CHANGED_ROWS
    result["full_h23_per_row_yield_candidate_delta"] = round(candidate_delta, 10)
    result["full_h23_per_row_yield_total_score_delta"] = round(0.4 * candidate_delta, 10)
    return result


def family_novelty_decomposition(
    h23: dict[str, Any], h44: dict[str, Any], h53: dict[str, Any]
) -> dict[str, Any]:
    h23_changes, h44_changes = h23["changes"], h44["changes"]
    h23_parents, h23_specifics, h23_lexical = _keys(h23_changes)
    h44_parents, h44_specifics, h44_lexical = _keys(h44_changes)
    seen_changes, novel_changes = [], []
    for change in h44_changes:
        parent = _canonical_change(change)[2]
        (seen_changes if parent in h23_parents else novel_changes).append(change)
    total_rows, total_families = len(h44_changes), len(h44_parents)
    strata = {
        "h23_seen_family": _stratum_summary(seen_changes, total_rows, total_families),
        "h23_novel_family": _stratum_summary(novel_changes, total_rows, total_families),
    }
    seen = strata["h23_seen_family"]
    novel = strata["h23_novel_family"]
    h53_overlap = h53["cross_experiment"]["parent_family_overlap"]
    checks = {
        "strata_disjoint_cover_611": len(seen_changes) + len(novel_changes) == 611,
        "seen_parent_count_equals_h53_overlap_28": seen["unique_parent_families"] == h53_overlap == 28,
        "zero_specific_code_overlap": not (h23_specifics & h44_specifics),
        "zero_normalized_lexical_unit_overlap": not (h23_lexical & h44_lexical),
    }
    novel_dominant = novel["row_share_of_h44"] >= 0.70 and novel["family_share_of_h44"] >= 0.70
    seen_material = seen["changed_rows"] >= 100 and seen["unique_parent_families"] >= 20
    return {
        "hypothesis": "H54_h44_family_novelty_decomposition",
        "strata": strata,
        "cross_checks": checks,
        "gates": {
            "novel_family_dominant": novel_dominant,
            "seen_family_subgroup_material": seen_material,
            "reproducibility": True,
        },
        "interpretation": "cross_family_extrapolation" if novel_dominant else "substantial_within_family_extension",
        "decision": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h23", type=Path, required=True)
    parser.add_argument("--h44", type=Path, required=True)
    parser.add_argument("--h53", type=Path, required=True)
    parser.add_argument("--h44-zip", type=Path, required=True)
    parser.add_argument("--expected-h44-zip-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual_hash = sha256(args.h44_zip)
    if actual_hash != args.expected_h44_zip_sha256:
        raise SystemExit(f"H44 ZIP hash mismatch: {actual_hash}")
    inputs = [json.loads(path.read_text()) for path in (args.h23, args.h44, args.h53)]
    report = family_novelty_decomposition(*inputs)
    report["h44_zip_sha256"] = actual_hash
    if report["decision"] != "PASS":
        raise SystemExit(json.dumps(report["cross_checks"], sort_keys=True))
    write_report(report, args.output)


if __name__ == "__main__":
    main()
