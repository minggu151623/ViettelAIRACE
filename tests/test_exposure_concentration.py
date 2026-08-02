from airace.exposure_concentration import concentration_audit, normalize_mention, summarize


def _change(record: str, text: str, parent: str, specific: str) -> dict:
    return {"record_id": record, "text": text, "after": [parent, specific]}


def test_normalize_mention_is_case_and_whitespace_invariant() -> None:
    assert normalize_mention("  Thiếu   MEN G6PD ") == "thiếu men g6pd"


def test_summary_uses_inverse_simpson_and_registered_shares() -> None:
    changes = [
        _change("1", "a", "A00", "A00.1"),
        _change("1", "A", "A00", "A00.1"),
        _change("2", "b", "B00", "B00.1"),
    ]
    result = summarize(changes)
    assert result["affected_records"] == 2
    assert result["unique_parent_families"] == 2
    assert result["unique_lexical_units"] == 2
    assert result["effective_parent_families_inverse_simpson"] == 1.8
    assert result["top_1_parent_row_share"] == 0.666667


def test_concentration_interpretation_and_overlap() -> None:
    h23 = {"changes": [_change("1", "a", "A00", "A00.1")]}
    h44 = {"changes": [_change("2", "a", "A00", "A00.1")]}
    result = concentration_audit(h23, h44)
    assert result["cross_experiment"] == {
        "parent_family_overlap": 1,
        "specific_code_overlap": 1,
        "lexical_unit_overlap": 1,
    }
    assert result["interpretation"] == "neither_broad"


def test_rejects_non_family_pair() -> None:
    try:
        summarize([_change("1", "x", "A00", "B00.1")])
    except ValueError as error:
        assert "not same-family" in str(error)
    else:
        raise AssertionError("expected same-family validation failure")
