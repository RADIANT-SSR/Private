"""Level-0 tests for the whole-traversed-path level evaluator (CU-224 / ex-CU-276).

The claims these pin, in order:

1. **The optical path is the true traversed one** — verified against the
   ``2·S(r_p; h_p→h_arm) + S(r_p; h_arm→h_top)`` construction assembled
   independently in the test from :mod:`radiant.atmosphere.grazing_column`.
2. **The obvious fix would have been wrong** — a sensor-rooted ascending arc,
   the shape the up-looking branch uses, drops up to 25 % of the column.  The
   CU-276 table, re-measured.
3. **There is no interior graybody boundary** — the whole path emits
   ``(1 − τ)·B(T_eff)`` once, which is what removes the CU-254 non-additivity
   the two-segment composition carried.
4. **It joins continuously onto the grazing evaluator** — a zero-length arm
   reduces to :func:`evaluate_grazing_segment` at ζ = π/2, exactly.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.grazing_column import grazing_slant_column_km
from radiant.atmosphere.level_arm import evaluate_level_arm
from radiant.atmosphere.level_whole_path import (
    evaluate_level_whole_path,
    level_path_perigee_radius_m,
    level_whole_path_optical_depth,
)
from radiant.atmosphere.segment_grazing import evaluate_grazing_segment
from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import LevelArmSpec
from radiant.atmosphere.simple import H_AER_M, H_H2O_M, H_MOL_M, SimpleAtmosphere
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

_TOP = DEFAULT_H_ATM_TOP_M


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere()


def _grid() -> np.ndarray:
    return np.linspace(0.4, 14.0, 301)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    "altitude_m,arm_m",
    [(0.0, 8_000.0), (3_000.0, 100_000.0), (10_000.0, 150_000.0)],
)
def test_perigee_matches_the_familiar_sag_formula(altitude_m: float, arm_m: float) -> None:
    """``r_arm − r_p`` is the familiar ``L²/8r`` tangent depression, to 4th order.

    The exact chord form and the small-angle sag differ only by the ``L⁴/128r³``
    term — 15 mm on the longest admissible arm — which is what says the two
    descriptions of the same geometry have not drifted apart.
    """
    r_p = level_path_perigee_radius_m(altitude_m, arm_m)
    exact_sag = (R_EARTH_M + altitude_m) - r_p
    # The familiar form is L^2/(8 r) with r the *endpoint* radius.  Several
    # shipped provenance fields print L^2/(8 R_E) instead, which is the h = 0
    # case and runs 0.15 % high at a 10 km endpoint (441.45 m against 440.78 m
    # for a 150 km arm) -- recorded here, not used.
    approx_sag = arm_m**2 / (8.0 * (R_EARTH_M + altitude_m))
    assert exact_sag == pytest.approx(approx_sag, rel=1e-4)


@pytest.mark.level0
def test_zero_length_arm_has_its_perigee_at_the_endpoint() -> None:
    assert level_path_perigee_radius_m(5_000.0, 0.0) == pytest.approx(
        R_EARTH_M + 5_000.0, rel=1e-15
    )


@pytest.mark.level0
@pytest.mark.parametrize("altitude_m,arm_m", [(-1.0, 1000.0), (0.0, -1.0), (float("nan"), 1000.0)])
def test_rejects_unphysical_level_geometry(altitude_m: float, arm_m: float) -> None:
    with pytest.raises(ParameterBoundsError):
        level_path_perigee_radius_m(altitude_m, arm_m)


@pytest.mark.level0
def test_rejects_a_chord_longer_than_the_diameter() -> None:
    with pytest.raises(ParameterBoundsError, match="twice the endpoint radius"):
        level_path_perigee_radius_m(0.0, 3.0 * R_EARTH_M)


# ---------------------------------------------------------------------------
# The optical path is the true traversed one
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("altitude_m,arm_m", [(3_000.0, 100_000.0), (10_000.0, 150_000.0)])
def test_slant_columns_are_two_halves_plus_the_continuation(
    altitude_m: float, arm_m: float
) -> None:
    """``S_i = 2·S(r_p; h_p→h_arm) + S(r_p; h_arm→h_top)``, per species.

    Assembled here independently from the spherical slant integral, so this is a
    statement about the *path*, not a re-run of the implementation.
    """
    _od, masses, geometry = level_whole_path_optical_depth(
        _atm(), _grid(), altitude_m=altitude_m, arm_length_m=arm_m
    )
    r_p = level_path_perigee_radius_m(altitude_m, arm_m)
    h_p = r_p - R_EARTH_M
    for scale_height, measured in (
        (H_MOL_M, masses.slant_column_mol_km),
        (H_AER_M, masses.slant_column_aer_km),
        (H_H2O_M, masses.slant_column_h2o_km),
    ):
        expected = 2.0 * grazing_slant_column_km(
            r_p, h_p, altitude_m, scale_height
        ) + grazing_slant_column_km(r_p, altitude_m, _TOP, scale_height)
        assert measured == pytest.approx(expected, rel=1e-9)
    assert geometry["perigee_altitude_m"] == pytest.approx(h_p, rel=1e-12)


@pytest.mark.level0
@pytest.mark.parametrize(
    "altitude_m,arm_m,expected_fraction",
    [(0.0, 8_000.0, 1.0142), (3_000.0, 100_000.0, 0.8304), (10_000.0, 150_000.0, 0.7512)],
)
def test_a_sensor_rooted_arc_would_have_dropped_the_arm(
    altitude_m: float, arm_m: float, expected_fraction: float
) -> None:
    """The CU-276 "why the obvious fix is wrong" table, re-measured.

    A single ascending arc rooted at the sensor — the up-looking branch's shape —
    recovers only 83.0 % of the true traversed molecular column for a 100 km arm
    at 3 km, and 75.1 % for 150 km at 10 km.  Rooting the level sky that way
    would have shed up to 25 % of the air to close a 12 %-class composition
    error.

    The sea-level row is **degenerate and is the exception**: an 8 km arm at MSL
    has its perigee 1.3 m *below* the ellipsoid, so the true path is the clamped
    one and the sensor-rooted arc comes out 1.4 % *longer*, not shorter.  CU-276
    filed 0.9859 for this row from an unclamped integral and corrected it to
    1.0142 on re-audit; 1.0142 is what a clamped model can actually produce.
    """
    r_p = level_path_perigee_radius_m(altitude_m, arm_m)
    h_p = max(r_p - R_EARTH_M, 0.0)
    true_column = 2.0 * grazing_slant_column_km(
        r_p, h_p, altitude_m, H_MOL_M
    ) + grazing_slant_column_km(r_p, altitude_m, _TOP, H_MOL_M)
    sensor_rooted = grazing_slant_column_km(R_EARTH_M + altitude_m, altitude_m, _TOP, H_MOL_M)
    assert sensor_rooted / true_column == pytest.approx(expected_fraction, rel=2e-3)


@pytest.mark.level0
def test_a_longer_arm_traverses_more_air() -> None:
    """Monotone in range: the arm is part of the path, so extending it adds air."""
    lam = _grid()
    ods = [
        float(
            level_whole_path_optical_depth(_atm(), lam, altitude_m=5_000.0, arm_length_m=arm)[0][
                150
            ]
        )
        for arm in (0.0, 10_000.0, 50_000.0, 150_000.0)
    ]
    assert all(b > a for a, b in zip(ods[:-1], ods[1:], strict=True))


# ---------------------------------------------------------------------------
# One graybody, no interior boundary
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_the_whole_path_emits_one_graybody() -> None:
    """``L = (1 − τ)·B(T_eff(h_arm))`` for a dark scene — exactly one emitter.

    The two-segment composition this replaces emitted twice, at two different
    effective temperatures, joined at the target plane.  One segment, one τ, one
    ``T_eff``: that identity is what removes the CU-254 non-additivity.
    """
    lam = _grid()
    atm = _atm()
    q = evaluate_level_whole_path(atm, lam, altitude_m=10_000.0, arm_length_m=50_000.0)
    expected = segment_thermal_emission(
        lam, q.tau, atm._downwelling_effective_temperature_K(10_000.0)
    )
    np.testing.assert_allclose(q.L_toward_lower, expected, rtol=1e-12, atol=0.0)
    np.testing.assert_array_equal(q.L_toward_lower, q.L_toward_upper)


@pytest.mark.level0
def test_it_differs_from_the_two_segment_composition_it_replaces() -> None:
    """And in the direction CU-254 measured: the composition under-reports.

    The retired form is rebuilt here from its own two shipped pieces — the level
    arm and the ascending continuation rooted at the target — so the comparison
    is against what actually shipped, not against a paraphrase.
    """
    lam = _grid()
    atm = _atm()
    altitude_m, arm_m = 10_000.0, 50_000.0
    whole = evaluate_level_whole_path(atm, lam, altitude_m=altitude_m, arm_length_m=arm_m)

    arm = evaluate_level_arm(atm, lam, LevelArmSpec(altitude_m=altitude_m, length_m=arm_m))
    r_p = level_path_perigee_radius_m(altitude_m, arm_m)
    continuation = evaluate_grazing_segment(
        atm,
        lam,
        r_tangent_m=r_p,
        h_low_m=altitude_m,
        h_high_m=_TOP,
        zeta_low_rad=math.asin(min(r_p / (R_EARTH_M + altitude_m), 1.0)),
    )
    composed = arm.L_toward_upper + arm.tau * continuation.L_toward_lower

    mwir = (lam > 3.0) & (lam < 5.0)
    assert float(np.median(composed[mwir])) < float(np.median(whole.L_toward_lower[mwir]))


# ---------------------------------------------------------------------------
# Continuity with the grazing evaluator
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_a_zero_length_arm_is_exactly_the_grazing_evaluator() -> None:
    """No step where the level topology meets the ascending one.

    With ``L = 0`` the perigee sits at the sensor, the descending half vanishes,
    and the whole path *is* the ascending arc at ζ = π/2.  Both evaluators must
    then return the identical arrays — they share the air-mass module, the
    thermal module and the single-scatter module, so this is a real
    cross-evaluator identity rather than a coincidence.
    """
    lam = _grid()
    atm = _atm()
    altitude_m = 3_000.0
    level = evaluate_level_whole_path(
        atm, lam, altitude_m=altitude_m, arm_length_m=0.0, theta_s_rad=0.6, delta_phi_rad=0.3
    )
    grazing = evaluate_grazing_segment(
        atm,
        lam,
        r_tangent_m=R_EARTH_M + altitude_m,
        h_low_m=altitude_m,
        h_high_m=_TOP,
        zeta_low_rad=math.pi / 2.0,
        theta_s_rad=0.6,
        delta_phi_rad=0.3,
    )
    np.testing.assert_allclose(level.tau, grazing.tau, rtol=1e-12, atol=0.0)
    np.testing.assert_allclose(level.L_toward_lower, grazing.L_toward_lower, rtol=1e-12, atol=0.0)


# ---------------------------------------------------------------------------
# Sub-surface perigee, vacuum, and failure modes
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_a_sea_level_arm_warns_that_its_perigee_is_clamped() -> None:
    """Rule 17: the clamp is announced, with its depth and its bounded size."""
    with pytest.warns(UserWarning, match="BELOW mean sea level"):
        _od, _m, geometry = level_whole_path_optical_depth(
            _atm(), _grid(), altitude_m=0.0, arm_length_m=8_000.0
        )
    assert geometry["perigee_altitude_m"] < 0.0
    assert geometry["integration_floor_m"] == 0.0
    # 8 km at sea level dips 1.3 m; the clamped column is within 0.1 % of the
    # unclamped one on the shallowest (water) profile.
    assert geometry["perigee_altitude_m"] == pytest.approx(-1.256, abs=0.05)


@pytest.mark.level0
def test_an_arm_above_h_atm_top_is_exact_vacuum() -> None:
    lam = _grid()
    q = evaluate_level_whole_path(
        _atm(), lam, altitude_m=_TOP + 1.0, arm_length_m=50_000.0, theta_s_rad=0.5
    )
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))
    np.testing.assert_array_equal(q.L_toward_lower, np.zeros_like(lam))


@pytest.mark.level0
def test_sun_below_the_horizon_gives_exactly_zero_scattered_term() -> None:
    lam = _grid()
    atm = _atm()
    dark = evaluate_level_whole_path(atm, lam, altitude_m=5_000.0, arm_length_m=40_000.0)
    night = evaluate_level_whole_path(
        atm, lam, altitude_m=5_000.0, arm_length_m=40_000.0, theta_s_rad=math.pi / 2.0
    )
    np.testing.assert_array_equal(dark.L_toward_lower, night.L_toward_lower)


@pytest.mark.level0
def test_directional_products_differ_under_illumination() -> None:
    """Forward scatter one way is back scatter the other."""
    lam = _grid()
    q = evaluate_level_whole_path(
        _atm(),
        lam,
        altitude_m=5_000.0,
        arm_length_m=40_000.0,
        theta_s_rad=math.radians(40.0),
        delta_phi_rad=0.0,
    )
    vis = lam < 0.8
    assert not np.allclose(q.L_toward_upper[vis], q.L_toward_lower[vis], rtol=1e-3)


@pytest.mark.level0
def test_no_nan_or_inf_over_the_admissible_range() -> None:
    lam = _grid()
    for altitude_m in (0.0, 3_000.0, 10_000.0, 90_000.0):
        for arm_m in (0.0, 1_000.0, 50_000.0, 200_000.0):
            with pytest.warns(UserWarning) if altitude_m == 0.0 and arm_m > 0.0 else _noop():
                q = evaluate_level_whole_path(
                    _atm(),
                    lam,
                    altitude_m=altitude_m,
                    arm_length_m=arm_m,
                    theta_s_rad=math.radians(30.0),
                )
            assert np.all(np.isfinite(q.tau))
            assert np.all(np.isfinite(q.L_toward_lower))
            assert np.all(q.L_toward_lower >= 0.0)


class _noop:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.mark.level0
def test_is_deterministic() -> None:
    lam = _grid()
    a = evaluate_level_whole_path(
        _atm(), lam, altitude_m=4_000.0, arm_length_m=30_000.0, theta_s_rad=0.4
    )
    b = evaluate_level_whole_path(
        _atm(), lam, altitude_m=4_000.0, arm_length_m=30_000.0, theta_s_rad=0.4
    )
    np.testing.assert_array_equal(a.tau, b.tau)
    np.testing.assert_array_equal(a.L_toward_lower, b.L_toward_lower)
