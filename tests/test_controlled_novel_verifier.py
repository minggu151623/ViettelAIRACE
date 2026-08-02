from airace.controlled_novel_verifier import CONTROL_TYPES


def test_controls_cover_submission_entity_types_with_candidates():
    assert CONTROL_TYPES == ("CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "THUỐC")
