from collections import Counter

from airace.schema import Entity
from airace.v6_rebuild import _structural_cleanup
from airace.ablation import _embedded_short_symptoms


def test_structural_cleanup_removes_nested_wrong_type():
    text = "bệnh rễ thần kinh tuỷ sống"
    entities = [
        Entity(text, "CHẨN_ĐOÁN", position=(0, len(text)), candidates=[]),
        Entity("rễ thần kinh tuỷ sống", "TRIỆU_CHỨNG", position=(5, len(text))),
    ]
    result = _structural_cleanup(text, entities, Counter())
    assert [(entity.text, entity.type) for entity in result] == [
        (text, "CHẨN_ĐOÁN")
    ]


def test_structural_cleanup_does_not_call_talc_a_drug():
    text = "Không thực hiện gây dính màng phổi bằng talc"
    start = text.index("gây")
    entity = Entity(
        text[start:],
        "THUỐC",
        position=(start, len(text)),
        candidates=["10323"],
    )
    assert _structural_cleanup(text, [entity], Counter()) == []


def test_structural_cleanup_extracts_coagulation_product():
    text = "Các thủ thuật thực hiện: Truyền dịch yếu tố IX đậm đặc"
    start = text.index("Truyền")
    entity = Entity(
        text[start:],
        "TÊN_XÉT_NGHIỆM",
        position=(start, len(text)),
    )
    result = _structural_cleanup(text, [entity], Counter())
    assert [(item.text, item.type) for item in result] == [
        ("yếu tố IX đậm đặc", "THUỐC")
    ]


def test_structural_cleanup_removes_short_symptom_inside_word():
    text = "Bệnh nhân buồn nôn thoáng qua"
    start = text.index("ho")
    entity = Entity("ho", "TRIỆU_CHỨNG", position=(start, start + 2))
    assert _structural_cleanup(text, [entity], Counter()) == []


def test_structural_cleanup_keeps_standalone_short_symptom():
    text = "Bệnh nhân có ho và sốt"
    start = text.index("ho")
    entity = Entity("ho", "TRIỆU_CHỨNG", position=(start, start + 2))
    result = _structural_cleanup(text, [entity], Counter())
    assert [(item.text, item.type) for item in result] == [
        ("ho", "TRIỆU_CHỨNG")
    ]


def test_structural_cleanup_trims_drug_action_and_indication():
    text = "Tăng liều bactrim và dùng propofol để an thần"
    bactrim_start = text.index("Tăng")
    propofol_start = text.index("propofol")
    entities = [
        Entity(
            "Tăng liều bactrim",
            "THUỐC",
            position=(bactrim_start, bactrim_start + len("Tăng liều bactrim")),
            candidates=["151399"],
        ),
        Entity(
            "propofol để an thần",
            "THUỐC",
            position=(propofol_start, len(text)),
            candidates=["8782"],
        ),
    ]
    result = _structural_cleanup(text, entities, Counter())
    assert [(item.text, item.type, item.candidates) for item in result] == [
        ("bactrim", "THUỐC", ["151399"]),
        ("propofol", "THUỐC", ["8782"]),
    ]


def test_structural_cleanup_trims_glued_drug_history_suffix():
    text = "lasixđã dừng cách vài tuần"
    entity = Entity(
        text,
        "THUỐC",
        position=(0, len(text)),
        candidates=["202991"],
    )
    result = _structural_cleanup(text, [entity], Counter())
    assert result[0].text == "lasix"
    assert result[0].position == (0, 5)


def test_boundary_ablation_does_not_change_non_symptoms():
    text = "nồng độ acetaminophen"
    entity = Entity("nồn", "TÊN_XÉT_NGHIỆM", position=(0, 3))
    result = _embedded_short_symptoms(text, [entity], Counter())
    assert result == [entity]
