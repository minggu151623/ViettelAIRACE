from airace.crossfit_voter import make_folds


def test_folds_cover_every_record_once_and_are_deterministic():
    first = make_folds()
    second = make_folds()
    assert first == second
    assert all(len(fold) == 20 for fold in first)
    assert sorted(record for fold in first for record in fold) == list(range(1, 101))


def test_training_validation_and_inference_are_disjoint():
    folds = make_folds()
    for index, inference in enumerate(folds):
        validation = folds[(index + 1) % 5]
        training = set(range(1, 101)) - set(inference) - set(validation)
        assert len(training) == 60
        assert not (set(inference) & set(validation))
        assert not (set(inference) & training)
        assert not (set(validation) & training)
