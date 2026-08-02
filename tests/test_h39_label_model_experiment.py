import numpy as np

from airace.h39_label_model_experiment import ABSTAIN, combine_family_votes, majority_probabilities


def test_combine_family_votes_abstains_on_conflict():
    votes = np.array([[1, 1], [1, 2], [ABSTAIN, 2], [ABSTAIN, ABSTAIN]])
    assert combine_family_votes(votes, (0, 1)).tolist() == [1, ABSTAIN, 2, ABSTAIN]


def test_majority_probabilities_are_smoothed_and_normalized():
    votes = np.array([[1, 1, 2], [ABSTAIN, ABSTAIN, ABSTAIN]])
    probabilities = majority_probabilities(votes, [(0, 1), (2,)])
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert probabilities[0, 1] == probabilities[0, 2]
