from airace.schema import Entity
from airace.vietmed_detector import RawSpan, _clean_entity, _decode_line, _disease_type


def test_decode_merges_malformed_b_fragments_inside_word():
    text = "Khó thở"
    spans = _decode_line(
        text,
        100,
        [(0, 1), (1, 3), (4, 7)],
        [0, 0, 1],
        [0.9, 0.8, 0.95],
        {0: "B-DISEASESYMTOM", 1: "I-DISEASESYMTOM"},
    )
    assert [(span.start, span.end, span.label) for span in spans] == [
        (100, 107, "DISEASESYMTOM"),
    ]


def test_qwen_overlap_disambiguates_disease_symptom_label():
    text = "Tiền sử tăng huyết áp."
    span = RawSpan(9, 22, "DISEASESYMTOM", 0.9)
    reference = [
        Entity("tăng huyết áp", "CHẨN_ĐOÁN", position=(9, 22))
    ]
    assert _disease_type(text, span, reference)[0] == "CHẨN_ĐOÁN"


def test_generic_heading_is_filtered():
    text = "Triệu chứng"
    entity = Entity(
        text,
        "TRIỆU_CHỨNG",
        position=(0, len(text)),
        confidence=0.9,
        source="vietmed_ner",
    )
    assert _clean_entity(entity, text) is None
