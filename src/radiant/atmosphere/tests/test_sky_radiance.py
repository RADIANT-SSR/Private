"""Level-0/1 tests for sky radiance along a LOS (``sky_radiance.py``)."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M, evaluate_column_segment
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.sky_radiance import (
    SCATTERED_SKY_PROVISIONAL_MAX_UM,
    sky_radiance_along_los,
)
from radiant.core.parameters import ParameterBoundsError


def _thermal_grid() -> np.ndarray:
    """MWIR+LWIR only — no wavelength below the provisional gate."""
    return np.linspace(3.0, 14.0, 221)


def _full_grid() -> np.ndarray:
    return np.linspace(0.4, 14.0, 301)


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere()


# ---------------------------------------------------------------------------
# Composition identity
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sky_radiance_is_the_continuation_segment_toward_lower() -> None:
    """L_sky = L_toward_lower of the receiver→h_atm_top column, plus nothing.

    Cold space contributes zero, so the composition
    ``L_sky = L_seg,dn + τ_seg · L_beyond`` reduces to the first term
    element-for-element.
    """
    lam = _thermal_grid()
    atm = _atm()
    zeta = math.radians(48.2)
    sky = sky_radiance_along_los(atm, lam, 0.0, zeta)
    segment = evaluate_column_segment(atm, lam, ColumnSegmentSpec(0.0, DEFAULT_H_ATM_TOP_M, zeta))
    np.testing.assert_array_equal(sky, segment.L_toward_lower)


# ---------------------------------------------------------------------------
# Vacuum limits
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sky_from_above_the_atmosphere_is_exactly_zero() -> None:
    lam = _thermal_grid()
    np.testing.assert_array_equal(
        sky_radiance_along_los(_atm(), lam, DEFAULT_H_ATM_TOP_M, 0.0), np.zeros_like(lam)
    )
    np.testing.assert_array_equal(
        sky_radiance_along_los(_atm(), lam, 3.0e5, 0.4), np.zeros_like(lam)
    )


# ---------------------------------------------------------------------------
# Physical behaviour
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sky_radiance_increases_with_zenith_angle() -> None:
    """A longer slant path through the same column is a warmer, brighter sky."""
    lam = _thermal_grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for zeta_deg in (0.0, 30.0, 60.0, 85.0):
        sky = sky_radiance_along_los(atm, lam, 0.0, math.radians(zeta_deg))
        if previous is not None:
            assert np.all(sky >= previous - 1e-15)
            assert np.any(sky > previous)
        previous = sky


@pytest.mark.level0
def test_sky_radiance_decreases_with_receiver_altitude() -> None:
    """Higher up there is less atmosphere overhead, so a colder sky."""
    lam = _thermal_grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for h in (0.0, 3.0e3, 1.0e4, 3.0e4):
        sky = sky_radiance_along_los(atm, lam, h, 0.0)
        if previous is not None:
            assert np.all(sky <= previous + 1e-15)
        previous = sky


@pytest.mark.level0
def test_sky_radiance_never_exceeds_the_planck_ceiling() -> None:
    """Kirchhoff: ε ≤ 1 so the thermal sky cannot out-radiate a blackbody
    at the emission temperature."""
    from radiant.core.blackbody import planck_spectral_radiance

    lam = _thermal_grid()
    atm = _atm()
    sky = sky_radiance_along_los(atm, lam, 0.0, math.radians(85.0))
    # The ceiling is the warmest air the path contains — sea level, since the
    # column is rooted at the ground.  Since CU-321 the emission temperature is
    # height-resolved and strictly below it, so this bound is the loose one it
    # was always meant to be.
    ceiling = planck_spectral_radiance(lam, float(atm._profile_temperature_K(np.asarray(0.0))))
    assert np.all(sky <= ceiling + 1e-12)


@pytest.mark.level0
def test_sky_radiance_is_non_negative_everywhere() -> None:
    lam = _full_grid()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        sky = sky_radiance_along_los(
            _atm(), lam, 0.0, math.radians(60.0), theta_s_rad=math.radians(30.0)
        )
    assert np.all(sky >= 0.0)
    assert np.all(np.isfinite(sky))


# ---------------------------------------------------------------------------
# Band gating (plan §8.3 answer 3)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_thermal_band_sky_does_not_warn() -> None:
    """MWIR/LWIR sky is first-class at delivery — no provisional warning."""
    lam = _thermal_grid()
    assert float(lam.min()) >= SCATTERED_SKY_PROVISIONAL_MAX_UM
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sky_radiance_along_los(_atm(), lam, 0.0, math.radians(48.2), theta_s_rad=math.radians(30.0))


@pytest.mark.level0
def test_visible_band_sky_warns_provisional() -> None:
    lam = _full_grid()
    with pytest.warns(UserWarning, match="provisional"):
        sky_radiance_along_los(_atm(), lam, 0.0, math.radians(48.2), theta_s_rad=math.radians(30.0))


@pytest.mark.level0
def test_no_warning_without_a_sun_even_in_the_visible() -> None:
    """The warning is about the scattered component; with no sun there is
    none to be provisional about."""
    lam = _full_grid()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sky_radiance_along_los(_atm(), lam, 0.0, math.radians(48.2), theta_s_rad=None)


@pytest.mark.level0
def test_no_warning_at_night_even_in_the_visible() -> None:
    lam = _full_grid()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sky_radiance_along_los(_atm(), lam, 0.0, math.radians(48.2), theta_s_rad=math.pi / 2.0)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_rejects_negative_start_altitude() -> None:
    with pytest.raises(ParameterBoundsError, match="finite altitude"):
        sky_radiance_along_los(_atm(), _thermal_grid(), -10.0, 0.0)


@pytest.mark.level0
def test_near_horizontal_sky_ray_is_refused_with_the_arm_pointer() -> None:
    """Inside the (89.5°, 90°) sliver the column has no trustworthy airmass."""
    with pytest.raises(ParameterBoundsError) as exc:
        sky_radiance_along_los(_atm(), _thermal_grid(), 0.0, math.radians(89.9))
    assert "LevelArmSpec" in str(exc.value)


@pytest.mark.level1
def test_sky_radiance_is_deterministic() -> None:
    lam = _thermal_grid()
    atm = _atm()
    a = sky_radiance_along_los(atm, lam, 1.0e3, 0.6, theta_s_rad=0.4, delta_phi_rad=0.2)
    b = sky_radiance_along_los(atm, lam, 1.0e3, 0.6, theta_s_rad=0.4, delta_phi_rad=0.2)
    np.testing.assert_array_equal(a, b)
