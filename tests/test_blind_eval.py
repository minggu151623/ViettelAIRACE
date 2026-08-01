import json
from pathlib import Path

from airace.blind_eval import (
    build_calibration_manifest,
    evaluate_blind_challenger,
    paired_bootstrap_interval,
    verify_manifest,
)


def _entity(text: str) -> dict:
    return {
        "text": text,
        "type": "TRIỆU_CHỨNG",
        "assertions": [],
        "position": [0, len(text)],
    }


def test_blind_manifest_is_deterministic_and_stratified(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for record_id in range(1, 101):
        text = (f"{record_id}. Bệnh sử\n- đau " * record_id).strip()
        (input_dir / f"{record_id}.txt").write_text(text, encoding="utf-8")
    first = build_calibration_manifest(input_dir, tmp_path / "first.json")
    second = build_calibration_manifest(input_dir, tmp_path / "second.json")
    assert first == second
    assert len(first["records"]) == 18
    assert len(first["record_ids"]["development"]) == 12
    assert len(first["record_ids"]["holdout"]) == 6
    assert {row["stratum"] for row in first["records"]} == set(range(1, 7))
    assert not verify_manifest(first, input_dir)

    (input_dir / "1.txt").write_text("changed", encoding="utf-8")
    assert verify_manifest(first, input_dir)


def test_paired_bootstrap_is_deterministic():
    first = paired_bootstrap_interval([0.1, 0.2, 0.3], iterations=1000)
    second = paired_bootstrap_interval([0.1, 0.2, 0.3], iterations=1000)
    assert first == second
    assert first["lower_95"] > 0


def test_holdout_promotes_only_clear_paired_improvement(tmp_path: Path):
    input_dir = tmp_path / "input"
    baseline = tmp_path / "baseline"
    challenger = tmp_path / "challenger"
    for directory in (input_dir, baseline, challenger):
        directory.mkdir()
    records = []
    label_rows = []
    for record_id in range(1, 7):
        text = f"đau{record_id}"
        (input_dir / f"{record_id}.txt").write_text(text, encoding="utf-8")
        (baseline / f"{record_id}.json").write_text("[]", encoding="utf-8")
        (challenger / f"{record_id}.json").write_text(
            json.dumps([_entity(text)], ensure_ascii=False), encoding="utf-8"
        )
        raw = (input_dir / f"{record_id}.txt").read_bytes()
        import hashlib

        records.append(
            {
                "record_id": str(record_id),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "features": {"characters": len(text)},
                "stratum": record_id,
                "split": "holdout",
            }
        )
        label_rows.append(
            {
                "record_id": str(record_id),
                "text": text,
                "entities": [_entity(text)],
                "reviewed": True,
            }
        )
    from airace.blind_eval import corpus_fingerprint

    fingerprint, _ = corpus_fingerprint(input_dir)
    manifest = {
        "corpus_sha256": fingerprint,
        "records": records,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in label_rows) + "\n",
        encoding="utf-8",
    )
    report = evaluate_blind_challenger(
        input_dir=input_dir,
        manifest_path=manifest_path,
        labels_path=labels_path,
        baseline_dir=baseline,
        challenger_dir=challenger,
        split="holdout",
        bootstrap_iterations=1000,
    )
    assert report["decision"] == "PROMOTE"
    assert report["paired_bootstrap_final_delta"]["lower_95"] > 0
    assert report["strict_span_type"]["challenger"]["f1"] == 1.0


def test_missing_annotations_cannot_promote(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "1.txt").write_text("đau", encoding="utf-8")
    from airace.blind_eval import corpus_fingerprint

    fingerprint, rows = corpus_fingerprint(input_dir)
    manifest = {
        "corpus_sha256": fingerprint,
        "records": [{**rows[0], "split": "holdout", "stratum": 1}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = evaluate_blind_challenger(
        input_dir=input_dir,
        manifest_path=manifest_path,
        labels_path=tmp_path / "missing.jsonl",
        baseline_dir=tmp_path / "baseline",
        challenger_dir=tmp_path / "challenger",
        split="holdout",
        bootstrap_iterations=10,
    )
    assert report["decision"] == "INCOMPLETE_ANNOTATIONS"

