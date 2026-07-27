"""Level-0/1 tests for the constant-altitude arm (``level_arm.py``)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.level_arm import (
    LEVEL_ARM_ZENITH_RAD,
    evaluate_level_arm,
    local_extinction_per_km,
)
from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segments import LevelArmSpec
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.parameters import ParameterBoundsError


def _grid() -> np.ndarray:
    return np.linspace(0.4, 14.0, 301)


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere()


# ---------------------------------------------------------------------------
# Vacuum limits
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_zero_length_arm_is_exact_vacuum() -> None:
    lam = _grid()
    q = evaluate_level_arm(
        _atm(), lam, LevelArmSpec(altitude_m=3.0e3, length_m=0.0), theta_s_rad=0.5
    )
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))
    np.testing.assert_array_equal(q.L_toward_upper, np.zeros_like(lam))
    np.testing.assert_array_equal(q.L_toward_lower, np.zeros_like(lam))


@pytest.mark.level0
def test_arm_above_h_atm_top_is_exact_vacuum() -> None:
    lam = _grid()
    q = evaluate_level_arm(
        _atm(), lam, LevelArmSpec(altitude_m=DEFAULT_H_ATM_TOP_M, length_m=5.0e4)
    )
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))
    np.testing.assert_array_equal(q.L_toward_lower, np.zeros_like(lam))


# ---------------------------------------------------------------------------
# The defining analytic property: pure exponential in path length
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_tau_of_double_length_is_tau_squared() -> None:
    """τ(2L) = τ(L)² — the analytic Beer-Lambert identity.

    Exact in exact arithmetic; in IEEE-754 the two orderings of the same
    product differ by at most ~1 ULP.  This identity is precisely what a
    MODTRAN band model does NOT satisfy (band transmittance saturates
    sub-exponentially); the divergence is quantified against the real
    horizontal 5×5 grid in the integration anchors.
    """
    lam = _grid()
    atm = _atm()
    for altitude_m in (0.0, 3.0e3, 1.0e4):
        one = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_m, 1.0e4)).tau
        two = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_m, 2.0e4)).tau
        np.testing.assert_allclose(two, one**2, rtol=1e-15, atol=0.0)


@pytest.mark.level0
def test_optical_depth_is_linear_in_length() -> None:
    """OD(L) = α·L exactly — three lengths on one straight line."""
    lam = _grid()
    atm = _atm()
    alpha, _species = local_extinction_per_km(atm, lam, 3.0e3)
    for length_m in (1.0e3, 2.5e4, 1.0e5):
        tau = evaluate_level_arm(atm, lam, LevelArmSpec(3.0e3, length_m)).tau
        np.testing.assert_allclose(-np.log(tau), alpha * length_m / 1000.0, rtol=1e-12)


@pytest.mark.level0
def test_local_extinction_species_sum_is_the_total() -> None:
    lam = _grid()
    alpha, species = local_extinction_per_km(_atm(), lam, 2.0e3)
    np.testing.assert_allclose(
        alpha, species["mol"] + species["aer"] + species["h2o"] + species["gas"], rtol=0.0
    )
    for name, values in species.items():
        assert np.all(values >= 0.0), name


# ---------------------------------------------------------------------------
# Monotonicity
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_tau_decreases_with_arm_length() -> None:
    lam = _grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for length_m in (1.0e3, 5.0e3, 2.5e4, 1.0e5):
        tau = evaluate_level_arm(atm, lam, LevelArmSpec(3.0e3, length_m)).tau
        if previous is not None:
            assert np.all(tau <= previous + 1e-15)
            assert np.any(tau < previous)
        previous = tau


@pytest.mark.level0
def test_tau_increases_with_arm_altitude() -> None:
    """Thinner air higher up: the same arm length is more transparent."""
    lam = _grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for altitude_m in (0.0, 3.0e3, 5.0e3, 1.0e4, 1.5e4):
        tau = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_m, 2.5e4)).tau
        if previous is not None:
            assert np.all(tau >= previous - 1e-15)
        previous = tau


@pytest.mark.level0
def test_tau_decreases_with_path_water() -> None:
    lam = _grid()
    previous: np.ndarray | None = None
    for pwv in (0.5, 1.4, 3.0, 5.0):
        tau = evaluate_level_arm(
            SimpleAtmosphere(precipitable_water_cm=pwv), lam, LevelArmSpec(1.0e3, 2.0e4)
        ).tau
        if previous is not None:
            assert np.all(tau <= previous + 1e-15)
            assert np.any(tau < previous)
        previous = tau


# ---------------------------------------------------------------------------
# Directional symmetry
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_thermal_arm_is_exactly_symmetric() -> None:
    """One altitude, one temperature, one τ ⇒ the two ends emit equally."""
    lam = _grid()
    atm = _atm()
    q = evaluate_level_arm(atm, lam, LevelArmSpec(3.0e3, 2.5e4), theta_s_rad=None)
    np.testing.assert_array_equal(q.L_toward_upper, q.L_toward_lower)
    t_eff = atm._downwelling_effective_temperature_K(3.0e3)
    np.testing.assert_array_equal(
        q.L_toward_lower, (1.0 - q.tau) * planck_spectral_radiance(lam, t_eff)
    )


@pytest.mark.level0
def test_arm_is_symmetric_for_a_sun_perpendicular_to_the_path() -> None:
    """cos Δφ = 0 makes the two scattering angles equal, so the fields match."""
    lam = _grid()
    q = evaluate_level_arm(
        _atm(),
        lam,
        LevelArmSpec(3.0e3, 2.5e4),
        theta_s_rad=math.radians(40.0),
        delta_phi_rad=math.pi / 2.0,
    )
    np.testing.assert_allclose(q.L_toward_upper, q.L_toward_lower, rtol=1e-12)


@pytest.mark.level0
def test_arm_scatter_is_direction_specific_in_the_solar_plane() -> None:
    """In-plane sun: forward one way, back the other — genuinely different."""
    lam = _grid()
    q = evaluate_level_arm(
        _atm(),
        lam,
        LevelArmSpec(3.0e3, 2.5e4),
        theta_s_rad=math.radians(40.0),
        delta_phi_rad=0.0,
    )
    assert q.provenance["cos_scatter_toward_upper"] == pytest.approx(
        -q.provenance["cos_scatter_toward_lower"], rel=1e-12
    )
    vis = lam < 0.8
    assert not np.allclose(q.L_toward_upper[vis], q.L_toward_lower[vis], rtol=1e-3)


@pytest.mark.level0
def test_arm_zenith_is_the_horizontal() -> None:
    assert math.pi / 2.0 == LEVEL_ARM_ZENITH_RAD


@pytest.mark.level0
def test_night_arm_collapses_to_the_thermal_product() -> None:
    lam = _grid()
    atm = _atm()
    spec = LevelArmSpec(1.0e3, 3.0e4)
    night = evaluate_level_arm(atm, lam, spec, theta_s_rad=math.pi / 2.0)
    thermal = evaluate_level_arm(atm, lam, spec, theta_s_rad=None)
    np.testing.assert_array_equal(night.L_toward_lower, thermal.L_toward_lower)


# ---------------------------------------------------------------------------
# Provenance and validation
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_provenance_reports_the_tangent_depression() -> None:
    """Δh ≈ L²/8R_E — the quantity the horizon guard bounds."""
    lam = _grid()
    q = evaluate_level_arm(_atm(), lam, LevelArmSpec(3.0e3, 1.0e5))
    assert q.provenance["tangent_depression_m"] == pytest.approx(196.2, rel=0.02)


@pytest.mark.level0
def test_rejects_bad_h_atm_top() -> None:
    with pytest.raises(ParameterBoundsError, match="positive-finite"):
        evaluate_level_arm(_atm(), _grid(), LevelArmSpec(0.0, 1.0e4), h_atm_top_m=0.0)


@pytest.mark.level1
def test_arm_evaluation_is_deterministic() -> None:
    lam = _grid()
    atm = _atm()
    spec = LevelArmSpec(2.0e3, 4.0e4)
    a = evaluate_level_arm(atm, lam, spec, theta_s_rad=0.5, delta_phi_rad=0.3)
    b = evaluate_level_arm(atm, lam, spec, theta_s_rad=0.5, delta_phi_rad=0.3)
    np.testing.assert_array_equal(a.tau, b.tau)
    np.testing.assert_array_equal(a.L_toward_lower, b.L_toward_lower)
