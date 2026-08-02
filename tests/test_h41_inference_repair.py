import numpy as np

from airace.h41_inference_repair import (
    _stratified_summary,
    compare_methods,
    simulate_method_lower_bounds,
)


def test_stratified_summary_matches_direct_mean_for_equal_weighted_rows() -> None:
    groups = [
        np.asarray([[1.0, 2.0, 3.0]]),
        np.asarray([[4.0, 5.0, 6.0, 7.0, 8.0]]),
        np.asarray([[9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0]]),
    ]
    mean, standard_error, degrees = _stratified_summary(groups, (3, 5, 7))
    assert mean.tolist() == [8.0]
    assert standard_error[0] > 0
    assert degrees[0] > 0


def test_method_bounds_shift_monotonically_with_effect() -> None:
    bounds, rate = simulate_method_lower_bounds(
        family="normal",
        multiplier=1,
        replications=20,
        bootstrap_iterations=40,
        seed=4,
        batch_size=5,
    )
    assert rate == 0
    for lower in bounds.values():
        assert np.mean(lower + 0.75 > 0) >= np.mean(lower + 0.5 > 0)


def test_method_comparison_is_deterministic_on_small_run() -> None:
    kwargs = dict(
        families=("normal", "left_skew"),
        effects=(0.0, 0.5, 0.75),
        multipliers=(1, 2, 3),
        replications=25,
        bootstrap_iterations=40,
        seed=8,
    )
    assert compare_methods(**kwargs) == compare_methods(**kwargs)
