import json
from pathlib import Path

from airace.lab_splitter import find_numeric_lab_pairs
from airace.evidence_rebuild import split_numeric_labs
from airace.schema import Entity


ROOT = Path(__file__).resolve().parents[1]


def test_policy_numeric_lab_fixture() -> None:
    rows = [
        json.loads(line)
        for line in (ROOT / "labels" / "policy_lab_numeric_fixture.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    lab_names = [row["name"]["text"] for row in rows]
    by_record: dict[int, list[dict]] = {}
    for row in rows:
        by_record.setdefault(row["record_id"], []).append(row)

    recovered: set[tuple[int, tuple[int, int], tuple[int, int]]] = set()
    for record_id, expected_rows in by_record.items():
        raw_text = (ROOT / "input" / f"{record_id}.txt").read_text(encoding="utf-8")
        for pair in find_numeric_lab_pairs(raw_text, lab_names):
            recovered.add((record_id, pair.name, pair.result))

    expected = {
        (
            row["record_id"],
            tuple(row["name"]["position"]),
            tuple(row["result"]["position"]),
        )
        for row in rows
    }
    assert expected <= recovered


def test_numeric_lab_splitter_keeps_units_and_rejects_textual_findings() -> None:
    raw_text = "glucose: 120 mg/dL; cấy máu âm tính; 80 neutrophil"
    pairs = find_numeric_lab_pairs(raw_text, ["glucose", "cấy máu", "neutrophil"])
    spans = {(raw_text[a:b], raw_text[c:d]) for (a, b), (c, d) in [
        (pair.name, pair.result) for pair in pairs
    ]}
    assert ("glucose", "120 mg/dL") in spans
    assert ("neutrophil", "80") in spans
    assert all(name != "cấy máu" for name, _ in spans)


def test_numeric_lab_splitter_rejects_adjacent_vital_and_treatment_dose() -> None:
    raw_text = "hr 88 rr 14 spo2 100\\n- Được bổ sung kali 80mEq trong 24 giờ"
    pairs = find_numeric_lab_pairs(raw_text, ["spo2", "kali"])
    spans = {(raw_text[a:b], raw_text[c:d]) for (a, b), (c, d) in [
        (pair.name, pair.result) for pair in pairs
    ]}
    assert ("spo2", "100") in spans
    assert ("spo2", "14") not in spans
    assert all(name != "kali" for name, _ in spans)


def test_numeric_lab_splitter_defers_trends_and_glued_suffixes() -> None:
    raw_text = "creatinine 2.0 -> 3.2\n- lactate 1.1-->0.8\n- spo2 100ra"
    pairs = find_numeric_lab_pairs(raw_text, ["creatinine", "lactate", "spo2"])
    assert pairs == []


def test_numeric_lab_splitter_prefers_longest_alias_per_value() -> None:
    raw_text = "canxi toàn phần là 12.0; canxi ion hóa 6.8"
    pairs = find_numeric_lab_pairs(
        raw_text,
        ["canxi", "canxi toàn phần", "canxi ion hóa"],
    )
    spans = {(raw_text[a:b], raw_text[c:d]) for (a, b), (c, d) in [
        (pair.name, pair.result) for pair in pairs
    ]}
    assert ("canxi toàn phần", "12.0") in spans
    assert ("canxi ion hóa", "6.8") in spans
    assert ("canxi", "12.0") not in spans


def test_evidence_rebuild_replaces_compound_lab_result() -> None:
    raw_text = "glucose: 120 mg/dL; bệnh nhân tỉnh"
    entities = [
        Entity(
            text="glucose: 120 mg/dL",
            type="KẾT_QUẢ_XÉT_NGHIỆM",
            position=(0, 19),
        ),
        Entity(
            text="bệnh nhân",
            type="THÔNG_TIN_BỆNH_NHÂN",
            position=(21, 31),
        ),
    ]

    rebuilt = split_numeric_labs(raw_text, entities, ["glucose"])
    rows = {(entity.text, entity.type, entity.position) for entity in rebuilt}

    assert ("glucose: 120 mg/dL", "KẾT_QUẢ_XÉT_NGHIỆM", (0, 19)) not in rows
    assert ("glucose", "TÊN_XÉT_NGHIỆM", (0, 7)) in rows
    assert ("120 mg/dL", "KẾT_QUẢ_XÉT_NGHIỆM", (9, 18)) in rows
    assert ("bệnh nhân", "THÔNG_TIN_BỆNH_NHÂN", (21, 31)) in rows


def test_evidence_rebuild_keeps_existing_exact_lab_entities() -> None:
    raw_text = "glucose 120"
    entities = [
        Entity(text="glucose", type="TÊN_XÉT_NGHIỆM", position=(0, 7)),
        Entity(text="120", type="KẾT_QUẢ_XÉT_NGHIỆM", position=(8, 11)),
    ]

    rebuilt = split_numeric_labs(raw_text, entities, ["glucose"])

    assert [entity.to_dict() for entity in rebuilt] == [
        entity.to_dict() for entity in entities
    ]
