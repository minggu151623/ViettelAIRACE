from airace.family_novelty import family_novelty_decomposition


def _change(record: str, text: str, parent: str, specific: str) -> dict:
    return {"record_id": record, "text": text, "after": [parent, specific]}


def test_decomposition_partitions_seen_and_novel_families() -> None:
    h23 = {"changes": [_change("1", "old", "A00", "A00.1")]}
    h44 = {
        "changes": [
            _change("2", "new seen", "A00", "A00.2"),
            _change("3", "new family", "B00", "B00.1"),
            _change("4", "new family 2", "B00", "B00.2"),
        ]
    }
    h53 = {"cross_experiment": {"parent_family_overlap": 1}}
    report = family_novelty_decomposition(h23, h44, h53)
    assert report["strata"]["h23_seen_family"]["changed_rows"] == 1
    assert report["strata"]["h23_novel_family"]["changed_rows"] == 2
    assert report["cross_checks"]["zero_specific_code_overlap"]
    assert report["cross_checks"]["zero_normalized_lexical_unit_overlap"]


def test_decomposition_detects_specific_overlap() -> None:
    shared = _change("1", "x", "A00", "A00.1")
    h53 = {"cross_experiment": {"parent_family_overlap": 1}}
    report = family_novelty_decomposition({"changes": [shared]}, {"changes": [shared]}, h53)
    assert not report["cross_checks"]["zero_specific_code_overlap"]
    assert not report["cross_checks"]["zero_normalized_lexical_unit_overlap"]
