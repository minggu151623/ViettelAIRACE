"""Fail-closed recorder for the pending H44 external result."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

from .exposure_concentration import sha256, write_report


DECISIONS = {
    "validation_anomaly": "STOP_ATTRIBUTION",
    "strong_positive": "PROMOTE_H44",
    "small_positive": "PROMOTE_H44_WEAK",
    "practical_null": "RETAIN_H38",
    "negative": "RETAIN_H38",
}


def _tree_hash(tree_path: Path) -> str:
    return hashlib.sha256(tree_path.read_bytes()).hexdigest()


def _branch_payload(tree: dict[str, Any], branch_id: str) -> dict[str, str]:
    branch = next(branch for branch in tree["branch_order"] if branch["id"] == branch_id)
    return {"interpretation": branch["interpretation"], "action": branch["action"]}


def classify_result(
    tree: dict[str, Any], *, submitted_zip_sha256: str, local_zip_sha256: str,
    score: float, wer_percent: float, j_assertion: float, j_candidates: float,
    decision_tree_sha256: str = "test-tree",
) -> dict[str, Any]:
    metrics = {
        "score": score,
        "wer_percent": wer_percent,
        "j_assertion": j_assertion,
        "j_candidates": j_candidates,
    }
    finite = all(isinstance(value, (int, float)) and math.isfinite(value) for value in metrics.values())
    baseline = tree["baseline_h38"]
    expected_hash = tree["artifact"]["sha256"]
    if finite:
        deltas = {key: round(metrics[key] - float(baseline[key]), 10) for key in metrics}
    else:
        deltas = {key: None for key in metrics}
    tolerance = tree["derived_checks"]
    checks = {
        "metrics_finite": finite,
        "submitted_zip_hash_matches": submitted_zip_sha256 == expected_hash,
        "local_zip_hash_matches": local_zip_sha256 == expected_hash,
        "wer_invariant": finite and abs(deltas["wer_percent"]) <= tolerance["invariant_display_tolerance"],
        "assertion_invariant": finite and abs(deltas["j_assertion"]) <= tolerance["invariant_display_tolerance"],
        "score_reconciles": finite and abs(
            deltas["score"] - 0.4 * deltas["j_candidates"]
        ) <= tolerance["score_reconciliation_tolerance"],
    }
    attributable = all(checks.values())
    if not attributable:
        branch_id = "validation_anomaly"
    else:
        candidate_delta, score_delta = deltas["j_candidates"], deltas["score"]
        strong = tolerance["strong_candidate_delta"]
        strong_score = tolerance["equivalent_strong_score_delta"]
        null = tolerance["practical_null_band"]
        if candidate_delta >= strong and score_delta >= strong_score:
            branch_id = "strong_positive"
        elif null < candidate_delta < strong:
            branch_id = "small_positive"
        elif abs(candidate_delta) <= null:
            branch_id = "practical_null"
        elif candidate_delta < -null:
            branch_id = "negative"
        else:
            branch_id = "validation_anomaly"
            checks["branch_coverage"] = False
            attributable = False
    payload = _branch_payload(tree, branch_id)
    return {
        "hypothesis": "H44_full_who_family_hedge",
        "submitted_zip_sha256": submitted_zip_sha256,
        "local_zip_sha256": local_zip_sha256,
        "decision_tree_sha256": decision_tree_sha256,
        "metrics": metrics,
        "baseline_h38": baseline,
        "deltas": deltas,
        "checks": checks,
        "attributable": attributable,
        "branch_id": branch_id,
        "decision": DECISIONS[branch_id],
        **payload,
        "pre_result_scope": {
            "breadth": tree["pre_result_concentration_calibration"]["interpretation"],
            "novelty": "cross_family_extrapolation"
            if tree["pre_result_family_novelty_decomposition"]["novel_family_dominant"]
            else "substantial_within_family_extension",
        },
    }


def readiness_matrix(tree: dict[str, Any], expected_hash: str, tree_hash: str) -> dict[str, Any]:
    baseline = tree["baseline_h38"]

    def case(name: str, candidate_delta: float = 0.0, score_delta: float = 0.0, **changes: Any) -> dict[str, Any]:
        values = {
            "submitted_zip_sha256": expected_hash,
            "local_zip_sha256": expected_hash,
            "score": baseline["score"] + score_delta,
            "wer_percent": baseline["wer_percent"],
            "j_assertion": baseline["j_assertion"],
            "j_candidates": baseline["j_candidates"] + candidate_delta,
            "decision_tree_sha256": tree_hash,
        }
        values.update(changes)
        result = classify_result(tree, **values)
        return {"case": name, "branch_id": result["branch_id"], "decision": result["decision"]}

    cases = [
        case("wrong_zip_hash", submitted_zip_sha256="wrong"),
        case("wer_movement", wer_percent=baseline["wer_percent"] + 0.0002),
        case("assertion_movement", j_assertion=baseline["j_assertion"] + 0.0002),
        case("score_reconciliation_failure", score_delta=0.01),
        case("strong_positive", 0.50, 0.20),
        case("small_positive", 0.10, 0.04),
        case("practical_null", 0.02, 0.008),
        case("negative", -0.10, -0.04),
    ]
    expected = [
        "validation_anomaly", "validation_anomaly", "validation_anomaly",
        "validation_anomaly", "strong_positive", "small_positive",
        "practical_null", "negative",
    ]
    return {
        "hypothesis": "H55_h44_external_result_recorder",
        "decision_tree_sha256": tree_hash,
        "h44_zip_sha256": expected_hash,
        "cases": cases,
        "all_registered_cases_pass": [case["branch_id"] for case in cases] == expected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-tree", type=Path, required=True)
    parser.add_argument("--h44-zip", type=Path, required=True)
    parser.add_argument("--submitted-zip-sha256")
    parser.add_argument("--score", type=float)
    parser.add_argument("--wer-percent", type=float)
    parser.add_argument("--j-assertion", type=float)
    parser.add_argument("--j-candidates", type=float)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tree = yaml.safe_load(args.decision_tree.read_text())
    local_hash, tree_hash = sha256(args.h44_zip), _tree_hash(args.decision_tree)
    if args.self_test:
        report = readiness_matrix(tree, tree["artifact"]["sha256"], tree_hash)
        if local_hash != tree["artifact"]["sha256"] or not report["all_registered_cases_pass"]:
            raise SystemExit("H55 readiness matrix failed")
        write_report(report, args.output)
        return
    required = [args.submitted_zip_sha256, args.score, args.wer_percent, args.j_assertion, args.j_candidates]
    if any(value is None for value in required):
        raise SystemExit("all submitted hash and metric arguments are required")
    report = classify_result(
        tree,
        submitted_zip_sha256=args.submitted_zip_sha256,
        local_zip_sha256=local_hash,
        score=args.score,
        wer_percent=args.wer_percent,
        j_assertion=args.j_assertion,
        j_candidates=args.j_candidates,
        decision_tree_sha256=tree_hash,
    )
    if not report["attributable"]:
        raise SystemExit(json.dumps(report, ensure_ascii=False, sort_keys=True))
    write_report(report, args.output)


if __name__ == "__main__":
    main()
