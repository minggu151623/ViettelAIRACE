from airace.rxnorm_identity_completion import select_contained_brand
from airace.schema import Entity


def drug(text: str, candidate: str = "4603") -> Entity:
    return Entity(text=text, type="THUỐC", position=[0, len(text)], candidates=[candidate])


def test_bounded_contained_brand_is_selected():
    assert select_contained_brand(drug("80mg po lasix"), {"lasix": "202991"}) == (
        "202991", "lasix"
    )


def test_mucinex_is_excluded_for_mucinex_d():
    assert select_contained_brand(drug("mucinex d"), {"mucinex": "352777"}) is None


def test_substring_without_word_boundary_is_rejected():
    assert select_contained_brand(drug("clasixate"), {"lasix": "202991"}) is None
