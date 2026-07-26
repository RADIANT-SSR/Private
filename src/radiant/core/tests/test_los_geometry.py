"""Tests for radiant.core.los_geometry.

Covers:
- LineOfSightGeometry bounds validation (each field at edges, inside/outside).
- slant_range_atm truth anchors: nadir exact, spherical-earth reference.
- path_airmass_up truth anchors: flat-earth secant limit, 60° reference.
- theta_o_from_eta round-trip and edge cases.
- Serialization round-trip via to_dict / from_dict.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant.core.los_geometry import (
    LineOfSightGeometry,
    theta_o_from_eta,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import (
    level_central_angle_from_slant_m,
    level_theta_o_from_central_angle_rad,
)

# ---------------------------------------------------------------------------
# Construction: valid edges
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_los_construct_nadir_ground() -> None:
    """h_tgt=0, theta_o=0 — the nadir ground case, always valid."""
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
    assert los.h_tgt == 0.0
    assert los.theta_o == 0.0
    assert los.h_atm_top == pytest.approx(1.0e5, rel=1e-12)
    assert los.theta_s is None
    assert los.delta_phi is None


@pytest.mark.level0
def test_los_h_tgt_at_top_is_valid_with_vacuum_limits() -> None:
    """h_tgt = h_atm_top is a valid edge (empty column); vacuum-limit properties (Gap 95)."""
    los = LineOfSightGeometry(h_tgt=1.0e5, theta_o=0.0)
    assert los.h_tgt == 1.0e5
    # slant_range_atm is 0 exactly at the edge [m]
    assert los.slant_range_atm == pytest.approx(0.0, abs=1e-6)
    # airmass takes the vacuum limit (0 m of slant over 0 m of column) [dimensionless]
    assert los.path_airmass_up == 1.0


@pytest.mark.level0
def test_los_valid_full_angle_set() -> None:
    """All optional angles set to valid values."""
    los = LineOfSightGeometry(
        h_tgt=5000.0,
        theta_o=math.radians(45),
        theta_s=math.radians(30),
        delta_phi=math.radians(-20),
    )
    assert los.theta_s == pytest.approx(math.radians(30), rel=1e-12)
    assert los.delta_phi == pytest.approx(math.radians(-20), rel=1e-12)


# ---------------------------------------------------------------------------
# Construction: invalid edges
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_los_h_tgt_negative_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        LineOfSightGeometry(h_tgt=-1.0, theta_o=0.0)


@pytest.mark.level0
def test_los_h_tgt_above_top_is_exo_target() -> None:
    """Gap 95: h_tgt above the column top is a legal exo-altitude target —
    no column above it (slant 0 m), vacuum airmass limit 1.0."""
    los = LineOfSightGeometry(h_tgt=2.0e5, theta_o=0.0)
    assert los.h_tgt == 2.0e5
    assert los.slant_range_atm == 0.0
    assert los.path_airmass_up == 1.0


@pytest.mark.level0
def test_los_h_atm_top_less_than_h_tgt_is_exo_target() -> None:
    """Same Gap 95 semantics when h_atm_top is explicitly below the target."""
    los = LineOfSightGeometry(h_tgt=5.0e4, theta_o=0.0, h_atm_top=1.0e4)
    assert los.slant_range_atm == 0.0
    assert los.path_airmass_up == 1.0


@pytest.mark.level0
def test_los_h_atm_top_nonpositive_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="h_atm_top"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, h_atm_top=0.0)


@pytest.mark.level0
def test_los_theta_o_at_pi_over_2_raises() -> None:
    """θ_o = π/2 exactly is grazing and must raise (horizon excluded)."""
    with pytest.raises(ParameterBoundsError, match="theta_o"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.pi / 2.0)


@pytest.mark.level0
def test_los_theta_o_just_below_pi_over_2_raises() -> None:
    """θ_o just below π/2 now raises via the hard horizon guard.

    Behaviour change, ADR-0011 decision 6 + plan §8.3: the ±0.5° band about
    the geometric horizontal is rejected because refraction dominates there
    and is unmodelled.  Before Phase 1 this band was silently computed (the
    only rejection was θ_o ≥ π/2).  No shipped scenario enters it —
    existing configurations sit at θ_o ≤ ~75°.
    """
    with pytest.raises(ParameterBoundsError, match="horizon guard"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.pi / 2.0 - 1e-6)


@pytest.mark.level0
def test_los_theta_o_outside_the_guard_band_valid() -> None:
    """Two degrees off the horizontal is admissible and silent."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(87.5))
    assert los.theta_o < math.pi / 2.0


