"""Level-0 tests for the 80° near-horizon hand-over on the down-looking and
solar columns (CU-224 checklist / ex-CU-275).

Three sites route their air mass through the exact spherical slant integral past
:data:`~radiant.atmosphere.protocol.SPHERICAL_SWITCH_RAD`, exactly as the
up-looking sky already does (CU-225 / CU-274):

* ``segment_simple.column_segment_optical_depth`` — any column segment;
* ``SimpleAtmosphere.evaluate``'s **observer** column (``tau_up`` /
  ``tau_full_up``, keyed to ``los.theta_o``);
* ``SimpleAtmosphere.evaluate``'s **solar** column (``tau_sun``, keyed to θ_s).

What these tests pin, in order of importance:

1. **Zero drift inside the band.** At or below 80° every one of the three is
   still exactly ``od_vertical × AtmosphericGeometry.air_mass()`` — the
   plane-parallel primitive, untouched. No shipped scenario exceeds 37.5° LOS
   zenith or 40° solar zenith, so nothing that ships moves.
2. **The correction has the right sign and size** past the switch.
3. **The step at the switch is small and bounded.** The hand-over is a step, not
   a blend — the same shape the up-looking sky has carried since CU-225. It is
   bounded here at ≈ 3.6 % in air mass, against the 18 % drop that got CU-274's
   root-form branch deleted and the factor of two the 89.5° ceiling carries.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.protocol import SPHERICAL_SWITCH_RAD, AtmosphericGeometry
from radiant.atmosphere.segment_simple import column_segment_optical_depth
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import (
    H_AER_M,
    H_H2O_M,
    H_MOL_M,
    SimpleAtmosphere,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet

_H_TOP_M = 100_000.0
#: Sensor altitude for the ``evaluate`` sites — deliberately below ``h_atm_top``
#: so the observer column is a genuine partial column and not the
#: ``h_sensor >= h_atm_top`` short-circuit.
_H_SENSOR_M = 20_000.0
_SWITCH_DEG = math.degrees(SPHERICAL_SWITCH_RAD)


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=1.4,
        standard_atmosphere="midlat_summer",
    )


def _grid() -> np.ndarray:
    return np.linspace(0.4, 14.0, 301)


def _vertical_od(atm: SimpleAtmosphere, lam: np.ndarray, h_low: float, h_high: float) -> np.ndarray:
    col_mol = atm._column_length_km(h_low, h_high, H_MOL_M)
    col_aer = atm._column_length_km(h_low, h_high, H_AER_M)
    col_h2o = atm._column_length_km(h_low, h_high, H_H2O_M)
    return np.asarray(
        atm._rayleigh_extinction_km(lam, 0.0) * col_mol
        + atm._aerosol_extinction_km(lam, 0.0) * col_aer
        + atm._h2o_vertical_od(lam, col_h2o)
        + atm._gas_floor_vertical_od(lam, col_mol),
        dtype=np.float64,
    )


def _column_od(zenith_deg: float, h_low: float = 0.0, h_high: float = _H_TOP_M) -> np.ndarray:
    od, _am, _lengths, _species = column_segment_optical_depth(
        _atm(),
        _grid(),
        ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=math.radians(zenith_deg)),
    )
    return od


# ---------------------------------------------------------------------------
# Zero drift inside the plane-parallel band
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("zenith_deg", [0.0, 30.0, 37.5, 60.0, 75.0, _SWITCH_DEG])
def test_inside_the_band_the_column_is_exactly_the_plane_parallel_product(
    zenith_deg: float,
) -> None:
    """At and below 80° the optical depth is bit-for-bit ``od_vert × air_mass``.

    The switch is strict (``ζ > 80°``), so 80° itself is still plane-parallel;
    this is what guarantees no shipped baseline moves.
    """
    lam = _grid()
    expected = (
        _vertical_od(_atm(), lam, 0.0, _H_TOP_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_TOP_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(zenith_deg),
        ).air_mass()
    )
    np.testing.assert_array_equal(_column_od(zenith_deg), expected)


# ---------------------------------------------------------------------------
# Direction and size of the correction past the switch
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    "zenith_deg,expected_ratio",
    [(80.5, 0.97799), (85.0, 0.93253), (89.4, 0.41515)],
)
def test_past_the_switch_the_column_carries_less_air(
    zenith_deg: float, expected_ratio: float
) -> None:
    """Spherical / plane-parallel optical depth, measured 2026-08-01.

    The plane-parallel form **over**-states the near-horizon column, so the
    correction removes air: transmittance and SNR move **up**, never down. The
    ratios are median-over-grid because the four species carry different
    effective air masses and therefore different ratios.
    """
    lam = _grid()
    plane = (
        _vertical_od(_atm(), lam, 0.0, _H_TOP_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_TOP_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(zenith_deg),
        ).air_mass()
    )
    ratio = float(np.median(_column_od(zenith_deg) / plane))
    assert ratio == pytest.approx(expected_ratio, rel=5e-3)
    assert ratio < 1.0


@pytest.mark.level0
def test_the_step_at_the_switch_is_bounded_and_downward() -> None:
    """The hand-over is a step, not a blend — and a small one.

    Straddling 80° by a thousandth of a degree, the optical depth drops by
    ≈ 3.6 %.  That is the plane-parallel model's own error where it is retired,
    the same shape and the same origin as the 0.64 % radiance step the
    up-looking sky has carried since CU-225.  Compare: the root-form branch
    CU-274 deleted dropped the air mass by **18 %** across its switch, and the
    89.5° ceiling would have deferred the hand-over to a point where the two
    forms differ by a **factor of two**.
    """
    below = _column_od(_SWITCH_DEG - 1e-3)
    above = _column_od(_SWITCH_DEG + 1e-3)
    step = float(np.median(above / below))
    assert 0.960 < step < 1.0, f"hand-over step {step:.5f} outside the bounded band"


@pytest.mark.level0
def test_optical_depth_is_monotone_within_each_branch() -> None:
    """More zenith, more air — separately on each side of the hand-over.

    Monotonicity across the whole domain is what the step forbids; monotonicity
    within each branch is what says neither form is misbehaving.
    """
    lam_index = 150
    inside = [float(_column_od(z)[lam_index]) for z in (0.0, 20.0, 40.0, 60.0, 75.0, _SWITCH_DEG)]
    outside = [float(_column_od(z)[lam_index]) for z in (80.5, 82.0, 85.0, 87.0, 89.4)]
    for series in (inside, outside):
        assert all(b > a for a, b in zip(series[:-1], series[1:], strict=True))


@pytest.mark.level0
def test_an_elevated_lower_endpoint_uses_its_own_ray() -> None:
    """The perigee comes from the segment's own lower endpoint, not from MSL.

    A 10 → 100 km column at 85° is a *different* ray from a 0 → 100 km one at
    85°, and its air masses must be computed about its own perigee.  Pinned by
    the fact that the correction is smaller for the elevated column (its air is
    thinner and its curvature gentler over the same angular offset).
    """
    lam = _grid()
    atm = _atm()
    for h_low in (0.0, 10_000.0):
        plane = (
            _vertical_od(atm, lam, h_low, _H_TOP_M)
            * AtmosphericGeometry(
                sensor_altitude_m=_H_TOP_M,
                target_altitude_m=h_low,
                path_zenith_rad=math.radians(85.0),
            ).air_mass()
        )
        ratio = float(np.median(_column_od(85.0, h_low=h_low) / plane))
        assert 0.5 < ratio < 1.0


# ---------------------------------------------------------------------------
# The two SimpleAtmosphere.evaluate sites
# ---------------------------------------------------------------------------


def _los(theta_o_deg: float, theta_s_deg: float, h_tgt_m: float = 0.0) -> LineOfSightGeometry:
    return LineOfSightGeometry(
        h_tgt=h_tgt_m,
        h_sensor=_H_SENSOR_M,
        theta_o=math.radians(theta_o_deg),
        theta_s=math.radians(theta_s_deg),
        delta_phi=0.0,
        h_atm_top=_H_TOP_M,
    )


def _evaluate(theta_o_deg: float, theta_s_deg: float, h_tgt_m: float = 0.0):  # type: ignore[no-untyped-def]
    lam = _grid()
    return _atm().evaluate(lam, _los(theta_o_deg, theta_s_deg, h_tgt_m), ParameterSet([]))


@pytest.mark.level0
@pytest.mark.parametrize("theta_o_deg", [0.0, 37.5, 60.0, _SWITCH_DEG])
def test_observer_column_inside_the_band_is_the_plane_parallel_product(
    theta_o_deg: float,
) -> None:
    """``tau_up`` at or below 80° is exactly the untouched plane-parallel value."""
    lam = _grid()
    q = _evaluate(theta_o_deg, 30.0)
    expected = np.exp(
        -_vertical_od(_atm(), lam, 0.0, _H_SENSOR_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_SENSOR_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(theta_o_deg),
        ).air_mass()
    )
    np.testing.assert_array_equal(q.tau_up, expected)


@pytest.mark.level0
@pytest.mark.parametrize("theta_s_deg", [0.0, 40.0, _SWITCH_DEG])
def test_solar_column_inside_the_band_is_the_plane_parallel_product(theta_s_deg: float) -> None:
    """``tau_sun`` at or below 80° is exactly the untouched plane-parallel value."""
    lam = _grid()
    q = _evaluate(20.0, theta_s_deg)
    expected = np.exp(
        -_vertical_od(_atm(), lam, 0.0, _H_TOP_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_TOP_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(theta_s_deg),
        ).air_mass()
    )
    np.testing.assert_array_equal(q.tau_sun, expected)


@pytest.mark.level0
def test_observer_column_past_the_switch_transmits_more() -> None:
    """Past 80° the observer column sheds the over-stated air, so τ_up rises."""
    lam = _grid()
    q = _evaluate(85.0, 30.0)
    plane = np.exp(
        -_vertical_od(_atm(), lam, 0.0, _H_SENSOR_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_SENSOR_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(85.0),
        ).air_mass()
    )
    assert np.all(q.tau_up >= plane - 1e-15)
    assert float(np.median(q.tau_up / plane)) > 1.05


@pytest.mark.level0
def test_solar_column_past_the_switch_transmits_more() -> None:
    """The same correction on the twilight solar leg — every low-sun scene."""
    lam = _grid()
    q = _evaluate(20.0, 87.0)
    plane = np.exp(
        -_vertical_od(_atm(), lam, 0.0, _H_TOP_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_TOP_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(87.0),
        ).air_mass()
    )
    assert np.all(q.tau_sun >= plane - 1e-15)
    assert float(np.median(q.tau_sun / plane)) > 1.10


@pytest.mark.level0
def test_the_solar_column_is_no_longer_clamped_at_the_ceiling() -> None:
    """θ_s between 89.5° and 90° gets its true column, not the 89.5° one.

    ``AtmosphericGeometry`` refuses a zenith past ``ZENITH_CEILING_RAD``, so the
    plane-parallel route had to clamp there — the worst place to clamp, since
    that is where ``sec ζ`` is most wrong (237 % high at 89.4°).  The spherical
    route has no ceiling, so the clamp is gone with it.
    """
    medians = [float(np.median(_evaluate(20.0, deg).tau_sun)) for deg in (89.4, 89.6, 89.9)]
    # Strictly decreasing: a clamped column would have returned the identical
    # 89.5° value for the last two.
    assert medians[0] > medians[1] > medians[2]
    assert medians[1] != medians[2]


@pytest.mark.level0
def test_the_full_ground_to_sensor_column_hands_over_with_the_observer_column() -> None:
    """``tau_full_up`` must not be left on the retired form while ``tau_up`` moves.

    The two describe the same ray; letting them use different air-mass physics
    would be a new inconsistency in place of the one being closed.  With an
    airborne target the two columns differ only in their lower endpoint, so
    ``tau_full_up < tau_up`` and both must exceed their plane-parallel values.
    """
    lam = _grid()
    q = _evaluate(85.0, 30.0, h_tgt_m=5_000.0)
    plane_full = np.exp(
        -_vertical_od(_atm(), lam, 0.0, _H_SENSOR_M)
        * AtmosphericGeometry(
            sensor_altitude_m=_H_SENSOR_M,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(85.0),
        ).air_mass()
    )
    assert np.all(q.tau_full_up < q.tau_up + 1e-15)
    assert float(np.median(q.tau_full_up / plane_full)) > 1.05


@pytest.mark.level0
def test_no_nan_or_inf_anywhere_across_the_hand_over() -> None:
    """Rule 16/17: the physics layer never returns a silent NaN."""
    for theta_o in (0.0, 79.9, 80.0, 80.1, 85.0, 89.4):
        for theta_s in (0.0, 79.9, 80.1, 89.4):
            q = _evaluate(theta_o, theta_s)
            for name in ("tau_up", "tau_sun", "tau_full_up", "L_path_up", "L_path_full"):
                values = getattr(q, name)
                assert np.all(np.isfinite(values)), f"{name} not finite at {theta_o}/{theta_s}"
