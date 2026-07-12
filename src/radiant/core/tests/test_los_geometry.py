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

import pytest

from radiant.core.los_geometry import (
    LineOfSightGeometry,
    theta_o_from_eta,
)
from radiant.core.parameters import ParameterBoundsError

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
def test_los_h_tgt_at_top_is_valid_but_airmass_undefined() -> None:
    """h_tgt = h_atm_top is a valid edge (empty column); airmass property raises."""
    los = LineOfSightGeometry(h_tgt=1.0e5, theta_o=0.0)
    assert los.h_tgt == 1.0e5
    # slant_range_atm is 0 exactly at the edge
    assert los.slant_range_atm == pytest.approx(0.0, abs=1e-6)
    # airmass undefined — property raises
    with pytest.raises(ParameterBoundsError, match="vertical column"):
        _ = los.path_airmass_up


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
def test_los_h_tgt_above_top_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        LineOfSightGeometry(h_tgt=2.0e5, theta_o=0.0)


@pytest.mark.level0
def test_los_h_atm_top_less_than_h_tgt_raises() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        LineOfSightGeometry(h_tgt=5.0e4, theta_o=0.0, h_atm_top=1.0e4)


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
def test_los_theta_o_just_below_pi_over_2_valid() -> None:
    """θ_o just below π/2 is valid."""
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=math.pi / 2.0 - 1e-6)
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
