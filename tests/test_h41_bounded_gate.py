import numpy as np

from airace.h41_bounded_gate import (
    analytic_penalties,
    bounded_noise,
    evaluate_bounded_gates,
    hoeffding_lower,
    stratified_empirical_bernstein_lower,
)


def test_bounded_families_respect_metric_delta_range() -> None:
    rng = np.random.default_rng(3)
    for family in (
        "symmetric_uniform",
        "rademacher",
        "beta_right_skew",
        "beta_left_skew",
        "rare_two_point",
    ):
        values, sd = bounded_noise(rng, family, (100_000,))
        assert values.min() >= -0.5
        assert values.max() <= 0.5
        assert abs(float(values.mean())) < 0.01
        assert abs(float(values.std()) - sd) < 0.01
        assert (values + sd).min() >= -1
        assert (values + sd).max() <= 1


def test_zero_vector_bounds_match_analytic_penalties() -> None:
    values = np.zeros((2, 15))
    analytic = analytic_penalties(1)
    assert np.allclose(hoeffding_lower(values), -analytic["hoeffding_penalty"])
    empirical = stratified_empirical_bernstein_lower(values, (3, 5, 7))
    assert np.allclose(
        empirical, -analytic["empirical_bernstein_zero_variance_penalty"]
    )


def test_bounded_gate_is_deterministic_on_small_run() -> None:
    kwargs = dict(
        families=("symmetric_uniform", "beta_left_skew"),
        effects=(0.0, 0.5, 0.75, 1.0),
        multipliers=(1, 2, 3, 4),
        replications=100,
        seed=5,
    )
    assert evaluate_bounded_gates(**kwargs) == evaluate_bounded_gates(**kwargs)
