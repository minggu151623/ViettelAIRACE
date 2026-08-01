from airace.schema import Entity
from airace.turn2_llm_rebuild import _choose_type, _proposal_is_safe


def _entity(text: str, kind: str, start: int = 0) -> Entity:
    return Entity(text=text, type=kind, position=(start, start + len(text)))


def test_turn2_noise_filter_rejects_generic_llm_spans() -> None:
    raw = "bệnh hiện tại điều trị nón"
    assert not _proposal_is_safe(_entity("bệnh hiện tại", "CHẨN_ĐOÁN"), raw, len(raw))
    assert not _proposal_is_safe(_entity("điều trị", "TÊN_XÉT_NGHIỆM", 14), raw, len(raw))
    assert not _proposal_is_safe(_entity("nón", "TRIỆU_CHỨNG", 23), raw, len(raw))


def test_turn2_type_guard_overrides_llm_for_test_and_drug() -> None:
    assert _choose_type(
        "xét nghiệm gắng sức bất thường",
        [_entity("xét nghiệm gắng sức bất thường", "CHẨN_ĐOÁN")],
    ) == "TÊN_XÉT_NGHIỆM"
    assert _choose_type(
        "thuốc giảm đau opioid",
        [_entity("thuốc giảm đau opioid", "TÊN_XÉT_NGHIỆM")],
    ) == "THUỐC"


def test_turn2_type_guard_treats_obesity_as_diagnosis() -> None:
    assert _choose_type(
        "chứng béo phì",
        [_entity("chứng béo phì", "TRIỆU_CHỨNG")],
    ) == "CHẨN_ĐOÁN"
