import hashlib

from airace.multiview_consensus import _remove_new_overlaps, frozen_digest, relation


def test_relation_accepts_only_disjoint_or_contained_same_type():
    baseline = [{"text": "đau đầu kéo dài", "type": "TRIỆU_CHỨNG", "position": [0, 15]}]
    assert relation({"position": [0, 7], "type": "TRIỆU_CHỨNG"}, baseline)[0] == "contained_same_type"
    assert relation({"position": [20, 23], "type": "TRIỆU_CHỨNG"}, baseline)[0] == "disjoint"
    assert relation({"position": [0, 7], "type": "CHẨN_ĐOÁN"}, baseline)[0] == "cross_type"
    assert relation({"position": [0, 20], "type": "TRIỆU_CHỨNG"}, baseline)[0] == "contains_same_type"


def test_overlap_tie_prefers_more_views_then_longer():
    rows = [
        {"record": 1, "position": [0, 4], "type": "CHẨN_ĐOÁN", "record_support": 3},
        {"record": 1, "position": [0, 12], "type": "CHẨN_ĐOÁN", "record_support": 3},
        {"record": 1, "position": [20, 24], "type": "TRIỆU_CHỨNG", "record_support": 4},
    ]
    selected = _remove_new_overlaps(rows)
    assert [row["position"] for row in selected] == [[0, 12], [20, 24]]


def test_frozen_digest_includes_stable_names_and_delimiters(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "b.txt").write_bytes(b"two")
    (source / "a.txt").write_bytes(b"one")
    expected = hashlib.sha256(b"a.txt\0one\0b.txt\0two\0").hexdigest()
    assert frozen_digest(source) == expected
