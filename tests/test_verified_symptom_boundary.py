from __future__ import annotations

import json
import zipfile

from airace.verified_symptom_boundary import build_verified_symptoms


def test_replaces_same_type_adds_disjoint_and_skips_cross_type(tmp_path):
    inputs = tmp_path / "input"
    baseline = tmp_path / "baseline"
    inputs.mkdir()
    baseline.mkdir()
    raw = "đau đầu kéo dài, ngã và mất ngủ"
    (inputs / "1.txt").write_text(raw, encoding="utf-8")
    source = [
        {"text": "đau đầu kéo dài", "type": "TRIỆU_CHỨNG", "assertions": ["isHistorical"], "position": [0, 15]},
        {"text": "mất ngủ", "type": "CHẨN_ĐOÁN", "candidates": [], "assertions": [], "position": [24, 31]},
    ]
    (baseline / "1.json").write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    base_zip = tmp_path / "base.zip"
    with zipfile.ZipFile(base_zip, "w") as archive:
        archive.writestr("output/1.json", json.dumps(source))
    queue = [
        {"record": 1, "text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [0, 7]},
        {"record": 1, "text": "ngã", "type": "TRIỆU_CHỨNG", "position": [17, 20]},
        {"record": 1, "text": "mất ngủ", "type": "TRIỆU_CHỨNG", "position": [24, 31]},
    ]
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    agreement = tmp_path / "agreement.json"
    agreement.write_text(json.dumps({"queue": queue}, ensure_ascii=False), encoding="utf-8")
    report = build_verified_symptoms(
        inputs, baseline, base_zip, queue_path, agreement,
        tmp_path / "output", tmp_path / "output.zip", enforce_hashes=False,
    )
    result = json.loads((tmp_path / "output" / "1.json").read_text(encoding="utf-8"))
    assert result == [
        {"text": "đau đầu", "type": "TRIỆU_CHỨNG", "assertions": ["isHistorical"], "position": [0, 7]},
        {"text": "ngã", "type": "TRIỆU_CHỨNG", "assertions": [], "position": [17, 20]},
        source[1],
    ]
    assert report["applied_rows"] == 2
    assert report["counts"]["skipped_conflicts"] == 1
    assert report["validation"]["ok"]
