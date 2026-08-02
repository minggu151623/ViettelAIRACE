from pathlib import Path

import numpy as np

from airace.proposal_pu import PURow, _greedy_additions, _jaccard, _prf, structured_features


def _row(start: int, end: int, score_sources=("vietmed_ner",), *, kind="TRIỆU_CHỨNG") -> PURow:
    return PURow(
        record=1,
        text="đau đầu",
        type=kind,
        position=(start, end),
        confidences={source: 0.8 for source in score_sources},
        assertions={},
        context="Ngữ cảnh ⟦đau đầu⟧",
        section="triệu chứng",
    )


def test_structured_features_are_fixed_width_and_finite():
    values = structured_features([_row(2, 9), _row(12, 19, ("bami_v15", "bami_v3"), kind="THUỐC")])
    assert values.shape[0] == 2
    assert values.shape[1] > 20
    assert np.isfinite(values).all()


def test_greedy_additions_resolves_overlapping_candidates_by_score():
    rows = [_row(0, 8), _row(4, 12), _row(15, 20)]
    selected = _greedy_additions(rows, np.asarray([0.91, 0.96, 0.90]), {1}, 0.90)
    assert selected[1] == [1, 2]


def test_prf_and_empty_jaccard_conventions():
    assert _prf({(0, 1, "A")}, {(0, 1, "A"), (2, 3, "A")})["f1"] == 2 / 3
    assert _jaccard([], []) == 1.0
