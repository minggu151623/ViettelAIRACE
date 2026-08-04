from airace.constrained_candidate_moe import candidate_for_normalized_mention


def test_concatenated_brand_identity_uses_bn_codes() -> None:
    selected = candidate_for_normalized_mention("vancozosynbactrim")
    assert selected is not None
    assert selected[0] == ["11124", "74170", "151399"]
    assert selected[1] == "concatenated_medication_segmenter"


def test_corpus_identity_repair_is_exact_not_fuzzy() -> None:
    assert candidate_for_normalized_mention("pimperam") == (
        ["6915"],
        "corpus_identity_repair",
        "near-identical corpus mention Pimperan",
    )
    assert candidate_for_normalized_mention("pimperan") is None
    assert candidate_for_normalized_mention("unknown medicine") is None
