import numpy as np

from airace.score_shape_cardinality import _select_actions, score_features


def test_score_features_are_fixed_width_and_finite() -> None:
    scores = np.linspace(0.9, 0.1, 10)
    identifiers = ["ICD:A10.1", "ICD:A10", *[f"ICD:B1{i}" for i in range(8)]]
    features = score_features(scores, identifiers)
    assert features.shape == (33,)
    assert np.isfinite(features).all()


def test_action_tie_breaks_to_smaller_prefix() -> None:
    predicted = np.asarray([[0.5, 0.5, 0.1], [0.1, 0.2, 0.2]])
    assert _select_actions(predicted).tolist() == [1, 2]
