import json
from pathlib import Path

from airace.who_icd_rebuild import build_h19_selection, load_who_icd10, merge_who_icd_review


def test_who_catalog_uses_canonical_code_field() -> None:
    catalog = load_who_icd10()
    assert "A00" in catalog
    assert "A00.0" in catalog
    assert "D75.A" not in catalog
    assert len(catalog) > 10_000


def test_who_merge_changes_only_diagnosis_candidates(tmp_path: Path) -> None:
    inputs, source, output = tmp_path / "input", tmp_path / "source", tmp_path / "output"
    inputs.mkdir(); source.mkdir()
    text = "viêm phổi dùng aspirin"
    (inputs / "1.txt").write_text(text, encoding="utf-8")
    values = [
        {"text": "viêm phổi", "type": "CHẨN_ĐOÁN", "candidates": ["J18.9"], "assertions": [], "position": [0, 9]},
        {"text": "aspirin", "type": "THUỐC", "candidates": ["1191"], "assertions": [], "position": [15, 22]},
    ]
    (source / "1.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    review = {"rows": [{"key": "viem phoi", "final_codes": ["J18", "J18.9"]}]}
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    report = merge_who_icd_review(inputs, source, review_path, output)
    result = json.loads((output / "1.json").read_text(encoding="utf-8"))
    assert report["candidate_changes"] == 1
    assert result[0]["candidates"] == ["J18", "J18.9"]
    assert result[1]["candidates"] == ["1191"]


def test_h19_reviewer_can_remove_old_and_reconciles_families(tmp_path: Path) -> None:
    review = {
        "rows": [
            {
                "key": "stent mach vanh",
                "text": "stent mạch vành",
                "uses": 1,
                "current_candidate_sets": [{"codes": ["T82.8"], "uses": 1}],
                "proposal": {"codes": [], "confidence": 0.0},
                "review": {"requested_keep_codes": [], "confidence": 1.0},
            },
            {
                "key": "roi loan lo au",
                "text": "rối loạn lo âu",
                "uses": 1,
                "current_candidate_sets": [{"codes": ["F40"], "uses": 1}],
                "proposal": {"codes": ["F41.1"], "confidence": 1.0},
                "review": {"requested_keep_codes": ["F40", "F41.1"], "confidence": 0.95},
            },
        ]
    }
    source = tmp_path / "review.json"
    target = tmp_path / "selection.json"
    source.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    build_h19_selection(source, target)
    rows = json.loads(target.read_text(encoding="utf-8"))["rows"]
    assert rows[0]["h19_codes"] == []
    assert rows[1]["h19_codes"] == ["F41.1"]
