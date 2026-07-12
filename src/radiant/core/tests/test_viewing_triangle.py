"""Level 0 tests — spherical viewing triangle (θ_o-referenced solutions).

Truth anchors:
  1. Exact nadir identities (analytic): d = h_s − h_t, ground = 0, η = 0.
  2. Plane-parallel limit (analytic): at low altitude the spherical
     solutions reduce to d = h/cos(θ_o), ground = h·tan(θ_o).
  3. Cross-check against the independently tested
     ``los_geometry.theta_o_from_eta`` (inverse identity) and
     ``geometry.incidence_angle_rad`` (η → θ_o forward map).
  4. Internal mathematical identities (law-of-sines vs law-of-cosines
     routes agree to float precision; forward/inverse round trips).
"""

from __future__ import annotations

import math

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import (
    eta_from_theta_o,
    ground_range_from_theta_o_m,
    slant_range_from_theta_o_m,
    theta_o_from_ground_range_m,
)

H_LEO = 500_000.0  # m
H_AIR = 10_000.0  # m


class TestNadirIdentities:
    """Anchor 1 — exact analytic identities at θ_o = 0."""

    def test_slant_range_nadir_is_altitude_difference(self) -> None:
        assert slant_range_from_theta_o_m(0.0, H_LEO) == pytest.approx(H_LEO, rel=1e-12)

    def test_slant_range_nadir_with_elevated_target(self) -> None:
        assert slant_range_from_theta_o_m(0.0, H_LEO, 3000.0) == pytest.approx(
            H_LEO - 3000.0, rel=1e-12
        )

    def test_ground_range_nadir_is_zero(self) -> None:
        assert ground_range_from_theta_o_m(0.0, H_LEO) == pytest.approx(0.0, abs=1e-9)

    def test_eta_nadir_is_zero(self) -> None:
        assert eta_from_theta_o(0.0, H_LEO) == pytest.approx(0.0, abs=1e-12)

    def test_inverse_ground_range_zero_is_nadir(self) -> None:
        assert theta_o_from_ground_range_m(0.0, H_LEO) == pytest.approx(0.0, abs=1e-12)


class TestPlaneParallelLimit:
    """Anchor 2 — at 1 km altitude, spherical ≈ flat to better than 0.1%."""

    H = 1000.0
    THETA = math.radians(30.0)

    def test_slant_range_approaches_sec_theta(self) -> None:
        expected = self.H / math.cos(self.THETA)  # 1154.7005 m
        assert slant_range_from_theta_o_m(self.THETA, self.H) == pytest.approx(expected, rel=1e-3)

    def test_ground_range_approaches_tan_theta(self) -> None:
        expected = self.H * math.tan(self.THETA)  # 577.35 m
        assert ground_range_from_theta_o_m(self.THETA, self.H) == pytest.approx(expected, rel=1e-3)

    def test_eta_approaches_theta_o(self) -> None:
        assert eta_from_theta_o(self.THETA, self.H) == pytest.approx(self.THETA, rel=1e-3)


class TestCrossChecks:
    """Anchor 3 — agreement with independently tested functions."""

    @pytest.mark.parametrize("theta_o", [0.1, 0.3, 0.6, 1.0, 1.4])
    def test_eta_is_exact_inverse_of_theta_o_from_eta(self, theta_o: float) -> None:
        eta = eta_from_theta_o(theta_o, H_LEO, 0.0)
        assert theta_o_from_eta(eta, H_LEO, 0.0) == pytest.approx(theta_o, rel=1e-12)

    @pytest.mark.parametrize("theta_o", [0.1, 0.5, 1.0])
    def test_eta_with_elevated_target(self, theta_o: float) -> None:
        eta = eta_from_theta_o(theta_o, H_LEO, 5000.0)
        assert theta_o_from_eta(eta, H_LEO, 5000.0) == pytest.approx(theta_o, rel=1e-12)

    def test_leo_45deg_eta_magnitude(self) -> None:
        """h = 500 km, θ_o = 45°: sin η = (R_E/(R_E+h))·sin 45° ⇒ η ≈ 40.97°.

        Hand calculation: R_E = 6 371 000 m ⇒ ratio = 6371000/6871000
        = 0.927230; sin η = 0.927230 × 0.707107 = 0.655651;
        η = asin(0.655651) = 0.71504 rad = 40.969°.
        """
        eta = eta_from_theta_o(math.radians(45.0), H_LEO)
        assert eta == pytest.approx(0.71504, abs=2e-5)


