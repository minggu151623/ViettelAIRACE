"""Prediction-blind power analysis for the H41 passage-clustered gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SEED = 4801
EFFECTS = (0.0, 0.25, 0.5, 0.75, 1.0)
BASE_STRATA = (3, 5, 7)


def _lower_percentile(samples: np.ndarray) -> np.ndarray:
    index = int(0.025 * (samples.shape[1] - 1))
    return np.partition(samples, index, axis=1)[:, index]


def simulate_null_lower_bounds(
    *,
    multiplier: int,
    replications: int = 5_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
    batch_size: int = 25,
) -> np.ndarray:
    """Return bootstrap lower bounds at d=0; adding d shifts every bound by d."""

    if multiplier < 1 or replications < 1 or bootstrap_iterations < 1:
        raise ValueError("simulation sizes must be positive")
    rng = np.random.default_rng(seed + 1009 * multiplier)
    group_sizes = tuple(value * multiplier for value in BASE_STRATA)
    total = sum(group_sizes)
    output: list[np.ndarray] = []
    for offset in range(0, replications, batch_size):
        count = min(batch_size, replications - offset)
        values = rng.standard_normal((count, total))
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
            sampled = np.take_along_axis(group[:, None, :], indices, axis=2).mean(axis=2)
            samples += sampled * (group_size / total)
            cursor += group_size
        output.append(_lower_percentile(samples))
    return np.concatenate(output)


def power_curve(
    *,
    effects: Iterable[float] = EFFECTS,
    multipliers: Iterable[int] = (1, 2, 3, 4),
    replications: int = 5_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
) -> dict[str, Any]:
    effect_values = tuple(float(value) for value in effects)
    rows = []
    for multiplier in multipliers:
        bounds = simulate_null_lower_bounds(
            multiplier=int(multiplier),
            replications=replications,
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
        )
        rates = {
            str(effect): float(np.mean(bounds + effect > 0)) for effect in effect_values
        }
        rows.append(
            {
                "multiplier": int(multiplier),
                "passages": int(15 * multiplier),
                "strata_counts": {
                    "high": int(3 * multiplier),
                    "middle": int(5 * multiplier),
                    "low": int(7 * multiplier),
                },
                "promotion_rates": rates,
            }
        )

    smallest_n = {}
    for effect in effect_values[1:]:
        eligible = [
            row["passages"]
            for row in rows
            if row["promotion_rates"][str(effect)] >= 0.80
        ]
        smallest_n[str(effect)] = min(eligible) if eligible else None
    mde = {}
    for row in rows:
        eligible_effects = [
            effect
            for effect in effect_values[1:]
            if row["promotion_rates"][str(effect)] >= 0.80
        ]
        mde[str(row["passages"])] = min(eligible_effects) if eligible_effects else None

    frozen = rows[0]
    type_i = frozen["promotion_rates"]["0.0"]
    moderate_power = frozen["promotion_rates"]["0.5"]
    gates = {
        "frozen_15_passage_type_i_between_0_03_and_0_07": 0.03 <= type_i <= 0.07,
        "frozen_15_passage_power_at_d_0_5_at_least_0_80": moderate_power >= 0.80,
    }
    return {
        "hypothesis": "H48_h41_power_curve",
        "seed": seed,
        "replications": replications,
        "bootstrap_iterations_per_replication": bootstrap_iterations,
        "standardized_effects": list(effect_values),
        "results": rows,
        "smallest_passage_count_at_80_percent_power": smallest_n,
        "grid_minimum_detectable_effect_at_80_percent_power": mde,
        "adequacy_gates": gates,
        "decision": "ADEQUATE_FOR_MODERATE_EFFECT" if all(gates.values()) else "VALID_BUT_UNDERPOWERED_FOR_MODERATE_EFFECT",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "artifact_policy": "NO_LABEL_OR_QUEUE_OR_ZIP_CHANGE",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report = dict(report)
    report["content_sha256_before_hash_field"] = hashlib.sha256(canonical.encode()).hexdigest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_report(power_curve(), args.output)


if __name__ == "__main__":
    main()
