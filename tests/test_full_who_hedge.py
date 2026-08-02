from airace.full_who_hedge import _eligible_parent


WHO = {"I10": "Essential hypertension", "E11": "Type 2 diabetes"}


def test_singleton_specific_diagnosis_gets_parent():
    row = {"type": "CHẨN_ĐOÁN", "candidates": ["E11.9"]}
    assert _eligible_parent(row, WHO) == "E11"


def test_parent_multi_code_and_drug_are_ineligible():
    assert _eligible_parent({"type": "CHẨN_ĐOÁN", "candidates": ["I10"]}, WHO) is None
    assert _eligible_parent({"type": "CHẨN_ĐOÁN", "candidates": ["E11", "E11.9"]}, WHO) is None
    assert _eligible_parent({"type": "THUỐC", "candidates": ["E11.9"]}, WHO) is None
