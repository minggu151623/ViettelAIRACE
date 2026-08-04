from airace.rxnorm_exact_brand import normalize_alias, select_exact_brand_replacement
from airace.schema import Entity


def entity(text: str, candidates: list[str], entity_type: str = "THUỐC") -> Entity:
    return Entity(
        text=text,
        type=entity_type,
        position=(0, len(text)),
        assertions=[],
        candidates=candidates,
    )


def test_full_span_unique_brand_replaces_generic_candidate():
    row = entity("  Tylenol  ", ["161"])
    assert normalize_alias(row.text) == "tylenol"
    assert select_exact_brand_replacement(row, {"tylenol": "202433"}) == "202433"


def test_no_fill_no_multicandidate_no_non_drug_and_no_identity_change():
    brands = {"tylenol": "202433"}
    assert select_exact_brand_replacement(entity("Tylenol", []), brands) is None
    assert select_exact_brand_replacement(entity("Tylenol", ["1", "2"]), brands) is None
    assert select_exact_brand_replacement(entity("Tylenol", ["161"], "CHẨN_ĐOÁN"), brands) is None
    assert select_exact_brand_replacement(entity("Tylenol", ["202433"]), brands) is None


def test_substring_or_fuzzy_brand_is_not_selected():
    brands = {"tylenol": "202433"}
    assert select_exact_brand_replacement(entity("Tylenol 500 mg", ["161"]), brands) is None
    assert select_exact_brand_replacement(entity("Tyleno", ["161"]), brands) is None
