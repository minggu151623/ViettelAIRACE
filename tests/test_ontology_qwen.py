import numpy as np

from airace.ontology_qwen import format_query, multilingual_retrieval_report


def test_query_uses_registered_instruction() -> None:
    query = format_query("suy tim")
    assert query.endswith("Query: suy tim")
    assert "English ICD-10 or RxNorm" in query


def test_multilingual_report_is_type_restricted() -> None:
    dataset = {
        "label_status": "weak",
        "rows": [
            {"id": 1, "fold": "test", "type": "CHẨN_ĐOÁN", "gold_concepts": ["ICD:A"]},
            {"id": 2, "fold": "test", "type": "THUỐC", "gold_concepts": ["RX:1"]},
        ],
    }
    ids = ["ICD:A", "ICD:B", "RX:1"]
    concepts = np.asarray([[1, 0], [0, 1], [1, 0]], dtype=np.float32)
    queries = np.asarray([[1, 0], [1, 0]], dtype=np.float32)
    report = multilingual_retrieval_report(dataset, ids, concepts, queries)
    assert report["folds"]["test"]["recall"]["@1"] == 1.0
