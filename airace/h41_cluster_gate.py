"""Prediction-blind statistical audit for the H41 repeated-passage gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .metrics import score_entities
from .passage_annotation import load_labels, validate_annotation_file
from .schema import Entity, entities_from_json
from .validator import validate_entities


SEED = 424241
CLUSTER_SIZES = np.asarray([4, 4, 4, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2])
STRATA = (
    ("high", np.arange(0, 3)),
    ("middle", np.arange(3, 8)),
    ("low", np.arange(8, 15)),
)


def _lower_percentile(samples: np.ndarray) -> np.ndarray:
    """Match the repository's registered order-statistic percentile rule."""
    iterations = samples.shape[1]
    index = int(0.025 * (iterations - 1))
    return np.partition(samples, index, axis=1)[:, index]


def stratified_cluster_bootstrap_interval(
    passage_deltas: Iterable[float],
    stratum_ids: Iterable[str],
    *,
    iterations: int = 10_000,
    seed: int = SEED,
) -> dict[str, Any]:
    """Bootstrap unique passages within their frozen selection strata."""
    values = np.asarray(list(passage_deltas), dtype=np.float64)
    labels = np.asarray(list(stratum_ids), dtype=object)
    if len(values) == 0 or len(values) != len(labels):
        raise ValueError("passage deltas and strata must have equal non-zero length")
    rng = np.random.default_rng(seed)
    samples = np.zeros(iterations, dtype=np.float64)
    strata_report: dict[str, dict[str, float | int]] = {}
    for name in ("high", "middle", "low"):
        group = values[labels == name]
        if not len(group):
            raise ValueError(f"missing frozen stratum: {name}")
        indices = rng.integers(0, len(group), size=(iterations, len(group)))
        samples += group[indices].mean(axis=1) * (len(group) / len(values))
        strata_report[name] = {
            "passages": int(len(group)),
            "mean": round(float(group.mean()), 6),
        }
    ordered = np.sort(samples)
    lo = ordered[int(0.025 * (iterations - 1))]
    hi = ordered[int(0.975 * (iterations - 1))]
    return {
        "iterations": iterations,
        "seed": seed,
        "independent_passages": int(len(values)),
        "mean": round(float(values.mean()), 6),
        "lower_95": round(float(lo), 6),
        "upper_95": round(float(hi), 6),
        "strata": strata_report,
    }


def _prediction_entities(
    root: Path,
    input_root: Path,
    record_id: str,
    cache: dict[tuple[Path, str], list[Entity]],
) -> list[Entity]:
    key = (root, record_id)
    if key not in cache:
        raw = (input_root / f"{record_id}.txt").read_text(encoding="utf-8")
        path = root / f"{record_id}.json"
        values = entities_from_json(json.loads(path.read_text(encoding="utf-8")))
        validate_entities(values, raw)
        cache[key] = values
    return cache[key]


def _local_predictions(
    entities: Iterable[Entity], occurrence_start: int, occurrence_end: int
) -> tuple[list[Entity], int]:
    local: list[Entity] = []
    crossing = 0
    for entity in entities:
        start, end = entity.position
        if end <= occurrence_start or start >= occurrence_end:
            continue
        if start < occurrence_start or end > occurrence_end:
            crossing += 1
        local.append(
            Entity(
                text=entity.text,
                type=entity.type,
                assertions=list(entity.assertions),
                position=(start - occurrence_start, end - occurrence_start),
                candidates=list(entity.candidates or []) if entity.candidates is not None else None,
            )
        )
    return local, crossing


def _gold_for_occurrence(label: dict[str, Any], occurrence: dict[str, Any]) -> list[Entity]:
    assertion_map = {
        int(row["entity_index"]): list(row.get("assertions", []))
        for row in label.get("occurrence_assertions", [])
        if str(row["record_id"]) == str(occurrence["record_id"])
        and list(row["occurrence_position"]) == list(occurrence["position"])
    }
    values: list[Entity] = []
    for index, row in enumerate(label.get("entities", [])):
        entity = Entity.from_dict(row)
        entity.assertions = assertion_map.get(index, [])
        values.append(entity)
    return values


def _strict_prf(gold: set[tuple[Any, ...]], predicted: set[tuple[Any, ...]]) -> dict[str, Any]:
    true_positive = len(gold & predicted)
    precision = true_positive / len(predicted) if predicted else float(not gold)
    recall = true_positive / len(gold) if gold else float(not predicted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "tp": true_positive,
        "fp": len(predicted - gold),
        "fn": len(gold - predicted),
    }


