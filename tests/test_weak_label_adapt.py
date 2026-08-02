import json

from airace.weak_label_adapt import dev_gates, export_jsonl, final_test_gates


def test_export_jsonl_preserves_raw_and_entities(tmp_path):
    inputs, labels = tmp_path / "input", tmp_path / "labels"
    inputs.mkdir(); labels.mkdir()
    (inputs / "1.txt").write_text("đau đầu", encoding="utf-8")
    entity = {"text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [0, 7],
              "assertions": [], "candidates": None}
    (labels / "1.json").write_text(json.dumps([entity], ensure_ascii=False), encoding="utf-8")
    target = tmp_path / "rows.jsonl"
    assert export_jsonl(inputs, labels, [1], target) == 1
    row = json.loads(target.read_text())
    assert row["text"] == "đau đầu" and row["entities"][0]["position"] == [0, 7]


def test_h30_gates_are_fail_closed():
    dev = {"f1": .82, "precision": .82, "offset_errors": 0}
    assert all(dev_gates(dev).values())
    result = {"f1": .78, "precision": .78,
              "per_type": {"x": {"gold_support": 20, "f1": .60}},
              "per_record": {1: [(0, 1, "x")]}}
    assert all(final_test_gates(result, result).values())
