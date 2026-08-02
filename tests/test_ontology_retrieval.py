from airace.ontology_graph import ConceptNode, OntologyGraph
from airace.ontology_retrieval import lexical_retrieval_baseline


def test_lexical_retrieval_finds_exact_alias() -> None:
    graph = OntologyGraph(
        nodes={
            "ICD:A": ConceptNode("ICD:A", "ICD", "cholera", ("cholera",), "DIAGNOSIS"),
            "ICD:B": ConceptNode("ICD:B", "ICD", "asthma", ("asthma",), "DIAGNOSIS"),
        },
        edges=(),
    )
    dataset = {
        "rows": [
            {
                "id": 0,
                "mention": "asthma",
                "type": "CHẨN_ĐOÁN",
                "gold_concepts": ["ICD:B"],
            }
        ]
    }
    report = lexical_retrieval_baseline(graph, dataset)
    assert report["recall"]["@1"] == 1.0
    assert report["predictions"][0]["top10"][0] == "ICD:B"

