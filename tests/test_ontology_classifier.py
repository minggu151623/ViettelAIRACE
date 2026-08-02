from airace.ontology_classifier import stable_candidate_union


def test_candidate_union_is_stable_and_deduplicated() -> None:
    assert stable_candidate_union(["A", "B", "C"], ["B", "D", "A"]) == ["A", "B", "C", "D"]
