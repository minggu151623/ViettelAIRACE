"""Distributional robustness audit for the H41 passage-level power curve."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .h41_power import BASE_STRATA, EFFECTS, _lower_percentile


SEED = 4901
FAMILIES = ("normal", "student_t3", "right_skew", "left_skew", "rademacher")
FAMILY_SEED_OFFSETS = {
    "normal": 101,
    "student_t3": 211,
    "right_skew": 307,
    "left_skew": 401,
    "rademacher": 503,
}


def draw_noise(rng: np.random.Generator, family: str, shape: tuple[int, ...]) -> np.ndarray:
    """Draw theoretically mean-zero, unit-variance noise from a frozen family."""

    if family == "normal":
        return rng.standard_normal(shape)
    if family == "student_t3":
        return rng.standard_t(3, size=shape) / math.sqrt(3)
    if family == "right_skew":
        return rng.exponential(1, size=shape) - 1
    if family == "left_skew":
        return 1 - rng.exponential(1, size=shape)
    if family == "rademacher":
        return rng.choice(np.asarray([-1.0, 1.0]), size=shape)
    raise ValueError(f"unknown noise family: {family}")


def simulate_lower_bounds(
    *,
    family: str,
    multiplier: int,
    replications: int = 5_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
    batch_size: int = 25,
) -> np.ndarray:
    """Simulate null bootstrap lower bounds; adding d shifts each bound by d."""

    if family not in FAMILY_SEED_OFFSETS:
        raise ValueError(f"unknown noise family: {family}")
    if multiplier < 1 or replications < 1 or bootstrap_iterations < 1:
        raise ValueError("simulation sizes must be positive")
    rng = np.random.default_rng(
        seed + FAMILY_SEED_OFFSETS[family] + 1009 * multiplier
    )
    group_sizes = tuple(value * multiplier for value in BASE_STRATA)
    total = sum(group_sizes)
    output: list[np.ndarray] = []
    for offset in range(0, replications, batch_size):
        count = min(batch_size, replications - offset)
        values = draw_noise(rng, family, (count, total))
        samples = np.zeros((count, bootstrap_iterations), dtype=np.float64)
        cursor = 0
        for group_size in group_sizes:
            group = values[:, cursor:cursor + group_size]
            indices = rng.integers(
                0,
                group_size,
                size=(count, bootstrap_iterations, group_size),
                dtype=np.int16,
            )
            sampled = np.take_along_axis(group[:, None, :], indices, axis=2)
            samples += sampled.mean(axis=2) * (group_size / total)
            cursor += group_size
        output.append(_lower_percentile(samples))
    return np.concatenate(output)


def robustness_envelope(
    *,
    families: Iterable[str] = FAMILIES,
    effects: Iterable[float] = (0.0, 0.5, 0.75),
    multipliers: Iterable[int] = (1, 2, 3, 4),
    replications: int = 5_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
) -> dict[str, Any]:
    family_values = tuple(families)
    effect_values = tuple(float(value) for value in effects)
    multiplier_values = tuple(int(value) for value in multipliers)
    rows: list[dict[str, Any]] = []
    for family in family_values:
        for multiplier in multiplier_values:
            bounds = simulate_lower_bounds(
                family=family,
                multiplier=multiplier,
                replications=replications,
                bootstrap_iterations=bootstrap_iterations,
                seed=seed,
            )
            rows.append(
                {
                    "noise_family": family,
                    "passages": 15 * multiplier,
                    "strata_counts": {
                        "high": 3 * multiplier,
                        "middle": 5 * multiplier,
                        "low": 7 * multiplier,
                    },
                    "promotion_rates": {
                        str(effect): float(np.mean(bounds + effect > 0))
                        for effect in effect_values
                    },
                }
            )

    by_n: dict[str, dict[str, Any]] = {}
    for multiplier in multiplier_values:
        passages = 15 * multiplier
        selected = [row for row in rows if row["passages"] == passages]
        by_n[str(passages)] = {
            "type_i_range": [
                min(row["promotion_rates"]["0.0"] for row in selected),
                max(row["promotion_rates"]["0.0"] for row in selected),
            ],
            "minimum_power": {
                str(effect): min(row["promotion_rates"][str(effect)] for row in selected)
                for effect in effect_values[1:]
            },
        }

    robust_n: dict[str, int | None] = {}
    for effect in effect_values[1:]:
        eligible = [
            int(passages)
            for passages, summary in by_n.items()
            if summary["minimum_power"][str(effect)] >= 0.80
        ]
        robust_n[str(effect)] = min(eligible) if eligible else None

    n15_type_i = by_n["15"]["type_i_range"]
    gates = {
        "every_15_passage_type_i_between_0_02_and_0_08": (
            n15_type_i[0] >= 0.02 and n15_type_i[1] <= 0.08
        ),
        "minimum_30_passage_power_at_d_0_5_at_least_0_70": (
            by_n["30"]["minimum_power"]["0.5"] >= 0.70
        ),
        "at_least_one_tested_n_reaches_0_80_power_at_d_0_5_in_every_family": (
            robust_n["0.5"] is not None
        ),
    }
    return {
        "hypothesis": "H49_h41_power_robustness",
        "seed": seed,
        "replications": replications,
        "bootstrap_iterations_per_replication": bootstrap_iterations,
        "noise_families": list(family_values),
        "standardized_effects": list(effect_values),
        "results": rows,
        "envelope_by_passage_count": by_n,
        "smallest_passage_count_at_80_percent_power_in_every_family": robust_n,
        "robustness_gates": gates,
        "decision": "ROBUST_QUALITATIVE_CONCLUSION" if all(gates.values()) else "DISTRIBUTION_SENSITIVE",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "artifact_policy": "NO_LABEL_PREDICTION_QUEUE_OR_ZIP_CHANGE",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    output = dict(report)
    output["content_sha256_before_hash_field"] = hashlib.sha256(canonical.encode()).hexdigest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_report(robustness_envelope(), args.output)


if __name__ == "__main__":
    main()
