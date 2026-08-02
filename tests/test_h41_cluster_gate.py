import json
from pathlib import Path

import pytest

from airace.h41_cluster_gate import (
    evaluate_h41_passage_challenger,
    run_null_simulation,
    stratified_cluster_bootstrap_interval,
)


def test_stratified_cluster_bootstrap_is_deterministic_and_passage_based():
    deltas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    strata = ["high", "high", "middle", "middle", "low", "low"]
    first = stratified_cluster_bootstrap_interval(
        deltas, strata, iterations=500, seed=17
    )
    second = stratified_cluster_bootstrap_interval(
        deltas, strata, iterations=500, seed=17
    )
    assert first == second
    assert first["independent_passages"] == 6
    assert first["mean"] == pytest.approx(0.35)
    assert set(first["strata"]) == {"high", "middle", "low"}


def test_stratified_cluster_bootstrap_requires_every_frozen_stratum():
    with pytest.raises(ValueError, match="missing frozen stratum"):
        stratified_cluster_bootstrap_interval(
            [0.1, 0.2], ["high", "middle"], iterations=10
        )


def test_small_null_simulation_is_byte_deterministic():
    first = run_null_simulation(
        replications=20, bootstrap_iterations=50, seed=99, batch_size=7
    )
    second = run_null_simulation(
        replications=20, bootstrap_iterations=50, seed=99, batch_size=7
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["independent_passages"] == 15
    assert first["descriptive_occurrences"] == 41
    assert [row["rho"] for row in first["results"]] == [0.0, 0.3, 0.6, 0.9]


def test_h41_evaluator_scores_only_passage_windows_and_clusters(tmp_path: Path):
    input_dir = tmp_path / "input"
    baseline_dir = tmp_path / "baseline"
    challenger_dir = tmp_path / "challenger"
    for directory in (input_dir, baseline_dir, challenger_dir):
        directory.mkdir()
    passages = []
    labels = []
    for index, stratum in enumerate(("high", "middle", "low"), 1):
        text = f"ngoài đau{index} ngoài"
        mention = f"đau{index}"
        start = text.index(mention)
        end = start + len(mention)
        record_id = str(index)
        (input_dir / f"{record_id}.txt").write_text(text, encoding="utf-8")
        (baseline_dir / f"{record_id}.json").write_text("[]", encoding="utf-8")
        entity = {
            "text": mention,
            "type": "TRIỆU_CHỨNG",
            "assertions": [],
            "position": [start, end],
        }
        (challenger_dir / f"{record_id}.json").write_text(
            json.dumps([entity], ensure_ascii=False), encoding="utf-8"
        )
        import hashlib

        passage_id = hashlib.sha256(mention.encode()).hexdigest()
        passages.append(
            {
                "passage_id": passage_id,
                "text": mention,
                "split": "holdout",
                "stratum": stratum,
                "occurrences": [{"record_id": record_id, "position": [start, end]}],
            }
        )
        labels.append(
            {
                "passage_id": passage_id,
                "passage_sha256": passage_id,
                "reviewer_id": "adjudicated",
                "entities": [{k: v for k, v in entity.items() if k != "assertions"} | {"position": [0, len(mention)]}],
                "occurrence_assertions": [
                    {
                        "record_id": record_id,
                        "occurrence_position": [start, end],
                        "entity_index": 0,
                        "assertions": [],
                    }
                ],
                "stage_a_reviewed": True,
                "stage_b_reviewed": True,
            }
        )
    manifest_path = tmp_path / "manifest.json"
    labels_path = tmp_path / "labels.jsonl"
    manifest_path.write_text(json.dumps({"passages": passages}), encoding="utf-8")
    labels_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in labels) + "\n",
        encoding="utf-8",
    )
    report = evaluate_h41_passage_challenger(
        input_dir=input_dir,
        manifest_path=manifest_path,
        labels_path=labels_path,
        baseline_dir=baseline_dir,
        challenger_dir=challenger_dir,
        bootstrap_iterations=500,
    )
    assert report["independent_passages"] == 3
    assert report["descriptive_occurrences"] == 3
    assert report["primary_interval"]["lower_95"] > 0
    assert report["strict_span_type"]["challenger"]["f1"] == 1.0
    assert report["decision"] == "PROMOTE"
