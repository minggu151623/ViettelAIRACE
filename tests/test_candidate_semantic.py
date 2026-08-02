from __future__ import annotations

import json

from airace.candidate_semantic import build_candidate_semantic_ablation


def _write_record(tmp_path, entities):
    inputs = tmp_path / "input"
    source = tmp_path / "source"
    inputs.mkdir()
    source.mkdir()
    (inputs / "1.txt").write_text("Bệnh mạch vành aspirin", encoding="utf-8")
    (source / "1.json").write_text(
        json.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )
    return inputs, source


def test_adds_same_family_parent_and_freezes_drug(tmp_path):
    entities = [
        {
            "text": "Bệnh mạch vành",
            "type": "CHẨN_ĐOÁN",
            "candidates": ["I25.10"],
            "assertions": [],
            "position": [0, 14],
        },
        {
            "text": "aspirin",
            "type": "THUỐC",
            "candidates": ["1191"],
            "assertions": [],
            "position": [15, 22],
        },
    ]
    inputs, source = _write_record(tmp_path, entities)
    report = build_candidate_semantic_ablation(
        inputs, source, tmp_path / "output", minimum_changes=1
    )
    result = json.loads((tmp_path / "output" / "1.json").read_text(encoding="utf-8"))
    assert result[0]["candidates"] == ["I25", "I25.10"]
    assert result[1] == entities[1]
    assert report["changed_rows"] == 1


def test_keeps_exact_who_and_quarantines_multi_code_rows(tmp_path):
    entities = [
        {
            "text": "Bệnh mạch vành",
            "type": "CHẨN_ĐOÁN",
            "candidates": ["I25.1"],
            "assertions": [],
            "position": [0, 14],
        },
        {
            "text": "aspirin",
            "type": "THUỐC",
            "candidates": ["1191"],
            "assertions": [],
            "position": [15, 22],
        },
    ]
    inputs, source = _write_record(tmp_path, entities)
    report = build_candidate_semantic_ablation(
        inputs, source, tmp_path / "output", minimum_changes=0
    )
    result = json.loads((tmp_path / "output" / "1.json").read_text(encoding="utf-8"))
    assert result == entities
    assert report["changed_rows"] == 0
