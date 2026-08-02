import json

import pytest

from airace.candidate_surgery import EXPECTED_REVIEW_UNITS, _drop_keys


def _entry(index: int, left: str = "KEEP", right: str = "KEEP", confidence: float = 0.9):
    return {
        "type": "CHẨN_ĐOÁN",
        "mention": f"bệnh {index}",
        "candidate": f"X{index}",
        "title": "known",
        "pass_1": {"action": left, "confidence": confidence},
        "pass_2": {"action": right, "confidence": confidence},
        "decision": "DROP" if left == right == "DROP" and confidence >= 0.8 else "KEEP",
    }


def test_drop_keys_requires_complete_dual_review():
    with pytest.raises(ValueError, match="expected"):
        _drop_keys({"entries": [_entry(1)]})


def test_drop_keys_enforces_frozen_rule_and_reports_agreement():
    entries = [_entry(index) for index in range(EXPECTED_REVIEW_UNITS)]
    entries[0] = _entry(0, "DROP", "DROP")
    drops, report = _drop_keys({"entries": entries})
    assert ("CHẨN_ĐOÁN", "benh 0", "X0") in drops
    assert report["review_units"] == EXPECTED_REVIEW_UNITS
    assert report["exact_action_agreement"] == 1.0


def test_drop_keys_rejects_tampered_decision():
    entries = [_entry(index) for index in range(EXPECTED_REVIEW_UNITS)]
    entries[0]["decision"] = "DROP"
    with pytest.raises(ValueError, match="frozen dual-pass rule"):
        _drop_keys({"entries": entries})
