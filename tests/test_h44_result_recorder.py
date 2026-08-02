import math

import yaml

from airace.h44_result_recorder import classify_result, readiness_matrix


HASH = "abc"


def _tree() -> dict:
    return yaml.safe_load(
        """
artifact: {sha256: abc}
baseline_h38: {score: 39.2813, wer_percent: 56.1576, j_assertion: 47.3920, j_candidates: 29.7776}
derived_checks:
  invariant_display_tolerance: 0.0001
  score_reconciliation_tolerance: 0.0002
  strong_candidate_delta: 0.5
  equivalent_strong_score_delta: 0.2
  practical_null_band: 0.02
pre_result_concentration_calibration: {interpretation: family_only}
pre_result_family_novelty_decomposition: {novel_family_dominant: true}
branch_order:
  - {id: validation_anomaly, interpretation: anomaly, action: stop}
  - {id: strong_positive, interpretation: strong, action: promote}
  - {id: small_positive, interpretation: small, action: weak}
  - {id: practical_null, interpretation: null, action: retain}
  - {id: negative, interpretation: negative, action: reject}
"""
    )


def _classify(candidate_delta: float, score_delta: float, **overrides):
    values = dict(
        submitted_zip_sha256=HASH,
        local_zip_sha256=HASH,
        score=39.2813 + score_delta,
        wer_percent=56.1576,
        j_assertion=47.3920,
        j_candidates=29.7776 + candidate_delta,
    )
    values.update(overrides)
    return classify_result(_tree(), **values)


def test_all_registered_branch_cases() -> None:
    report = readiness_matrix(_tree(), HASH, "tree")
    assert report["all_registered_cases_pass"]


def test_strong_result_copies_frozen_semantics() -> None:
    result = _classify(0.5, 0.2)
    assert result["branch_id"] == "strong_positive"
    assert result["decision"] == "PROMOTE_H44"
    assert result["interpretation"] == "strong"
    assert result["pre_result_scope"] == {
        "breadth": "family_only",
        "novelty": "cross_family_extrapolation",
    }


def test_identity_and_formula_anomalies_stop_attribution() -> None:
    assert _classify(0.0, 0.0, submitted_zip_sha256="wrong")["branch_id"] == "validation_anomaly"
    assert _classify(0.0, 0.01)["branch_id"] == "validation_anomaly"


def test_nonfinite_metric_stops_attribution() -> None:
    result = _classify(0.0, 0.0, score=math.nan)
    assert result["decision"] == "STOP_ATTRIBUTION"
    assert not result["checks"]["metrics_finite"]
