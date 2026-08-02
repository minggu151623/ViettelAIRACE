import hashlib
import json
from pathlib import Path

import pytest

from airace import passage_annotation as pa


def _write_repeated_corpus(path: Path) -> None:
    for record in range(1, 7):
        lines = []
        for index in range(60):
            repeat = 4 if index < 13 else 3 if index < 30 else 2
            if record <= repeat:
                lines.append(
                    f"Đoạn lâm sàng số {index:02d} có đủ độ dài và được lặp lại nguyên văn."
                )
        (path / f"{record}.txt").write_text("\n".join(lines), encoding="utf-8")


def test_build_manifest_is_blind_stratified_and_deterministic(tmp_path: Path, monkeypatch):
    corpus = tmp_path / "input"
    corpus.mkdir()
    _write_repeated_corpus(corpus)
    monkeypatch.setattr(pa, "EXPECTED_INPUT_SHA256", pa._tree_digest(corpus))
    first, second = tmp_path / "queue1.json", tmp_path / "queue2.json"
    manifest = pa.build_manifest(corpus, first)
    pa.build_manifest(corpus, second)
    assert first.read_bytes() == second.read_bytes()
    assert manifest["passage_count"] == 60
    assert manifest["development_count"] == 45
    assert manifest["holdout_count"] == 15
    counts = {}
    for stratum in pa.STRATA:
        values = [row for row in manifest["passages"] if row["stratum"] == stratum]
        counts[stratum] = len(values)
    assert counts == {"high": 13, "middle": 17, "low": 30}
    serialized = first.read_text(encoding="utf-8").lower()
    assert "prediction" not in serialized
    assert "confidence" not in serialized
    audit = pa.audit_manifest(corpus, first)
    assert audit["status"] == "passed"
    assert audit["occurrence_count"] == 163
    secondary_path = tmp_path / "secondary.json"
    secondary = pa.build_secondary_manifest(first, secondary_path)
    assert secondary["passage_count"] == 15
    assert all("split" not in row for row in secondary["passages"])


def test_entities_and_occurrence_assertions_validate():
    text = "Bệnh nhân đau đầu và sốt."
    entities = pa.validate_passage_entities(
        text,
        [{"text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [10, 17]}],
    )
    rows = pa.validate_occurrence_assertions(
        entities,
        [{
            "record_id": "1",
            "occurrence_position": [100, 127],
            "entity_index": 0,
            "assertions": ["isHistorical", "isNegated"],
        }],
    )
    assert rows[0]["assertions"] == ["isHistorical", "isNegated"]
    with pytest.raises(ValueError):
        pa.validate_passage_entities(
            text,
            [{"text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [9, 16]}],
        )


def test_annotation_file_requires_full_stage_b_coverage(tmp_path: Path):
    text = "Bệnh nhân đau đầu và sốt."
    passage_id = hashlib.sha256(text.encode()).hexdigest()
    manifest = {
        "passages": [{
            "passage_id": passage_id,
            "text": text,
            "occurrences": [
                {"record_id": "1", "position": [0, len(text)]},
                {"record_id": "2", "position": [3, 3 + len(text)]},
            ],
        }]
    }
    manifest_path = tmp_path / "manifest.json"
    labels_path = tmp_path / "labels.jsonl"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    label = {
        "passage_id": passage_id,
        "passage_sha256": passage_id,
        "reviewer_id": "r1",
        "entities": [{"text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [10, 17]}],
        "occurrence_assertions": [{
            "record_id": "1", "occurrence_position": [0, len(text)],
            "entity_index": 0, "assertions": []
        }],
        "stage_a_reviewed": True,
        "stage_b_reviewed": True,
    }
    pa.save_label(labels_path, label)
    with pytest.raises(ValueError, match="coverage mismatch"):
        pa.validate_annotation_file(manifest_path, labels_path)


def test_reviewer_agreement_scores_exact_spans_and_multi_assertions(tmp_path: Path):
    text = "Bệnh nhân đau đầu và sốt."
    passage_id = hashlib.sha256(text.encode()).hexdigest()
    passage = {
        "passage_id": passage_id,
        "split": "holdout",
        "text": text,
        "occurrences": [{"record_id": "1", "position": [0, len(text)]}],
    }
    main_manifest = tmp_path / "main.json"
    second_manifest = tmp_path / "second.json"
    main_manifest.write_text(json.dumps({"passages": [passage]}), encoding="utf-8")
    blind_passage = dict(passage)
    blind_passage.pop("split")
    second_manifest.write_text(json.dumps({"passages": [blind_passage]}), encoding="utf-8")
    label = {
        "passage_id": passage_id,
        "passage_sha256": passage_id,
        "reviewer_id": "reviewer",
        "entities": [{"text": "đau đầu", "type": "TRIỆU_CHỨNG", "position": [10, 17]}],
        "occurrence_assertions": [{
            "record_id": "1", "occurrence_position": [0, len(text)],
            "entity_index": 0, "assertions": ["isHistorical", "isNegated"]
        }],
        "stage_a_reviewed": True,
        "stage_b_reviewed": True,
    }
    left, right = tmp_path / "left.jsonl", tmp_path / "right.jsonl"
    pa.save_label(left, label)
    label["reviewer_id"] = "reviewer_2"
    pa.save_label(right, label)
    report = pa.reviewer_agreement(main_manifest, second_manifest, left, right)
    assert report["status"] == "passed"
    assert report["strict_span_type"]["F1"] == 1.0
    assert report["assertion_macro_jaccard"] == 1.0
