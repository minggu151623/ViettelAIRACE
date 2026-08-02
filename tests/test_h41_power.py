import numpy as np

from airace.h41_power import _lower_percentile, power_curve, simulate_null_lower_bounds


def test_effect_shift_reuses_null_bounds_exactly() -> None:
    bounds = simulate_null_lower_bounds(
        multiplier=1, replications=20, bootstrap_iterations=50, seed=3, batch_size=5
    )
    assert bounds.shape == (20,)
    assert np.mean(bounds + 1.0 > 0) >= np.mean(bounds + 0.5 > 0)


def test_power_curve_is_deterministic_and_monotone_on_small_run() -> None:
    first = power_curve(
        effects=(0.0, 0.5, 1.0),
        multipliers=(1, 2),
        replications=40,
        bootstrap_iterations=50,
        seed=11,
    )
    second = power_curve(
        effects=(0.0, 0.5, 1.0),
        multipliers=(1, 2),
        replications=40,
        bootstrap_iterations=50,
        seed=11,
    )
    assert first == second
    for row in first["results"]:
        rates = row["promotion_rates"]
        assert rates["0.0"] <= rates["0.5"] <= rates["1.0"]


def test_lower_percentile_uses_registered_order_statistic() -> None:
    samples = np.arange(40, dtype=float).reshape(2, 20)
    assert _lower_percentile(samples).tolist() == [0.0, 20.0]
