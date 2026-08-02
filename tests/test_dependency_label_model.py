import numpy as np
import pytest

from airace.dependency_label_model import DependencyAwareLabelModel, synthetic_correlated_noise


def test_label_model_rejects_invalid_vote():
    model = DependencyAwareLabelModel(2)
    with pytest.raises(ValueError):
        model.fit(np.array([[0, 2]]))


def test_anchors_are_preserved():
    votes = np.array([[0, 0, 1], [1, 1, 0], [0, 1, 0]])
    anchors = np.array([1, -1, 0])
    result = DependencyAwareLabelModel(2, max_iter=10).fit(votes, anchors)
    assert result.posterior[0].tolist() == [0.0, 1.0]
    assert result.posterior[2].tolist() == [1.0, 0.0]


def test_preregistered_correlated_noise_gate():
    report = synthetic_correlated_noise()
    assert report["converged"]
    assert report["gate_gain_at_least_0_05"]