class TestInternalConsistency:
    """Anchor 4 — mathematical identities between the solutions."""

    @pytest.mark.parametrize("theta_o", [0.05, 0.4, 0.8, 1.2, 1.5])
    @pytest.mark.parametrize("h_sensor", [H_AIR, H_LEO])
    def test_ground_range_round_trip(self, theta_o: float, h_sensor: float) -> None:
        # rel=1e-6: the inverse goes through acos near cos → −1 at small
        # θ_o / low altitude, where float conditioning limits the round
        # trip to ~1e-8 relative (measured 1.8e-8 at θ_o=0.05, h=10 km).
        s = ground_range_from_theta_o_m(theta_o, h_sensor)
        assert theta_o_from_ground_range_m(s, h_sensor) == pytest.approx(theta_o, rel=1e-6)

    @pytest.mark.parametrize("theta_o", [0.2, 0.9, 1.3])
    def test_law_of_cosines_route_matches_slant(self, theta_o: float) -> None:
        """d via the θ_o quadratic == d via (φ, law of cosines) — identity."""
        r_t = R_EARTH_M
        r_s = R_EARTH_M + H_LEO
        eta = eta_from_theta_o(theta_o, H_LEO)
        phi = theta_o - eta
        d_via_phi = math.sqrt(r_t**2 + r_s**2 - 2.0 * r_t * r_s * math.cos(phi))
        assert slant_range_from_theta_o_m(theta_o, H_LEO) == pytest.approx(d_via_phi, rel=1e-12)

    def test_slant_range_monotonic_in_theta_o(self) -> None:
        d = [slant_range_from_theta_o_m(t, H_LEO) for t in (0.0, 0.3, 0.6, 0.9, 1.2)]
        assert all(a < b for a, b in zip(d, d[1:], strict=False))


class TestFailureModes:
    """Edge-of-domain behavior — all rejections are actionable (Rule 15/16)."""

    def test_theta_o_at_horizontal_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            slant_range_from_theta_o_m(math.pi / 2.0, H_LEO)

    def test_negative_theta_o_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            eta_from_theta_o(-0.1, H_LEO)

    def test_sensor_below_target_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            slant_range_from_theta_o_m(0.3, 1000.0, 2000.0)

    def test_sensor_equal_target_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            eta_from_theta_o(0.3, 5000.0, 5000.0)

    def test_negative_target_altitude_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            slant_range_from_theta_o_m(0.3, H_LEO, -10.0)

    def test_negative_ground_range_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            theta_o_from_ground_range_m(-1.0, H_LEO)

    def test_beyond_horizon_ground_range_raises_with_limit(self) -> None:
        r_t = R_EARTH_M
        r_s = R_EARTH_M + H_LEO
        s_max = R_EARTH_M * (math.pi / 2.0 - math.asin(r_t / r_s))
        with pytest.raises(ParameterBoundsError) as exc:
            theta_o_from_ground_range_m(s_max * 1.01, H_LEO)
        assert "horizon" in str(exc.value)

    def test_just_inside_horizon_ground_range_succeeds(self) -> None:
        r_t = R_EARTH_M
        r_s = R_EARTH_M + H_LEO
        s_max = R_EARTH_M * (math.pi / 2.0 - math.asin(r_t / r_s))
        theta_o = theta_o_from_ground_range_m(s_max * 0.99, H_LEO)
        assert 0.0 < theta_o < math.pi / 2.0
