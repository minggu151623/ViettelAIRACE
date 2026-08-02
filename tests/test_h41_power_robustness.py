import numpy as np
import pytest

from airace.h41_power_robustness import draw_noise, robustness_envelope, simulate_lower_bounds


def test_frozen_noise_families_have_expected_moments() -> None:
    rng = np.random.default_rng(7)
    for family in ("normal", "student_t3", "right_skew", "left_skew", "rademacher"):
        values = draw_noise(rng, family, (300_000,))
        assert abs(float(values.mean())) < 0.02
        assert float(values.var()) == pytest.approx(1.0, abs=0.08)


def test_robustness_envelope_is_deterministic_on_small_run() -> None:
    kwargs = dict(
        families=("normal", "right_skew"),
        effects=(0.0, 0.5),
        multipliers=(1, 2),
        replications=30,
        bootstrap_iterations=40,
        seed=9,
    )
    assert robustness_envelope(**kwargs) == robustness_envelope(**kwargs)


def test_unknown_family_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown noise family"):
        simulate_lower_bounds(
            family="unknown", multiplier=1, replications=2, bootstrap_iterations=2
        )
