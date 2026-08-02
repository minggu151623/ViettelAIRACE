import numpy as np

from airace.ontology_dense import rank_type_restricted


def test_dense_ranker_respects_ontology_type() -> None:
    concepts = np.asarray([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    concepts /= np.linalg.norm(concepts, axis=1, keepdims=True)
    queries = np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    ranked = rank_type_restricted(
        queries,
        ["CHẨN_ĐOÁN", "THUỐC"],
        concepts,
        ["ICD:A", "RX:1", "RX:2"],
        top_k=2,
    )
    assert ranked[0] == ["ICD:A"]
    assert ranked[1][0] == "RX:1"