@pytest.mark.level0
def test_los_theta_o_negative_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="theta_o"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=-1e-9)


@pytest.mark.level0
def test_los_theta_s_out_of_range_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="theta_s"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=-1e-9)
    with pytest.raises(ParameterBoundsError, match="theta_s"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=math.pi + 1e-9)


@pytest.mark.level0
def test_los_theta_s_at_edges_valid() -> None:
    LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=0.0)
    LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=math.pi)


@pytest.mark.level0
def test_los_delta_phi_out_of_range_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="delta_phi"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, delta_phi=-math.pi - 1e-9)
    with pytest.raises(ParameterBoundsError, match="delta_phi"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, delta_phi=math.pi + 1e-9)


@pytest.mark.level0
def test_los_delta_phi_at_edges_valid() -> None:
    LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, delta_phi=-math.pi)
    LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, delta_phi=math.pi)


# ---------------------------------------------------------------------------
# slant_range_atm truth anchors
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_slant_range_nadir_equals_column() -> None:
    """Truth anchor: at θ_o = 0, slant = h_atm_top − h_tgt exactly."""
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
    assert los.slant_range_atm == pytest.approx(1.0e5, rel=1e-12)

    los2 = LineOfSightGeometry(h_tgt=5.0e4, theta_o=0.0, h_atm_top=1.0e5)
    assert los2.slant_range_atm == pytest.approx(5.0e4, rel=1e-12)


@pytest.mark.level0
def test_slant_range_spherical_60deg() -> None:
    """Truth anchor (independent hand computation).

    At R_E = 6.371e6 m, h_atm_top = 1.0e5 m, h_tgt = 0, θ_o = 60°:
        slant = -r_t cos(θ) + √((r_t cos θ)² + (r_top² − r_t²))
              = -6371000 * 0.5 + sqrt((6371000*0.5)² + (6471000² − 6371000²))
              ≈ 195566.44 m (hand-calculated)
    """
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(60))
    expected = 195566.44  # m, hand-computed independently
    assert los.slant_range_atm == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# path_airmass_up truth anchors
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_airmass_nadir_is_one() -> None:
    """Truth anchor: nadir airmass is exactly 1."""
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
    assert los.path_airmass_up == pytest.approx(1.0, rel=1e-12)


@pytest.mark.level0
def test_airmass_small_angle_matches_secant() -> None:
    """Flat-Earth limit: airmass ≈ sec(θ_o) for small θ_o."""
    for deg in (1.0, 5.0, 10.0, 20.0):
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(deg))
        sec = 1.0 / math.cos(math.radians(deg))
        assert los.path_airmass_up == pytest.approx(sec, rel=1e-2)


@pytest.mark.level0
def test_airmass_60deg_spherical_reference() -> None:
    """Truth anchor: spherical-Earth airmass at 60° with h_atm_top=100 km.

    Hand-computed: slant ≈ 195.57 km, column = 100 km → airmass ≈ 1.956.
    This is *less* than sec(60°) = 2.0 — the spherical correction reduces
    the airmass by ~2%, which is the standard textbook result.
    """
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(60))
    assert los.path_airmass_up == pytest.approx(1.956, rel=1e-3)


# ---------------------------------------------------------------------------
# theta_o_from_eta round-trip and edges
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_theta_o_from_eta_zero_stays_zero() -> None:
    """Truth anchor: η = 0 ⇒ θ_o = 0 for any altitudes."""
    for h_sensor in (100.0, 1_000.0, 500_000.0, 1.0e7):
        for h_tgt in (0.0, 1_000.0, 50_000.0):
            assert theta_o_from_eta(0.0, h_sensor, h_tgt) == pytest.approx(0.0, abs=1e-15)


