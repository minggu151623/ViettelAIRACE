from airace.phrase_verifier import _candidate_digest, _split_gates


def test_candidate_digest_does_not_include_pseudo_label():
    row = {"id": 1, "text": "đau đầu", "pseudo_positive": True}
    changed = {**row, "pseudo_positive": False}
    assert _candidate_digest([row]) == _candidate_digest([changed])


def test_split_gates_use_registered_thresholds():
    result = {
        "true_addition_retention": 0.8,
        "pseudo_precision_gain": 0.15,
        "baseline": {"f1": 0.50},
        "with_additions": {"f1": 0.53},
    }
    assert all(_split_gates(result).values())
