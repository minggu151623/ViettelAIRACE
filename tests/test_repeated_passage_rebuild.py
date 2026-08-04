from airace.repeated_passage_consistency import Occurrence, RelativeEntity
from airace.repeated_passage_rebuild import rebuild_occurrence


def test_exact_local_entity_preserves_metadata():
    raw = "đau đầu kéo dài"
    occurrence = Occurrence(1, 0, len(raw))
    source = [{
        "text": "đau đầu", "type": "TRIỆU_CHỨNG",
        "assertions": ["isHistorical"], "position": [0, 7],
    }]
    rebuilt = rebuild_occurrence(
        raw, occurrence, [RelativeEntity(0, 7, "TRIỆU_CHỨNG")], source
    )
    assert rebuilt == source


def test_rebounded_entity_uses_only_local_overlap_metadata():
    raw = "đau đầu kéo dài"
    occurrence = Occurrence(1, 0, len(raw))
    source = [{
        "text": "đau đầu", "type": "TRIỆU_CHỨNG",
        "assertions": ["isNegated"], "position": [0, 7],
    }]
    rebuilt = rebuild_occurrence(
        raw, occurrence, [RelativeEntity(0, 16, "TRIỆU_CHỨNG")], source
    )
    assert rebuilt[0]["text"] == raw
    assert rebuilt[0]["assertions"] == ["isNegated"]


def test_disjoint_new_diagnosis_has_empty_local_metadata():
    raw = "viêm phổi"
    occurrence = Occurrence(1, 0, len(raw))
    rebuilt = rebuild_occurrence(
        raw, occurrence, [RelativeEntity(0, len(raw), "CHẨN_ĐOÁN")], []
    )
    assert rebuilt[0]["assertions"] == []
    assert rebuilt[0]["candidates"] == []