@pytest.mark.level0
def test_theta_o_from_eta_sine_rule_identity() -> None:
    """Truth anchor: the result satisfies the sine-rule identity to 1e-12.

    sin(θ_o) · (R_E + h_tgt) = sin(η) · (R_E + h_sensor)
    """
    from radiant.core.constants import R_EARTH_M

    eta = math.radians(30)
    h_sensor = 500_000.0
    h_tgt = 0.0

    theta_o = theta_o_from_eta(eta, h_sensor, h_tgt)
    lhs = math.sin(theta_o) * (R_EARTH_M + h_tgt)
    rhs = math.sin(eta) * (R_EARTH_M + h_sensor)
    assert lhs == pytest.approx(rhs, rel=1e-12)


@pytest.mark.level0
def test_theta_o_from_eta_grows_with_eta() -> None:
    """θ_o increases monotonically with η at fixed altitudes."""
    h_sensor = 500_000.0
    h_tgt = 0.0
    thetas = [theta_o_from_eta(math.radians(d), h_sensor, h_tgt) for d in (5.0, 10.0, 20.0, 40.0)]
    assert all(thetas[i] < thetas[i + 1] for i in range(len(thetas) - 1))


@pytest.mark.level0
def test_theta_o_from_eta_invalid_sensor_altitude() -> None:
    with pytest.raises(ParameterBoundsError, match="h_sensor"):
        theta_o_from_eta(0.0, -1.0, 0.0)


@pytest.mark.level0
def test_theta_o_from_eta_invalid_tgt_altitude() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        theta_o_from_eta(0.0, 500_000.0, -1.0)


@pytest.mark.level0
def test_theta_o_from_eta_eta_out_of_range() -> None:
    with pytest.raises(ParameterBoundsError, match="eta"):
        theta_o_from_eta(math.pi / 2.0 + 0.1, 500_000.0, 0.0)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_los_to_from_dict_round_trip_minimal() -> None:
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.1)
    d = los.to_dict()
    rebuilt = LineOfSightGeometry.from_dict(d)
    assert rebuilt == los


@pytest.mark.level0
def test_los_to_from_dict_round_trip_full() -> None:
    los = LineOfSightGeometry(
        h_tgt=5000.0,
        theta_o=math.radians(45),
        h_atm_top=1.2e5,
        theta_s=math.radians(30),
        delta_phi=math.radians(-20),
    )
    d = los.to_dict()
    rebuilt = LineOfSightGeometry.from_dict(d)
    assert rebuilt == los


# ===========================================================================
# Phase 1 (ADR-0011) — direction-general LOS contract
# ===========================================================================

H_GEO = 35_786_000.0  # m


# ---------------------------------------------------------------------------
# h_sensor field, direction, serialization
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_h_sensor_defaults_to_none_legacy_payload() -> None:
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.3)
    assert los.h_sensor is None


@pytest.mark.level0
def test_los_direction_from_altitudes() -> None:
    down = LineOfSightGeometry(h_tgt=0.0, theta_o=0.3, h_sensor=500_000.0)
    up = LineOfSightGeometry(h_tgt=500_000.0, theta_o=math.pi, h_sensor=0.0, h_atm_top=1.0e5)
    assert down.los_direction == "down"
    assert not down.is_uplooking
    assert up.los_direction == "up"
    assert up.is_uplooking


@pytest.mark.level0
def test_los_direction_level_equal_altitudes() -> None:
    theta_o = level_theta_o_from_central_angle_rad(level_central_angle_from_slant_m(8_000.0, 30.0))
    los = LineOfSightGeometry(h_tgt=30.0, theta_o=theta_o, h_sensor=30.0)
    assert los.los_direction == "level"
    assert not los.is_uplooking


@pytest.mark.level0
def test_los_direction_legacy_falls_back_to_theta_o() -> None:
    """Without h_sensor the hemisphere invariant still fixes the direction."""
    assert LineOfSightGeometry(h_tgt=0.0, theta_o=0.3).los_direction == "down"
    assert (
        LineOfSightGeometry(h_tgt=500_000.0, theta_o=math.pi, h_atm_top=1.0e5).los_direction == "up"
    )


