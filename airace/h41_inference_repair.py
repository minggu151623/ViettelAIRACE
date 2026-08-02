"""Prediction-blind comparison of small-sample H41 inference repairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.stats import t as student_t

from .h41_power import BASE_STRATA
from .h41_power_robustness import FAMILY_SEED_OFFSETS, FAMILIES, draw_noise


SEED = 5001
METHODS = ("percentile", "stratified_welch_t", "bootstrap_t")


def _order_statistic(values: np.ndarray, probability: float) -> np.ndarray:
    index = int(probability * (values.shape[1] - 1))
    return np.partition(values, index, axis=1)[:, index]


def _stratified_summary(
    groups: list[np.ndarray], group_sizes: tuple[int, ...]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return weighted mean, standard error, and Welch-Satterthwaite df."""

    total = sum(group_sizes)
    mean = np.zeros(groups[0].shape[:-1], dtype=np.float64)
    variance = np.zeros_like(mean)
    denominator = np.zeros_like(mean)
    for group, size in zip(groups, group_sizes, strict=True):
        weight = size / total
        component = weight * weight * group.var(axis=-1, ddof=1) / size
        mean += weight * group.mean(axis=-1)
        variance += component
        denominator += component * component / (size - 1)
    standard_error = np.sqrt(variance)
    degrees = np.divide(
        variance * variance,
        denominator,
        out=np.full_like(variance, np.inf),
        where=denominator > 0,
    )
    return mean, standard_error, degrees


def simulate_method_lower_bounds(
    *,
    family: str,
    multiplier: int,
    replications: int = 5_000,
    bootstrap_iterations: int = 1_000,
    seed: int = SEED,
    batch_size: int = 25,
) -> tuple[dict[str, np.ndarray], float]:
    """Return null lower bounds for each method and bootstrap-t nonfinite rate."""

    if family not in FAMILY_SEED_OFFSETS:
        raise ValueError(f"unknown noise family: {family}")
    if multiplier < 1 or replications < 1 or bootstrap_iterations < 1:
        raise ValueError("simulation sizes must be positive")
    rng = np.random.default_rng(seed + FAMILY_SEED_OFFSETS[family] + 1009 * multiplier)
    group_sizes = tuple(value * multiplier for value in BASE_STRATA)
    total = sum(group_sizes)
    outputs: dict[str, list[np.ndarray]] = {method: [] for method in METHODS}
    nonfinite = 0

    for offset in range(0, replications, batch_size):
        count = min(batch_size, replications - offset)
        values = draw_noise(rng, family, (count, total))
        groups: list[np.ndarray] = []
        cursor = 0
        for size in group_sizes:
            groups.append(values[:, cursor:cursor + size])
            cursor += size
        observed_mean, observed_se, observed_df = _stratified_summary(groups, group_sizes)
        critical = student_t.ppf(0.975, observed_df)
        outputs["stratified_welch_t"].append(observed_mean - critical * observed_se)

        bootstrap_groups: list[np.ndarray] = []
        for group, size in zip(groups, group_sizes, strict=True):
            indices = rng.integers(
                0,
                size,
                size=(count, bootstrap_iterations, size),
                dtype=np.int16,
            )
            bootstrap_groups.append(
                np.take_along_axis(group[:, None, :], indices, axis=2)
            )
        bootstrap_mean, bootstrap_se, _ = _stratified_summary(
            bootstrap_groups, group_sizes
        )
        outputs["percentile"].append(_order_statistic(bootstrap_mean, 0.025))

        numerator = bootstrap_mean - observed_mean[:, None]
        statistic = np.divide(
            numerator,
            bootstrap_se,
            out=np.zeros_like(numerator),
            where=bootstrap_se > 0,
        )
        zero_se = bootstrap_se == 0
        statistic[zero_se & (numerator > 0)] = np.inf
        statistic[zero_se & (numerator < 0)] = -np.inf
        upper_t = _order_statistic(statistic, 0.975)
        bootstrap_t_lower = observed_mean - upper_t * observed_se
        nonfinite += int(np.count_nonzero(~np.isfinite(bootstrap_t_lower)))
        outputs["bootstrap_t"].append(bootstrap_t_lower)

    return (
        {method: np.concatenate(chunks) for method, chunks in outputs.items()},
        nonfinite / replications,
    )


