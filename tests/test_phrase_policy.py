from airace.phrase_policy import PhraseEntry, match_lexicon, phrase_key, select_disjoint


def test_phrase_key_preserves_accents_but_folds_case_and_space():
    assert phrase_key("  Đau   đầu ") == "đau đầu"
    assert phrase_key("đau đầu") != phrase_key("dau dau")


def test_case_insensitive_matching_preserves_raw_offsets():
    raw = "ĐAU ĐẦU, sau đó đau đầu nhẹ."
    entries = [PhraseEntry("đau đầu", "TRIỆU_CHỨNG", 3, 5)]
    rows = match_lexicon(raw, 1, entries, case_sensitive=False)
    assert [(row.text, row.position) for row in rows] == [
        ("ĐAU ĐẦU", (0, 7)), ("đau đầu", (16, 23)),
    ]


def test_longest_phrase_wins_and_baseline_overlap_is_excluded():
    raw = "đau đầu dữ dội"
    entries = [
        PhraseEntry("đau đầu dữ dội", "TRIỆU_CHỨNG", 2, 2),
        PhraseEntry("đau đầu", "TRIỆU_CHỨNG", 4, 8),
    ]
    rows = match_lexicon(raw, 1, entries, case_sensitive=True)
    assert [row.text for row in select_disjoint(rows, [])] == ["đau đầu dữ dội"]
    assert select_disjoint(rows, [(0, 3)]) == []
