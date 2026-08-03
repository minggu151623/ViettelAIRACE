from airace.phoner_boundary import (
    boundary_metrics,
    clinical_entities,
    select_threshold,
)
from airace.schema import Entity
from airace.phoner_target_merge import select_exact_supported


def test_clinical_entities_preserve_exact_offsets_and_separate_mentions() -> None:
    words = ["Bệnh", "nhân", "sốt", "cao", "và", "khó", "thở", "."]
    tags = [
        "O", "O", "B-SYMPTOM_AND_DISEASE", "I-SYMPTOM_AND_DISEASE",
        "O", "B-SYMPTOM_AND_DISEASE", "I-SYMPTOM_AND_DISEASE", "O",
    ]
    text, entities = clinical_entities(words, tags)
    assert [entity.text for entity in entities] == ["sốt cao", "khó thở"]
    assert all(text[start:end] == entity.text for entity in entities
               for start, end in [entity.position])


def test_clinical_entities_repairs_orphan_inside_tag() -> None:
    text, entities = clinical_entities(["đau", "đầu"], [
        "I-SYMPTOM_AND_DISEASE", "I-SYMPTOM_AND_DISEASE",
    ])
    assert text == "đau đầu"
    assert [entity.position for entity in entities] == [(0, 7)]


def test_boundary_metrics_ignore_source_type_but_apply_confidence() -> None:
    gold = [{"entities": [{"position": [0, 3]}]}]
    predicted = [[
        Entity("đau", "CHẨN_ĐOÁN", position=(0, 3), confidence=0.95),
        Entity("đầu", "TRIỆU_CHỨNG", position=(4, 7), confidence=0.60),
    ]]
    metrics = boundary_metrics(gold, predicted, 0.90)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_select_threshold_obeys_frozen_gates_before_recall() -> None:
    selected = select_threshold([
        {"threshold": 0.80, "precision": 0.89, "recall": 0.90, "f1": 0.895},
        {"threshold": 0.90, "precision": 0.91, "recall": 0.70, "f1": 0.79},
        {"threshold": 0.95, "precision": 0.95, "recall": 0.60, "f1": 0.735},
    ])
    assert selected is not None
    assert selected["threshold"] == 0.90


def test_target_merge_requires_exact_boundary_not_overlap() -> None:
    proposals = [
        {"record": 1, "position": [10, 20], "type": "TRIỆU_CHỨNG"},
        {"record": 1, "position": [30, 40], "type": "CHẨN_ĐOÁN"},
    ]
    selected = select_exact_supported(proposals, {1: {(10, 20), (29, 40)}})
    assert selected == [proposals[0]]
