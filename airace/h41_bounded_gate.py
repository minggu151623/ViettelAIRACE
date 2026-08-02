"""Finite-sample bounded confidence gates for H41 passage deltas."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .h41_power import BASE_STRATA


SEED = 5101
ALPHA = 0.025
FAMILIES = (
    "symmetric_uniform",
    "rademacher",
    "beta_right_skew",
    "beta_left_skew",
    "rare_two_point",
)
FAMILY_SEED_OFFSETS = {
    "symmetric_uniform": 101,
    "rademacher": 211,
    "beta_right_skew": 307,
    "beta_left_skew": 401,
    "rare_two_point": 503,
}


def bounded_noise(
    rng: np.random.Generator, family: str, shape: tuple[int, ...]
) -> tuple[np.ndarray, float]:
    """Return centered bounded noise and its frozen theoretical standard deviation."""

    if family == "symmetric_uniform":
        return rng.uniform(-0.5, 0.5, size=shape), 0.5 / math.sqrt(3)
    if family == "rademacher":
        return rng.choice(np.asarray([-0.5, 0.5]), size=shape), 0.5
    if family in {"beta_right_skew", "beta_left_skew"}:
        values = (rng.beta(1, 4, size=shape) - 0.2) * 0.625
        if family == "beta_left_skew":
            values = -values
        return values, math.sqrt(4 / (25 * 6)) * 0.625
    if family == "rare_two_point":
        values = (rng.binomial(1, 0.2, size=shape) - 0.2) * 0.625
        return values, math.sqrt(0.2 * 0.8) * 0.625
    raise ValueError(f"unknown bounded family: {family}")


def hoeffding_lower(values: np.ndarray, *, alpha: float = ALPHA) -> np.ndarray:
    """One-sided lower mean bound for independent values in [-1, 1]."""

    n = values.shape[1]
    penalty = 2 * math.sqrt(math.log(1 / alpha) / (2 * n))
    return values.mean(axis=1) - penalty


def stratified_empirical_bernstein_lower(
    values: np.ndarray,
    group_sizes: tuple[int, ...],
    *,
    alpha: float = ALPHA,
) -> np.ndarray:
    """Union-bound Maurer-Pontil lower bound across frozen strata."""

    if values.shape[1] != sum(group_sizes):
        raise ValueError("group sizes do not match passage matrix")
    delta_h = alpha / len(group_sizes)
    log_term = math.log(2 / delta_h)
    total = sum(group_sizes)
    lower = np.zeros(values.shape[0], dtype=np.float64)
    cursor = 0
    for size in group_sizes:
        group = (values[:, cursor:cursor + size] + 1) / 2
        variance = group.var(axis=1, ddof=1)
        penalty = np.sqrt(2 * variance * log_term / size) + (
            7 * log_term / (3 * (size - 1))
        )
        lower += (size / total) * (2 * (group.mean(axis=1) - penalty) - 1)
        cursor += size
    return lower


def analytic_penalties(multiplier: int, *, alpha: float = ALPHA) -> dict[str, Any]:
    group_sizes = tuple(value * multiplier for value in BASE_STRATA)
    total = sum(group_sizes)
    hoeffding = 2 * math.sqrt(math.log(1 / alpha) / (2 * total))
    delta_h = alpha / len(group_sizes)
    log_term = math.log(2 / delta_h)
    eb_zero_variance = sum(
        (size / total) * 2 * (7 * log_term / (3 * (size - 1)))
        for size in group_sizes
    )
    return {
        "passages": total,
        "hoeffding_penalty": hoeffding,
        "empirical_bernstein_zero_variance_penalty": eb_zero_variance,
        "strata_counts": list(group_sizes),
    }


def evaluate_bounded_gates(
    *,
    families: Iterable[str] = FAMILIES,
    effects: Iterable[float] = (0.0, 0.5, 0.75, 1.0),
    multipliers: Iterable[int] = (1, 2, 3, 4),
    replications: int = 10_000,
    seed: int = SEED,
) -> dict[str, Any]:
    family_values = tuple(families)
    effect_values = tuple(float(value) for value in effects)
    multiplier_values = tuple(int(value) for value in multipliers)
    rows: list[dict[str, Any]] = []
    for family in family_values:
        for multiplier in multiplier_values:
            group_sizes = tuple(value * multiplier for value in BASE_STRATA)
            n = sum(group_sizes)
            rng = np.random.default_rng(
                seed + FAMILY_SEED_OFFSETS[family] + 1009 * multiplier
            )
            noise, standard_deviation = bounded_noise(rng, family, (replications, n))
            for method, lower in (
                ("global_hoeffding", hoeffding_lower(noise)),
                (
                    "stratified_empirical_bernstein",
                    stratified_empirical_bernstein_lower(noise, group_sizes),
                ),
            ):
                rows.append(
                    {
                        "noise_family": family,
                        "passages": n,
                        "method": method,
                        "theoretical_noise_sd": standard_deviation,
                        "promotion_rates": {
                            str(effect): float(
                                np.mean(lower + effect * standard_deviation > 0)
                            )
                            for effect in effect_values
                        },
                    }
                )

    methods = ("global_hoeffding", "stratified_empirical_bernstein")
    envelopes: dict[str, dict[str, Any]] = {}
    for multiplier in multiplier_values:
        n = 15 * multiplier
        envelopes[str(n)] = {}
        for method in methods:
            selected = [
                row for row in rows if row["passages"] == n and row["method"] == method
            ]
            envelopes[str(n)][method] = {
                "maximum_type_i": max(row["promotion_rates"]["0.0"] for row in selected),
                "minimum_power_d_0_5": min(row["promotion_rates"]["0.5"] for row in selected),
                "minimum_power_d_0_75": min(row["promotion_rates"]["0.75"] for row in selected),
                "minimum_power_d_1_0": min(row["promotion_rates"]["1.0"] for row in selected),
            }

    gates = {
        "maximum_type_i_at_most_0_025_for_both_methods": all(
            envelopes[str(15 * multiplier)][method]["maximum_type_i"] <= 0.025
            for multiplier in multiplier_values
            for method in methods
        ),
        "one_method_has_n15_worst_power_at_least_0_50_at_d_0_75": any(
            envelopes["15"][method]["minimum_power_d_0_75"] >= 0.50
            for method in methods
        ),
        "one_method_has_n60_worst_power_at_least_0_80_at_d_0_5": any(
            envelopes["60"][method]["minimum_power_d_0_5"] >= 0.80
            for method in methods
        ),
    }
    return {
        "hypothesis": "H51_h41_bounded_gate",
        "seed": seed,
        "replications": replications,
        "standardized_effects": list(effect_values),
        "bounded_noise_families": list(family_values),
        "analytic_penalties": [analytic_penalties(value) for value in multiplier_values],
        "results": rows,
        "envelopes": envelopes,
        "usefulness_gates": gates,
        "decision": "INSTALL_BOUNDED_GATE" if all(gates.values()) else "VALID_BUT_VACUOUS",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "artifact_policy": "NO_LABEL_PREDICTION_QUEUE_EVALUATOR_OR_ZIP_CHANGE",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    output = dict(report)
    output["content_sha256_before_hash_field"] = hashlib.sha256(canonical.encode()).hexdigest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_report(evaluate_bounded_gates(), args.output)


if __name__ == "__main__":
    main()
