import numpy as np

from airace.ontology_prototypes import build_train_prototypes, replace_seen_concepts


def test_prototypes_use_train_rows_only_and_normalize() -> None:
    rows = [
        {"fold": "train", "gold_concepts": ["ICD:A"]},
        {"fold": "train", "gold_concepts": ["ICD:A"]},
        {"fold": "dev", "gold_concepts": ["ICD:B"]},
    ]
    mentions = np.asarray([[1.0, 0.0], [0.0, 1.0], [9.0, 9.0]], dtype=np.float32)
    prototypes, counts = build_train_prototypes(rows, mentions, ["ICD:A", "ICD:B"])
    assert counts == {"ICD:A": 2}
    assert np.allclose(prototypes[0], np.asarray([2**-0.5, 2**-0.5]))
    assert np.allclose(prototypes[1], 0)


def test_replace_seen_concepts_preserves_unseen_canonical() -> None:
    canonical = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    prototypes = np.asarray([[0.0, 2.0], [0.0, 0.0]], dtype=np.float32)
    result = replace_seen_concepts(
        canonical, prototypes, {"ICD:A": 1}, ["ICD:A", "ICD:B"]
    )
    assert np.allclose(result, np.asarray([[0.0, 1.0], [0.0, 1.0]]))