@pytest.mark.level0
def test_round_trip_preserves_none_h_sensor() -> None:
    """A legacy payload serializes to the pre-ADR-0011 keys, byte-for-byte."""
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.3)
    d = los.to_dict()
    assert "h_sensor" not in d
    assert set(d) == {"h_tgt", "h_atm_top", "theta_o", "theta_s", "delta_phi"}
    assert LineOfSightGeometry.from_dict(d) == los


@pytest.mark.level0
def test_from_dict_accepts_explicit_none_h_sensor() -> None:
    d = {"h_tgt": 0.0, "h_atm_top": 1.0e5, "theta_o": 0.3, "h_sensor": None}
    assert LineOfSightGeometry.from_dict(d).h_sensor is None


@pytest.mark.level0
def test_round_trip_preserves_h_sensor_value() -> None:
    los = LineOfSightGeometry(h_tgt=1000.0, theta_o=0.3, h_sensor=500_000.0)
    rebuilt = LineOfSightGeometry.from_dict(los.to_dict())
    assert rebuilt == los
    assert rebuilt.h_sensor == 500_000.0


@pytest.mark.level0
def test_from_dict_of_old_payload_without_h_sensor() -> None:
    """Back-compat: a pre-ADR-0011 payload has no h_sensor key at all."""
    old = {"h_tgt": 0.0, "h_atm_top": 1.0e5, "theta_o": 0.3, "theta_s": None, "delta_phi": None}
    los = LineOfSightGeometry.from_dict(old)
    assert los.h_sensor is None
    assert los.theta_o == 0.3


@pytest.mark.level0
def test_negative_h_sensor_field_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="h_sensor"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=0.3, h_sensor=-1.0)


# ---------------------------------------------------------------------------
# Extended theta_o domain + hemisphere invariant
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_theta_o_pi_is_legal_up_looking() -> None:
    """Vertical up-looking (LEO under GEO) is θ_o = π exactly."""
    los = LineOfSightGeometry(h_tgt=H_GEO, theta_o=math.pi, h_sensor=500_000.0, h_atm_top=1.0e5)
    assert los.theta_o == math.pi
    assert los.is_uplooking


@pytest.mark.level0
def test_theta_o_beyond_pi_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="theta_o"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.pi + 1e-9)


@pytest.mark.level0
def test_hemisphere_invariant_violation_raises() -> None:
    """Sensor below target with an acute θ_o is not a viewing geometry."""
    with pytest.raises(ParameterBoundsError):
        LineOfSightGeometry(h_tgt=400_000.0, theta_o=0.3, h_sensor=100_000.0, h_atm_top=5.0e5)


@pytest.mark.level0
def test_hemisphere_invariant_error_names_altitudes() -> None:
    with pytest.raises(ParameterBoundsError) as exc:
        LineOfSightGeometry(h_tgt=400_000.0, theta_o=0.3, h_sensor=100_000.0, h_atm_top=5.0e5)
    msg = str(exc.value)
    assert "400000" in msg and "100000" in msg
    assert "hemisphere" in msg


# ---------------------------------------------------------------------------
# Horizon guard at the contract boundary
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_grazing_down_looking_raises_with_h_sensor() -> None:
    with pytest.raises(ParameterBoundsError, match="horizon guard"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(89.7), h_sensor=500_000.0)


@pytest.mark.level0
def test_shoulder_down_looking_warns_with_h_sensor() -> None:
    with pytest.warns(UserWarning, match="refraction"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(89.0), h_sensor=500_000.0)


@pytest.mark.level0
def test_ordinary_slant_is_silent() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(60.0), h_sensor=500_000.0)


@pytest.mark.level0
def test_legacy_payload_grazing_theta_o_raises() -> None:
    """Without h_sensor the conservative angular band still applies."""
    with pytest.raises(ParameterBoundsError, match="theta_o"):
        LineOfSightGeometry(h_tgt=0.0, theta_o=math.radians(89.8))