def evaluate_h41_passage_challenger(
    *,
    input_dir: str | Path,
    manifest_path: str | Path,
    labels_path: str | Path,
    baseline_dir: str | Path,
    challenger_dir: str | Path,
    split: str = "holdout",
    bootstrap_iterations: int = 10_000,
    seed: int = SEED,
) -> dict[str, Any]:
    """Evaluate H41 only inside labeled passage windows with passage-level inference."""
    manifest_path = Path(manifest_path)
    labels_path = Path(labels_path)
    validation = validate_annotation_file(
        manifest_path, labels_path, require_complete=True
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = load_labels(labels_path)
    passages = [row for row in manifest["passages"] if row.get("split") == split]
    if not passages:
        raise ValueError(f"no passages for split {split!r}")

    input_root = Path(input_dir)
    roots = {"baseline": Path(baseline_dir), "challenger": Path(challenger_dir)}
    cache: dict[tuple[Path, str], list[Entity]] = {}
    strict_gold: set[tuple[Any, ...]] = set()
    strict_prediction = {"baseline": set(), "challenger": set()}
    per_passage: list[dict[str, Any]] = []
    crossing_counts = {"baseline": 0, "challenger": 0}

    for passage in passages:
        label = labels[passage["passage_id"]]
        occurrence_rows: list[dict[str, Any]] = []
        for occurrence in passage["occurrences"]:
            gold = _gold_for_occurrence(label, occurrence)
            occurrence_key = (
                passage["passage_id"],
                str(occurrence["record_id"]),
                int(occurrence["position"][0]),
            )
            strict_gold.update(
                (*occurrence_key, *entity.position, entity.type) for entity in gold
            )
            side_scores: dict[str, dict[str, float]] = {}
            for side, root in roots.items():
                predictions = _prediction_entities(
                    root, input_root, str(occurrence["record_id"]), cache
                )
                local, crossing = _local_predictions(
                    predictions, *[int(value) for value in occurrence["position"]]
                )
                crossing_counts[side] += crossing
                strict_prediction[side].update(
                    (*occurrence_key, *entity.position, entity.type) for entity in local
                )
                side_scores[side] = score_entities(gold, local)
            occurrence_rows.append(
                {
                    "record_id": str(occurrence["record_id"]),
                    "position": occurrence["position"],
                    "baseline": side_scores["baseline"],
                    "challenger": side_scores["challenger"],
                }
            )

        passage_scores: dict[str, dict[str, float]] = {}
        for side in ("baseline", "challenger"):
            passage_scores[side] = {
                metric: float(np.mean([row[side][metric] for row in occurrence_rows]))
                for metric in ("text_score", "assertions_score", "candidates_score", "final_score")
            }
        delta = {
            metric: passage_scores["challenger"][metric] - passage_scores["baseline"][metric]
            for metric in passage_scores["baseline"]
        }
        per_passage.append(
            {
                "passage_id": passage["passage_id"],
                "stratum": passage["stratum"],
                "occurrences": len(occurrence_rows),
                "baseline": passage_scores["baseline"],
                "challenger": passage_scores["challenger"],
                "delta": delta,
                "per_occurrence": occurrence_rows,
            }
        )

    mean_delta = {
        metric: round(float(np.mean([row["delta"][metric] for row in per_passage])), 6)
        for metric in ("text_score", "assertions_score", "candidates_score", "final_score")
    }
    interval = stratified_cluster_bootstrap_interval(
        [row["delta"]["final_score"] for row in per_passage],
        [row["stratum"] for row in per_passage],
        iterations=bootstrap_iterations,
        seed=seed,
    )
    strict = {
        side: _strict_prf(strict_gold, strict_prediction[side])
        for side in ("baseline", "challenger")
    }
    all_occurrence_deltas = [
        occurrence["challenger"]["final_score"] - occurrence["baseline"]["final_score"]
        for passage in per_passage
        for occurrence in passage["per_occurrence"]
    ]
    checks = {
        "bootstrap_lower_bound_positive": interval["lower_95"] > 0,
        "strict_span_type_f1_improves": strict["challenger"]["f1"] > strict["baseline"]["f1"],
        "assertion_floor": mean_delta["assertions_score"] >= -0.01,
        "candidate_floor": mean_delta["candidates_score"] >= -0.01,
        "no_boundary_crossing_predictions": not any(crossing_counts.values()),
    }
    return {
        "hypothesis": "H41_repeated_passage_blind_annotation",
        "split": split,
        "annotation_validation": validation,
        "independent_passages": len(per_passage),
        "descriptive_occurrences": len(all_occurrence_deltas),
        "primary_estimand": "unweighted mean over unique passages",
        "primary_interval": interval,
        "mean_delta": mean_delta,
        "strict_span_type": strict,
        "boundary_crossing_predictions": crossing_counts,
        "descriptive_occurrence_weighted_final_delta": round(
            float(np.mean(all_occurrence_deltas)), 6
        ),
        "checks": checks,
        "decision": "PROMOTE" if split == "holdout" and all(checks.values()) else (
            "DEVELOPMENT_ONLY" if split != "holdout" else "DO_NOT_PROMOTE"
        ),
        "per_passage": per_passage,
    }


def _simulate_batch(
    rng: np.random.Generator,
    rho: float,
    batch_size: int,
    bootstrap_iterations: int,
) -> tuple[int, int]:
    cluster_effects = rng.standard_normal((batch_size, len(CLUSTER_SIZES)))
    occurrence_noise = rng.standard_normal((batch_size, int(CLUSTER_SIZES.sum())))
    flat = np.empty_like(occurrence_noise)
    cluster_means = np.empty_like(cluster_effects)
    cursor = 0
    for cluster_index, size in enumerate(CLUSTER_SIZES):
        width = int(size)
        values = (
            math.sqrt(rho) * cluster_effects[:, cluster_index, None]
            + math.sqrt(1.0 - rho) * occurrence_noise[:, cursor : cursor + width]
        )
        flat[:, cursor : cursor + width] = values
        cluster_means[:, cluster_index] = values.mean(axis=1)
        cursor += width

    naive_indices = rng.integers(
        0,
        flat.shape[1],
        size=(batch_size, bootstrap_iterations, flat.shape[1]),
        dtype=np.int16,
    )
    naive_samples = np.take_along_axis(flat[:, None, :], naive_indices, axis=2).mean(axis=2)
    naive_promotions = int(np.count_nonzero(_lower_percentile(naive_samples) > 0))

    cluster_samples = np.zeros((batch_size, bootstrap_iterations), dtype=np.float64)
    for _, positions in STRATA:
        group = cluster_means[:, positions]
        indices = rng.integers(
            0,
            group.shape[1],
            size=(batch_size, bootstrap_iterations, group.shape[1]),
            dtype=np.int16,
        )
        means = np.take_along_axis(group[:, None, :], indices, axis=2).mean(axis=2)
        cluster_samples += means * (group.shape[1] / len(CLUSTER_SIZES))
    cluster_promotions = int(np.count_nonzero(_lower_percentile(cluster_samples) > 0))
    return naive_promotions, cluster_promotions


def run_null_simulation(
    *,
    replications: int = 10_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Measure false-promotion rates under the preregistered correlated null."""
    if replications <= 0 or bootstrap_iterations <= 0 or batch_size <= 0:
        raise ValueError("simulation sizes must be positive")
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float]] = []
    for rho in (0.0, 0.3, 0.6, 0.9):
        naive = cluster = completed = 0
        while completed < replications:
            current = min(batch_size, replications - completed)
            batch_naive, batch_cluster = _simulate_batch(
                rng, rho, current, bootstrap_iterations
            )
            naive += batch_naive
            cluster += batch_cluster
            completed += current
        naive_rate = naive / replications
        cluster_rate = cluster / replications
        rows.append(
            {
                "rho": rho,
                "naive_false_promotion_rate": round(naive_rate, 6),
                "cluster_false_promotion_rate": round(cluster_rate, 6),
                "absolute_rate_reduction": round(naive_rate - cluster_rate, 6),
            }
        )

    indexed = {row["rho"]: row for row in rows}
    gates = {
        "rho_0_6_reduction_at_least_0_03": indexed[0.6]["absolute_rate_reduction"] >= 0.03,
        "rho_0_9_reduction_at_least_0_08": indexed[0.9]["absolute_rate_reduction"] >= 0.08,
    }
    report: dict[str, Any] = {
        "hypothesis": "H42_h41_cluster_gate",
        "seed": seed,
        "replications": replications,
        "bootstrap_iterations_per_replication": bootstrap_iterations,
        "cluster_sizes": CLUSTER_SIZES.tolist(),
        "independent_passages": int(len(CLUSTER_SIZES)),
        "descriptive_occurrences": int(CLUSTER_SIZES.sum()),
        "results": rows,
        "registered_gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    report["content_sha256_before_hash_field"] = hashlib.sha256(canonical).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/H42_h41_cluster_gate/results/null_simulation.json"),
    )
    parser.add_argument("--replications", type=int, default=10_000)
    parser.add_argument("--bootstrap-iterations", type=int, default=1_000)
    args = parser.parse_args()
    report = run_null_simulation(
        replications=args.replications,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
