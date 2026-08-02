from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


KS = tuple(range(1, 11))
TYPES = ("CHẨN_ĐOÁN", "THUỐC")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jaccard(predicted: list[str], gold: list[str]) -> float:
    predicted_set, gold_set = set(predicted), set(gold)
    union = predicted_set | gold_set
    return len(predicted_set & gold_set) / len(union) if union else 1.0


def row_scores(row: dict[str, Any]) -> dict[int, float]:
    return {k: jaccard(row["top10"][:k], row["gold"]) for k in KS}


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def curve(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {str(k): mean([row_scores(row)[k] for row in rows]) for k in KS}


def select_k(rows: list[dict[str, Any]]) -> int:
    values = curve(rows)
    return min(KS, key=lambda k: (-values[str(k)], k))


def policy_score(row: dict[str, Any], policy: dict[str, int]) -> float:
    k = policy.get(row["type"], policy.get("global", 1))
    return row_scores(row)[k]


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def paired_bootstrap(
    baseline: list[float], challenger: list[float], *, seed: int, resamples: int
) -> dict[str, float | int]:
    if len(baseline) != len(challenger) or not baseline:
        raise ValueError("paired bootstrap requires equal non-empty vectors")
    rng = random.Random(seed)
    n = len(baseline)
    deltas = []
    for _ in range(resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        deltas.append(mean([challenger[i] - baseline[i] for i in indices]))
    return {
        "seed": seed,
        "resamples": resamples,
        "point_delta": mean(challenger) - mean(baseline),
        "ci95_low": percentile(deltas, 0.025),
        "ci95_high": percentile(deltas, 0.975),
    }


def build_report(
    ranking_path: str | Path,
    dataset_path: str | Path,
    *,
    expected_ranking_sha256: str,
    expected_dataset_sha256: str,
    bootstrap_seed: int = 4501,
    bootstrap_resamples: int = 10_000,
) -> dict[str, Any]:
    ranking_hash = sha256_file(ranking_path)
    dataset_hash = sha256_file(dataset_path)
    if ranking_hash != expected_ranking_sha256:
        raise ValueError("ranking report SHA-256 mismatch")
    if dataset_hash != expected_dataset_sha256:
        raise ValueError("dataset SHA-256 mismatch")

    ranking = json.loads(Path(ranking_path).read_text(encoding="utf-8"))
    rows = ranking["predictions"]
    if len(rows) != 518 or any(len(row["top10"]) != 10 for row in rows):
        raise ValueError("frozen H24 census mismatch")
    folds = {fold: [row for row in rows if row["fold"] == fold] for fold in ("train", "dev", "test")}
    if {fold: len(values) for fold, values in folds.items()} != {"train": 426, "dev": 36, "test": 56}:
        raise ValueError("frozen split mismatch")

    global_k = select_k(folds["dev"])
    type_k = {kind: select_k([row for row in folds["dev"] if row["type"] == kind]) for kind in TYPES}
    global_policy = {"global": global_k}
    baseline_policy = {"global": 1}

    fold_curves: dict[str, Any] = {}
    for fold, fold_rows in folds.items():
        fold_curves[fold] = {
            "all": curve(fold_rows),
            "by_type": {kind: curve([row for row in fold_rows if row["type"] == kind]) for kind in TYPES},
        }

    test = folds["test"]
    baseline_scores = [policy_score(row, baseline_policy) for row in test]
    global_scores = [policy_score(row, global_policy) for row in test]
    type_scores = [policy_score(row, type_k) for row in test]
    oracle_scores = [max(row_scores(row).values()) for row in test]

    type_test_deltas = {}
    for kind in TYPES:
        selected = [row for row in test if row["type"] == kind]
        base = mean([policy_score(row, baseline_policy) for row in selected])
        challenger = mean([policy_score(row, type_k) for row in selected])
        type_test_deltas[kind] = challenger - base

    bootstrap = paired_bootstrap(
        baseline_scores,
        type_scores,
        seed=bootstrap_seed,
        resamples=bootstrap_resamples,
    )
    gates = {
        "primary_test_delta_at_least_0_02": bootstrap["point_delta"] >= 0.02,
        "primary_95_percent_bootstrap_lower_bound_above_0": bootstrap["ci95_low"] > 0,
        "neither_entity_type_test_delta_below_minus_0_01": min(type_test_deltas.values()) >= -0.01,
        "input_hashes_match": True,
    }
    return {
        "hypothesis": "H45_jaccard_cardinality_audit",
        "label_warning": "weak_pseudo_labels_not_organizer_ground_truth",
        "inputs": {
            "ranking_sha256": ranking_hash,
            "dataset_sha256": dataset_hash,
            "fold_counts": {fold: len(values) for fold, values in folds.items()},
        },
        "selection": {"global_k": global_k, "type_k": type_k, "tie_break": "smaller_k"},
        "jaccard_curves": fold_curves,
        "test": {
            "singleton_top1": mean(baseline_scores),
            "global_dev_selected": mean(global_scores),
            "type_specific_dev_selected": mean(type_scores),
            "per_row_oracle": mean(oracle_scores),
            "type_specific_delta": mean(type_scores) - mean(baseline_scores),
            "by_type_delta": type_test_deltas,
        },
        "paired_bootstrap": bootstrap,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "REJECT",
        "artifact_policy": "NO_SUBMISSION_ZIP",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranking", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--ranking-sha256", required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(
        args.ranking,
        args.dataset,
        expected_ranking_sha256=args.ranking_sha256,
        expected_dataset_sha256=args.dataset_sha256,
    )
    write_report(report, args.output)


if __name__ == "__main__":
    main()
