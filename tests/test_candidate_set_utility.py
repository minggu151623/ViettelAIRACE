from airace.candidate_set_utility import jaccard, paired_bootstrap, select_k


def test_jaccard_penalizes_extra_candidates() -> None:
    assert jaccard(["A"], ["A"]) == 1.0
    assert jaccard(["A", "B"], ["A"]) == 0.5
    assert jaccard(["B"], ["A"]) == 0.0


def test_select_k_uses_dev_utility_and_smaller_tie() -> None:
    rows = [
        {"top10": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"], "gold": ["A"]},
        {"top10": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"], "gold": ["B"]},
    ]
    assert select_k(rows) == 1


def test_paired_bootstrap_is_deterministic() -> None:
    baseline = [0.0, 0.5, 1.0]
    challenger = [0.5, 0.5, 1.0]
    first = paired_bootstrap(baseline, challenger, seed=7, resamples=100)
    second = paired_bootstrap(baseline, challenger, seed=7, resamples=100)
    assert first == second
    assert first["point_delta"] > 0
