from airace.section_expert_core import (chunk_windows, normalize_chunk_response,
                                        normalize_response)


def test_normalize_response_round_trip_and_unique_recovery() -> None:
    raw = "Bệnh nhân sốt. Xét nghiệm CRP tăng."
    response = {"entities": [
        {"text": "sốt", "type": "TRIỆU_CHỨNG", "start": 10, "end": 13,
         "assertions": []},
        {"text": "CRP", "type": "TÊN_XÉT_NGHIỆM", "start": -1, "end": -1,
         "assertions": []},
    ]}
    clinical = normalize_response(raw, "clinical", response)
    lab = normalize_response(raw, "laboratory", response)
    assert clinical[0]["text"] == "sốt"
    assert lab[0]["position"] == [26, 29]


def test_normalize_response_rejects_ambiguous_quote_and_wrong_type() -> None:
    raw = "đau rồi lại đau"
    response = {"entities": [
        {"text": "đau", "type": "TRIỆU_CHỨNG", "start": -1, "end": -1,
         "assertions": []},
        {"text": "đau", "type": "THUỐC", "start": 0, "end": 3,
         "assertions": []},
    ]}
    assert normalize_response(raw, "clinical", response) == []


def test_chunk_windows_cover_text_and_overlap() -> None:
    raw = "a" * 100 + "\n" + "b" * 100
    windows = chunk_windows(raw, size=120, overlap_size=20)
    assert windows[0][0] == 0
    assert windows[-1][1] == len(raw)
    assert windows[1][0] < windows[0][1]


def test_normalize_chunk_response_projects_all_repeated_quotes() -> None:
    raw = "prefix đau rồi đau suffix"
    rows = normalize_chunk_response(
        raw, 7, 19,
        {"entities": [{"q": "đau", "t": "TRIỆU_CHỨNG"}]},
    )
    assert [row["position"] for row in rows] == [[7, 10], [15, 18]]
