from airace.phoner_boundary_resegment import select_replacements


def _row(text: str, start: int, end: int, kind: str = "TRIỆU_CHỨNG") -> dict:
    return {
        "text": text,
        "type": kind,
        "position": [start, end],
        "assertions": [],
    }


def test_select_replacements_keeps_only_one_to_one_containment() -> None:
    baseline = {1: [_row("đau đầu nhiều", 0, 13), _row("ho", 20, 22)]}
    teacher = {"1": [
        {"text": "đau đầu", "position": [0, 7], "confidence": 0.9},
        {"text": "ho kéo dài", "position": [20, 30], "confidence": 0.9},
        {"text": "ngoài", "position": [40, 45], "confidence": 0.9},
    ]}
    selected, rejected = select_replacements(baseline, teacher)
    assert [row["relation"] for row in selected] == [
        "teacher_strictly_inside_baseline",
        "baseline_strictly_inside_teacher",
    ]
    assert rejected["not_exactly_one_baseline_overlap"] == 1


def test_select_replacements_rejects_competing_teacher_spans() -> None:
    baseline = {1: [_row("đau đầu dữ dội", 0, 15)]}
    teacher = {"1": [
        {"text": "đau đầu", "position": [0, 7], "confidence": 0.9},
        {"text": "đầu dữ dội", "position": [4, 15], "confidence": 0.9},
    ]}
    selected, rejected = select_replacements(baseline, teacher)
    assert selected == []
    assert rejected["competing_teacher_spans"] == 2


def test_select_replacements_does_not_resegment_nonclinical_rows() -> None:
    baseline = {1: [_row("CRP tăng", 0, 8, "KẾT_QUẢ_XÉT_NGHIỆM")]}
    teacher = {"1": [
        {"text": "tăng", "position": [4, 8], "confidence": 0.9},
    ]}
    selected, rejected = select_replacements(baseline, teacher)
    assert selected == []
    assert rejected["nonclinical_baseline_type"] == 1
