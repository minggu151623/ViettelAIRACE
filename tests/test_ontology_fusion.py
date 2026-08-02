from airace.ontology_fusion import type_specialist_fusion


def test_type_router_uses_qwen_for_diagnosis_and_lexical_for_drug() -> None:
    dataset = {
        "label_status": "weak",
        "rows": [
            {"id": 1, "fold": "test", "type": "CHẨN_ĐOÁN", "gold_concepts": ["ICD:Q"]},
            {"id": 2, "fold": "test", "type": "THUỐC", "gold_concepts": ["RX:L"]},
        ],
    }
    lexical = {"predictions": [{"id": 1, "top10": ["ICD:L"]}, {"id": 2, "top10": ["RX:L"]}]}
    qwen = {"predictions": [{"id": 1, "top10": ["ICD:Q"]}, {"id": 2, "top10": ["RX:Q"]}]}
    report = type_specialist_fusion(dataset, lexical, qwen)
    assert report["folds"]["test"]["recall"]["@1"] == 1.0
    assert [row["source"] for row in report["predictions"]] == ["qwen", "lexical"]
