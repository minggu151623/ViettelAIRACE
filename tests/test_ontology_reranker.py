from airace.ontology_graph import ConceptEdge, ConceptNode, OntologyGraph
from airace.ontology_reranker import format_concept_document, format_rerank_query


def test_graph_document_adds_exact_relation() -> None:
    graph = OntologyGraph(
        nodes={
            "ICD:A00.1": ConceptNode("ICD:A00.1", "WHO", "child title", (), "DIAGNOSIS"),
            "ICD:A00": ConceptNode("ICD:A00", "WHO", "parent title", (), "DIAGNOSIS"),
        },
        edges=(ConceptEdge("ICD:A00.1", "ICD:A00", "icd_parent"),),
    )
    plain = format_concept_document(graph, "ICD:A00.1", include_graph=False)
    enriched = format_concept_document(graph, "ICD:A00.1", include_graph=True)
    assert "parent title" not in plain
    assert "icd_parent -> parent title [ICD:A00]" in enriched


def test_query_contains_frozen_context_and_type() -> None:
    query = format_rerank_query(
        {"type": "CHẨN_ĐOÁN", "mention": "suy tim", "contexts": ["có ⟦suy tim⟧"]}
    )
    assert "CHẨN_ĐOÁN" in query
    assert "có ⟦suy tim⟧" in query
