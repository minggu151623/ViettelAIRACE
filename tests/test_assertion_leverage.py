from airace.assertion_leverage import cohort_report, entity_key


def _entity(text: str, start: int, assertions: list[str]) -> dict:
    return {
        "text": text,
        "type": "TRIỆU_CHỨNG",
        "position": [start, start + len(text)],
        "assertions": assertions,
        "candidates": [],
    }


def test_entity_key_includes_record_and_exact_span() -> None:
    entity = _entity("đau", 4, [])
    assert entity_key("2", entity) == ("2", "đau", "TRIỆU_CHỨNG", 4, 7)


def test_cohort_counts_only_novel_asserted_entities() -> None:
    old = _entity("đau", 0, [])
    new = _entity("sốt", 5, ["isPresent"])
    source = {entity_key("1", old): old}
    target = {entity_key("1", old): old, entity_key("1", new): new}
    report = cohort_report(source, target, assertion_delta=-0.1)
    assert report["novel_entities"] == 1
    assert report["asserted_novel_entities"] == 1
    assert report["assertion_label_distribution"] == {"isPresent": 1}
