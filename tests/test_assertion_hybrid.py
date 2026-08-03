import json
from pathlib import Path

from airace.assertion_hybrid import _load_direct, _load_reviews, _response_audit


def test_load_direct_deduplicates_and_rejects_invalid(tmp_path: Path):
    path = tmp_path / "direct.json"
    path.write_text(json.dumps({"response": {"labels": [
        {"id": 1, "assertions": ["isNegated", "isHistorical"]},
        {"id": 1, "assertions": []},
        {"id": 2, "assertions": ["bad"]},
    ]}}))
    assert _load_direct(path) == {1: ("isNegated", "isHistorical")}


def test_load_reviews_keeps_first_id(tmp_path: Path):
    path = tmp_path / "critic.json"
    first = {"id": 4, "assertions": [], "evidence": [], "removals": []}
    second = {"id": 4, "assertions": ["isFamily"], "evidence": [], "removals": []}
    path.write_text(json.dumps({"response": {"reviews": [first, second]}}))
    assert _load_reviews(path) == {4: first}


def test_load_reviews_combines_ordered_shards(tmp_path: Path):
    first = {"id": 1, "assertions": [], "evidence": [], "removals": []}
    second = {"id": 2, "assertions": ["isNegated"], "evidence": [], "removals": []}
    (tmp_path / "9_0.json").write_text(json.dumps({"response": {"reviews": [first]}}))
    (tmp_path / "9_1.json").write_text(json.dumps({"response": {"reviews": [second]}}))
    assert _load_reviews(tmp_path / "9.json") == {1: first, 2: second}


def test_response_audit_counts_both_stages(tmp_path: Path):
    rows = [
        {"type": "TRIỆU_CHỨNG", "assertions": []},
        {"type": "CHẨN_ĐOÁN", "assertions": ["isHistorical"]},
        {"type": "TÊN_XÉT_NGHIỆM", "assertions": []},
    ]
    direct = tmp_path / "direct.json"
    direct.write_text(json.dumps({"response": {"labels": [
        {"id": 0, "assertions": ["isNegated"]},
        {"id": 0, "assertions": []},
    ]}}))
    critic = tmp_path / "critic.json"
    critic.write_text(json.dumps({"response": {"reviews": [
        {"id": 0, "assertions": ["isNegated"], "evidence": [], "removals": []},
        {"id": 99, "assertions": [], "evidence": [], "removals": []},
    ]}}))
    assert _response_audit(rows, direct, critic) == {
        "direct_expected": 2,
        "direct_returned": 1,
        "direct_missing": 1,
        "direct_malformed": 1,
        "critic_expected": 1,
        "critic_returned": 1,
        "critic_missing": 0,
        "critic_malformed": 1,
    }
