"""Pre-result exposure calibration for the H44 WHO-family hedge."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


H23_CANDIDATE_DELTA = 0.3441
H23_ROWS = 144
H44_ROWS = 611
PRACTICAL_GATE = 0.02
STRONG_GATE = 0.50
CANDIDATE_WEIGHT = 0.4


def _h23_key(change: dict[str, Any]) -> tuple[str, tuple[int, int], str]:
    return (
        str(change["record"]),
        tuple(int(value) for value in change["position"]),
        str(change["new_candidates"][-1]),
    )


def _h44_key(change: dict[str, Any]) -> tuple[str, tuple[int, int], str]:
    return (
        str(change["record_id"]),
        tuple(int(value) for value in change["position"]),
        str(change["after"][-1]),
    )


def transfer_calibration(
    h23_report: dict[str, Any], h44_report: dict[str, Any]
) -> dict[str, Any]:
    h23 = {_h23_key(row) for row in h23_report["changes"]}
    h44 = {_h44_key(row) for row in h44_report["changes"]}
    if len(h23) != H23_ROWS or len(h44) != H44_ROWS:
        raise ValueError("frozen changed-row census mismatch")
    per_row = H23_CANDIDATE_DELTA / H23_ROWS
    full_candidate = per_row * H44_ROWS
    return {
        "hypothesis": "H52_h44_transfer_calibration",
        "identity_key": ["record_id", "exact_position", "preserved_specific_code"],
        "lineage": {
            "h23_rows": len(h23),
            "h44_rows": len(h44),
            "exact_overlap_rows": len(h23 & h44),
            "disjoint_h44_rows": len(h44 - h23),
            "union_rows": len(h23 | h44),
        },
        "h23_external_yield": {
            "candidate_delta": H23_CANDIDATE_DELTA,
            "candidate_delta_per_changed_row": per_row,
        },
        "h44_linear_transfer_forecast": {
            "candidate_delta_at_100_percent_h23_per_row_yield": full_candidate,
            "total_score_delta_at_100_percent_h23_per_row_yield": CANDIDATE_WEIGHT * full_candidate,
            "forecast_score_from_h38_39_2813": 39.2813 + CANDIDATE_WEIGHT * full_candidate,
        },
        "locked_gate_calibration": {
            "practical_candidate_delta": PRACTICAL_GATE,
            "practical_gate_equivalent_h23_yield_ratio": PRACTICAL_GATE / full_candidate,
            "strong_candidate_delta": STRONG_GATE,
            "strong_gate_equivalent_h23_yield_ratio": STRONG_GATE / full_candidate,
        },
        "decision_tree_correction": {
            "incorrect_additional_row_count": 467,
            "correct_additional_row_count": len(h44 - h23),
            "correct_total_parent_hedge_interventions_across_h23_h44": len(h23 | h44),
        },
        "interpretation": "EXPOSURE_CALIBRATION_NOT_GOLD_PREVALENCE_OR_SCORE_GUARANTEE",
        "artifact_policy": "H44_UNCHANGED_NO_SECOND_ARTIFACT",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    output = dict(report)
    output["content_sha256_before_hash_field"] = hashlib.sha256(canonical.encode()).hexdigest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h23", required=True)
    parser.add_argument("--h44", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    h23 = json.loads(Path(args.h23).read_text())
    h44 = json.loads(Path(args.h44).read_text())
    write_report(transfer_calibration(h23, h44), args.output)


if __name__ == "__main__":
    main()