@pytest.mark.level0
def test_level_towers_are_admissible() -> None:
    theta_o = level_theta_o_from_central_angle_rad(level_central_angle_from_slant_m(8_000.0, 30.0))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        los = LineOfSightGeometry(h_tgt=30.0, theta_o=theta_o, h_sensor=30.0)
    assert los.los_direction == "level"


@pytest.mark.level0
def test_deep_level_transit_raises() -> None:
    theta_o = level_theta_o_from_central_angle_rad(
        level_central_angle_from_slant_m(500_000.0, 5_000.0)
    )
    with pytest.raises(ParameterBoundsError, match="tangent"):
        LineOfSightGeometry(h_tgt=5_000.0, theta_o=theta_o, h_sensor=5_000.0)


# ---------------------------------------------------------------------------
# intercepts_earth — root-selection fix
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_leo_under_geo_does_not_intercept() -> None:
    """Regression: the '+' root used to pick the through-Earth intersection."""
    los = LineOfSightGeometry(h_tgt=H_GEO, theta_o=math.pi, h_sensor=500_000.0, h_atm_top=1.0e5)
    assert not los.intercepts_earth(500_000.0)


@pytest.mark.level0
def test_up_looking_ground_to_air_does_not_intercept() -> None:
    los = LineOfSightGeometry(
        h_tgt=10_000.0, theta_o=math.radians(175.0), h_sensor=0.0, h_atm_top=1.0e5
    )
    assert not los.intercepts_earth(0.0)


@pytest.mark.level0
def test_level_path_below_the_surface_intercepts() -> None:
    """Two 500 m hilltops 175 km apart: the chord passes ~100 m underground."""
    theta_o = level_theta_o_from_central_angle_rad(
        level_central_angle_from_slant_m(175_000.0, 500.0)
    )
    with pytest.warns(UserWarning):
        los = LineOfSightGeometry(h_tgt=500.0, theta_o=theta_o, h_sensor=500.0)
    assert los.intercepts_earth(500.0)


@pytest.mark.level0
def test_short_level_path_does_not_intercept() -> None:
    theta_o = level_theta_o_from_central_angle_rad(level_central_angle_from_slant_m(8_000.0, 30.0))
    los = LineOfSightGeometry(h_tgt=30.0, theta_o=theta_o, h_sensor=30.0)
    assert not los.intercepts_earth(30.0)


@pytest.mark.level0
def test_impossible_geometry_raises_instead_of_returning_true() -> None:
    """A sensor shell the ray never reaches is a bad input, not an intercept."""
    los = LineOfSightGeometry(h_tgt=400_000.0, theta_o=1.55, h_atm_top=5.0e5)
    with pytest.raises(ParameterBoundsError):
        los.intercepts_earth(100_000.0)


# ---------------------------------------------------------------------------
# Up-looking atmospheric column — Phase 2 guard (Gaps 108/109)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_up_looking_slant_range_atm_raises() -> None:
    los = LineOfSightGeometry(
        h_tgt=10_000.0, theta_o=math.radians(175.0), h_sensor=0.0, h_atm_top=1.0e5
    )
    with pytest.raises(ParameterBoundsError, match="Phase 2"):
        _ = los.slant_range_atm


@pytest.mark.level0
def test_up_looking_airmass_raises() -> None:
    los = LineOfSightGeometry(
        h_tgt=10_000.0, theta_o=math.radians(175.0), h_sensor=0.0, h_atm_top=1.0e5
    )
    with pytest.raises(ParameterBoundsError, match="Phase 2"):
        _ = los.path_airmass_up


@pytest.mark.level0
def test_up_looking_exo_target_keeps_vacuum_limits() -> None:
    """The LEO→GEO quick win: exo target ⇒ 0.0 m column and airmass 1.0."""
    los = LineOfSightGeometry(h_tgt=H_GEO, theta_o=math.pi, h_sensor=500_000.0, h_atm_top=1.0e5)
    assert los.slant_range_atm == 0.0
    assert los.path_airmass_up == 1.0