def compare_methods(
    *,
    families: Iterable[str] = FAMILIES,
    effects: Iterable[float] = (0.0, 0.5, 0.75),
    multipliers: Iterable[int] = (1, 2, 3),
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
            bounds, nonfinite_rate = simulate_method_lower_bounds(
                family=family,
                multiplier=multiplier,
                replications=replications,
                bootstrap_iterations=bootstrap_iterations,
                seed=seed,
            )
            for method, lower in bounds.items():
                rows.append(
                    {
                        "noise_family": family,
                        "passages": 15 * multiplier,
                        "method": method,
                        "promotion_rates": {
                            str(effect): float(np.mean(lower + effect > 0))
                            for effect in effect_values
                        },
                        "nonfinite_replication_rate": (
                            nonfinite_rate if method == "bootstrap_t" else 0.0
                        ),
                    }
                )

    envelopes: dict[str, dict[str, dict[str, float]]] = {}
    for passages in (15 * value for value in multiplier_values):
        envelopes[str(passages)] = {}
        for method in METHODS:
            selected = [
                row for row in rows
                if row["passages"] == passages and row["method"] == method
            ]
            envelopes[str(passages)][method] = {
                "minimum_type_i": min(row["promotion_rates"]["0.0"] for row in selected),
                "maximum_type_i": max(row["promotion_rates"]["0.0"] for row in selected),
                "minimum_power_d_0_5": min(row["promotion_rates"]["0.5"] for row in selected),
                "minimum_power_d_0_75": min(row["promotion_rates"]["0.75"] for row in selected),
                "maximum_nonfinite_replication_rate": max(
                    row["nonfinite_replication_rate"] for row in selected
                ),
            }

    eligibility: dict[str, bool] = {}
    n15 = envelopes["15"]
    for method in METHODS:
        summary = n15[method]
        eligibility[method] = (
            summary["maximum_type_i"] <= 0.08
            and summary["minimum_type_i"] >= 0.01
            and summary["maximum_nonfinite_replication_rate"] <= 0.01
        )
    eligible = [method for method in METHODS if eligibility[method]]
    complexity = {"stratified_welch_t": 0, "bootstrap_t": 1, "percentile": 2}
    selected_method = None
    if eligible:
        best_power = max(n15[method]["minimum_power_d_0_5"] for method in eligible)
        tied = [
            method for method in eligible
            if best_power - n15[method]["minimum_power_d_0_5"] <= 0.005
        ]
        selected_method = min(tied, key=complexity.__getitem__)

    installed = False
    if selected_method is not None:
        installed = (
            n15["percentile"]["maximum_type_i"]
            - n15[selected_method]["maximum_type_i"] >= 0.02
            and n15[selected_method]["minimum_power_d_0_5"] >= 0.50
        )
    return {
        "hypothesis": "H50_h41_inference_repair",
        "seed": seed,
        "replications": replications,
        "bootstrap_iterations_per_replication": bootstrap_iterations,
        "noise_families": list(family_values),
        "standardized_effects": list(effect_values),
        "results": rows,
        "envelopes": envelopes,
        "eligibility_at_15_passages": eligibility,
        "selected_method": selected_method,
        "installation_gate_passed": installed,
        "decision": "INSTALL_REPAIR" if installed else "NO_ELIGIBLE_REPAIR",
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "artifact_policy": "NO_LABEL_PREDICTION_QUEUE_OR_ZIP_CHANGE",
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
    write_report(compare_methods(), args.output)


if __name__ == "__main__":
    main()
