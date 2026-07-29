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
import warnings

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import (
    GUARD_DH_CLEAN_M,
    GUARD_DH_RAISE_M,
    GUARD_HARD_RAD,
    GUARD_WARN_RAD,
    check_horizon_guard,
    classify_horizon_topology,
    eta_from_theta_o,
    ground_range_from_theta_o_m,
    level_central_angle_from_ground_arc_m,
    level_central_angle_from_slant_m,
    level_slant_range_from_central_angle_m,
    level_theta_o_from_central_angle_rad,
    slant_range_from_theta_o_m,
    solve_from_lower_zenith,
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


# ===========================================================================
# Phase 1 (ADR-0011) — direction-general viewing triangle
# ===========================================================================

H_GEO = 35_786_000.0  # m


class TestHemisphereInvariant:
    """Altitude/hemisphere invariant: h_s > h_t ⟺ θ_o < π/2 (ADR-0011)."""

    def test_sensor_above_with_obtuse_theta_o_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="hemisphere|below"):
            slant_range_from_theta_o_m(math.radians(120.0), H_LEO, 0.0)

    def test_sensor_below_with_acute_theta_o_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="hemisphere|above"):
            slant_range_from_theta_o_m(math.radians(30.0), 0.0, H_LEO)

    def test_equal_altitudes_with_acute_theta_o_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            slant_range_from_theta_o_m(math.radians(80.0), 5000.0, 5000.0)

    def test_error_names_both_altitudes(self) -> None:
        with pytest.raises(ParameterBoundsError) as exc:
            eta_from_theta_o(math.radians(30.0), 1000.0, 2000.0)
        msg = str(exc.value)
        assert "1000" in msg and "2000" in msg

    def test_theta_o_beyond_pi_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            slant_range_from_theta_o_m(math.pi + 1e-9, 0.0, H_LEO)

    def test_theta_o_exactly_pi_is_legal(self) -> None:
        """θ_o = π (vertical up-looking) is IN the closed domain [0, π]."""
        d = slant_range_from_theta_o_m(math.pi, H_LEO, H_GEO)
        assert d == pytest.approx(H_GEO - H_LEO, rel=1e-12)


class TestVerticalLimits:
    """Truth anchor: the two collinear limits are exact altitude differences."""

    def test_nadir_limit_down_looking(self) -> None:
        assert slant_range_from_theta_o_m(0.0, H_GEO, H_LEO) == pytest.approx(
            H_GEO - H_LEO, rel=1e-12
        )

    def test_zenith_limit_up_looking(self) -> None:
        """LEO sensor directly under a GEO target: d = h_t − h_s exactly."""
        assert slant_range_from_theta_o_m(math.pi, H_LEO, H_GEO) == pytest.approx(
            H_GEO - H_LEO, rel=1e-12
        )

    def test_zenith_limit_ground_to_space(self) -> None:
        assert slant_range_from_theta_o_m(math.pi, 0.0, H_LEO) == pytest.approx(H_LEO, rel=1e-12)

    def test_eta_at_zenith_limit_is_pi(self) -> None:
        """θ_o = π ⇒ the sensor sees the target straight up: η_int = π."""
        assert eta_from_theta_o(math.pi, H_LEO, H_GEO) == pytest.approx(math.pi, abs=1e-12)

    def test_ground_range_zero_at_zenith_limit(self) -> None:
        assert ground_range_from_theta_o_m(math.pi, H_LEO, H_GEO) == pytest.approx(0.0, abs=1e-6)


class TestRoleSwapIdentity:
    """Anchor: the up-looking triangle is the down-looking triangle read
    from the other vertex.  θ_o' = π − η_int and η_int' = π − θ_o."""

    CASES = [
        (math.radians(172.0), 0.0, H_LEO),
        (math.radians(160.0), 0.0, 100_000.0),
        (3.0, 500_000.0, H_GEO),
    ]

    @pytest.mark.parametrize("theta_o,h_s,h_t", CASES)
    def test_role_swap_recovers_theta_o(self, theta_o: float, h_s: float, h_t: float) -> None:
        eta_int = eta_from_theta_o(theta_o, h_s, h_t)
        theta_o_swapped = math.pi - eta_int
        # Swapped triangle: the old sensor becomes the target and vice versa.
        eta_swapped = eta_from_theta_o(theta_o_swapped, h_t, h_s)
        assert eta_swapped == pytest.approx(math.pi - theta_o, rel=1e-9, abs=1e-12)

    @pytest.mark.parametrize("theta_o,h_s,h_t", CASES)
    def test_role_swap_preserves_slant_range(self, theta_o: float, h_s: float, h_t: float) -> None:
        eta_int = eta_from_theta_o(theta_o, h_s, h_t)
        d_up = slant_range_from_theta_o_m(theta_o, h_s, h_t)
        d_down = slant_range_from_theta_o_m(math.pi - eta_int, h_t, h_s)
        assert d_down == pytest.approx(d_up, rel=1e-9)

    @pytest.mark.parametrize("theta_o,h_s,h_t", CASES)
    def test_law_of_sines_holds_both_ways(self, theta_o: float, h_s: float, h_t: float) -> None:
        """r_t·sin(θ_o) = r_s·sin(η_int) — the invariant perigee radius."""
        eta_int = eta_from_theta_o(theta_o, h_s, h_t)
        r_t = R_EARTH_M + h_t
        r_s = R_EARTH_M + h_s
        assert r_t * math.sin(theta_o) == pytest.approx(r_s * math.sin(eta_int), rel=1e-12)

    @pytest.mark.parametrize("theta_o,h_s,h_t", CASES)
    def test_central_angle_matches_law_of_cosines(
        self, theta_o: float, h_s: float, h_t: float
    ) -> None:
        r_t = R_EARTH_M + h_t
        r_s = R_EARTH_M + h_s
        d = slant_range_from_theta_o_m(theta_o, h_s, h_t)
        cos_delta = (r_t * r_t + r_s * r_s - d * d) / (2.0 * r_t * r_s)
        delta_cos = math.acos(max(-1.0, min(1.0, cos_delta)))
        delta_ang = theta_o - eta_from_theta_o(theta_o, h_s, h_t)
        assert delta_ang == pytest.approx(delta_cos, rel=1e-6, abs=1e-9)


class TestUpLookingSolutions:
    """Up-looking near-branch solutions (h_sensor < h_target)."""

    def test_ground_to_leo_slant_range(self) -> None:
        """Ground sensor, h_t = 500 km, θ_o = 170°: d = 508 334.28 m.

        Truth anchor computed three independent ways off-line
        (r_t = 6 871 000 m, r_s = 6 371 000 m):
          1. law-of-cosines near root  −r_t cosθ − √(r_t²cos²θ + r_s² − r_t²)
          2. sine-rule route: η = π − asin((r_t/r_s) sinθ), φ = θ − η,
             d = √(r_t² + r_s² − 2 r_t r_s cos φ)
          3. bisection on |T + t·û| = r_s in the target-local plane
        All three give 508 334.2765 m; the vector check confirms the
        end point lands exactly on the sensor shell.
        """
        d = slant_range_from_theta_o_m(math.radians(170.0), 0.0, 500_000.0)
        assert d == pytest.approx(508_334.2765, rel=1e-9)

    def test_near_branch_is_the_short_root(self) -> None:
        """The '−' root is selected: d < the through-Earth far root."""
        d = slant_range_from_theta_o_m(math.radians(170.0), 0.0, 500_000.0)
        assert d < 1_000_000.0

    def test_ground_range_round_trip_up_looking(self) -> None:
        theta_o = math.radians(170.0)
        s = ground_range_from_theta_o_m(theta_o, 0.0, 500_000.0)
        assert s > 0.0
        assert theta_o_from_ground_range_m(s, 0.0, 500_000.0) == pytest.approx(theta_o, rel=1e-9)

    def test_eta_is_obtuse_up_looking(self) -> None:
        """The sensor looks ABOVE its own horizontal: η_int > π/2."""
        eta = eta_from_theta_o(math.radians(170.0), 0.0, 500_000.0)
        assert eta > math.pi / 2.0

    def test_unreachable_shell_raises(self) -> None:
        """A ray whose perigee never descends to the sensor shell raises."""
        # Target at 500 km, θ_o = 100° ⇒ perigee radius r_t sin(100°) is far
        # above a ground sensor's radius — no solution.
        with pytest.raises(ParameterBoundsError, match="perigee|never"):
            slant_range_from_theta_o_m(math.radians(100.0), 0.0, 500_000.0)


class TestSolveFromLowerZenith:
    """Unambiguous lower-endpoint construction (ADR-0011 decision 3)."""

    def test_vertical_ascent_gives_altitude_difference(self) -> None:
        sol = solve_from_lower_zenith(0.0, 0.0, 500_000.0)
        assert sol.slant_range_m == pytest.approx(500_000.0, rel=1e-12)
        assert sol.central_angle_rad == pytest.approx(0.0, abs=1e-12)
        assert sol.theta_o_rad == pytest.approx(math.pi, abs=1e-12)

    def test_agrees_with_theta_o_solver_on_the_near_branch(self) -> None:
        """ζ_low ≤ π/2 ⇒ near branch ⇒ both doors give the same triangle."""
        sol = solve_from_lower_zenith(math.radians(20.0), 0.0, 500_000.0)
        d = slant_range_from_theta_o_m(sol.theta_o_rad, 0.0, 500_000.0)
        assert d == pytest.approx(sol.slant_range_m, rel=1e-9)

    def test_down_looking_equivalent(self) -> None:
        """Lower endpoint = target ⇒ ζ_low IS θ_o and d matches the legacy solver."""
        sol = solve_from_lower_zenith(math.radians(45.0), 0.0, H_LEO)
        d_legacy = slant_range_from_theta_o_m(math.radians(45.0), H_LEO, 0.0)
        assert sol.slant_range_m == pytest.approx(d_legacy, rel=1e-12)
        assert sol.eta_int_rad == pytest.approx(
            eta_from_theta_o(math.radians(45.0), H_LEO, 0.0), rel=1e-12
        )

    def test_central_angle_is_zeta_difference(self) -> None:
        sol = solve_from_lower_zenith(math.radians(60.0), 1000.0, 200_000.0)
        assert sol.central_angle_rad == pytest.approx(sol.zeta_low_rad - sol.zeta_up_rad, rel=1e-12)

    def test_theta_o_is_supplement_of_zeta_up(self) -> None:
        sol = solve_from_lower_zenith(math.radians(30.0), 0.0, 400_000.0)
        assert sol.theta_o_rad == pytest.approx(math.pi - sol.zeta_up_rad, rel=1e-12)

    def test_descending_shoulder_still_unique(self) -> None:
        """ζ_low just past π/2 dips to perigee then ascends — one solution."""
        with pytest.warns(UserWarning):
            sol = solve_from_lower_zenith(math.radians(90.8), 10_000.0, 10_100.0)
        assert sol.slant_range_m > 0.0
        assert sol.zeta_up_rad < math.pi / 2.0

    def test_inverted_altitudes_raise(self) -> None:
        with pytest.raises(ParameterBoundsError):
            solve_from_lower_zenith(0.0, 500_000.0, 0.0)


class TestLevelPaths:
    """Equal-altitude (horizontal) central-angle solutions."""

    def test_towers_theta_o(self) -> None:
        """Two 30 m towers 8 km apart: θ_o = 90.036°."""
        delta = level_central_angle_from_slant_m(8_000.0, 30.0)
        theta_o = level_theta_o_from_central_angle_rad(delta)
        assert math.degrees(theta_o) == pytest.approx(90.036, abs=1e-3)

    def test_slant_round_trip(self) -> None:
        delta = level_central_angle_from_slant_m(8_000.0, 30.0)
        assert level_slant_range_from_central_angle_m(delta, 30.0) == pytest.approx(
            8_000.0, rel=1e-12
        )

    def test_theta_o_solver_reproduces_level_slant(self) -> None:
        """The general θ_o solver takes the far root at equal altitudes."""
        delta = level_central_angle_from_slant_m(8_000.0, 30.0)
        theta_o = level_theta_o_from_central_angle_rad(delta)
        assert slant_range_from_theta_o_m(theta_o, 30.0, 30.0) == pytest.approx(8_000.0, rel=1e-9)

    def test_eta_int_is_supplement_at_equal_altitudes(self) -> None:
        delta = level_central_angle_from_slant_m(8_000.0, 30.0)
        theta_o = level_theta_o_from_central_angle_rad(delta)
        assert eta_from_theta_o(theta_o, 30.0, 30.0) == pytest.approx(math.pi - theta_o, rel=1e-12)

    def test_ground_arc_form(self) -> None:
        assert level_central_angle_from_ground_arc_m(R_EARTH_M * 0.01) == pytest.approx(
            0.01, rel=1e-12
        )

    def test_lab_bench_is_essentially_horizontal(self) -> None:
        """5 m bench at one altitude: θ_o ≈ π/2, tangent depression ~5e−7 m."""
        delta = level_central_angle_from_slant_m(5.0, 0.0)
        theta_o = level_theta_o_from_central_angle_rad(delta)
        assert theta_o == pytest.approx(math.pi / 2.0, abs=1e-6)
        guard = classify_horizon_topology(theta_o, 0.0, 0.0)
        assert guard.action == "clean"
        assert guard.dh_m is not None and guard.dh_m < 1e-5

    def test_negative_slant_raises(self) -> None:
        with pytest.raises(ParameterBoundsError):
            level_central_angle_from_slant_m(-1.0, 0.0)


class TestHorizonGuard:
    """Two-tier horizon guard (plan §8.3 addendum)."""

    def _level_theta_o(self, slant_m: float, h_m: float) -> float:
        return level_theta_o_from_central_angle_rad(level_central_angle_from_slant_m(slant_m, h_m))

    def test_towers_are_clean(self) -> None:
        theta_o = self._level_theta_o(8_000.0, 30.0)
        guard = classify_horizon_topology(theta_o, 30.0, 30.0)
        assert guard.topology == "interior_tangent"
        assert guard.action == "clean"
        assert guard.dh_m == pytest.approx(1.26, abs=0.1)

    def test_two_hundred_km_level_warns(self) -> None:
        theta_o = self._level_theta_o(200_000.0, 10_000.0)
        guard = classify_horizon_topology(theta_o, 10_000.0, 10_000.0)
        assert guard.topology == "interior_tangent"
        assert guard.action == "warn"
        assert guard.dh_m == pytest.approx(785.0, rel=0.02)
        with pytest.warns(UserWarning, match="refraction"):
            check_horizon_guard(theta_o, 10_000.0, 10_000.0, where="test")

    def test_shoulder_warning_sizes_the_refraction_it_excludes(self) -> None:
        """CU-269: the warn shoulder must quantify what it is leaving out.

        Under the standard k = 4/3 effective-radius model the tangent depression
        of a fixed geometry scales as 1/k, so a warned path bottoms out ``dh/k``
        below its endpoints instead of ``dh``. Hand-check against the CU's own
        independently-derived scenario-10.2 figures: dh = 195.9 m refracts to
        146.9 m, a path-mean sampling-altitude error of 32.6 m (two-thirds of the
        49.0 m peak, the depression profile being parabolic about the tangent).
        """
        from radiant.core.viewing_triangle import GUARD_REFRACTION_K

        dh = 195.9
        refracted = dh / GUARD_REFRACTION_K
        mean_error = (2.0 / 3.0) * (dh - refracted)
        assert refracted == pytest.approx(146.9, abs=0.1)
        assert mean_error == pytest.approx(32.6, abs=0.1)

        # And the emitted warning carries the numbers, not just the caveat.
        theta_o = self._level_theta_o(200_000.0, 10_000.0)
        with pytest.warns(UserWarning) as record:
            guard = check_horizon_guard(theta_o, 10_000.0, 10_000.0, where="test")
        assert guard.dh_m is not None
        text = str(record[0].message)
        assert "refraction is NOT modelled" in text
        assert f"{guard.dh_m / GUARD_REFRACTION_K:.1f} m" in text
        assert "on average" in text

    def test_endpoint_minimum_shoulder_says_the_size_does_not_apply(self) -> None:
        """A slant with no interior tangent must not quote a tangent-depression number.

        Its closest approach is its lower endpoint, so the refraction omission is a
        path-length effect, not a sampling-altitude one — the warning says that
        rather than printing a figure that does not describe this geometry.
        """
        with pytest.warns(UserWarning) as record:
            guard = check_horizon_guard(math.radians(89.0), H_LEO, 0.0, where="test")
        assert guard.dh_m is None
        text = str(record[0].message)
        assert "no interior tangent point" in text
        assert "not sized here" in text

    def test_deep_level_transit_raises(self) -> None:
        theta_o = self._level_theta_o(500_000.0, 5_000.0)
        guard = classify_horizon_topology(theta_o, 5_000.0, 5_000.0)
        assert guard.action == "raise"
        assert guard.dh_m == pytest.approx(4_900.0, rel=0.02)
        with pytest.raises(ParameterBoundsError, match="tangent"):
            check_horizon_guard(theta_o, 5_000.0, 5_000.0, where="test")

    def test_grazing_down_looking_raises(self) -> None:
        guard = classify_horizon_topology(math.radians(89.7), H_LEO, 0.0)
        assert guard.topology == "endpoint_minimum"
        assert guard.action == "raise"
        with pytest.raises(ParameterBoundsError):
            check_horizon_guard(math.radians(89.7), H_LEO, 0.0, where="test")

    def test_near_horizon_down_looking_warns(self) -> None:
        guard = classify_horizon_topology(math.radians(89.0), H_LEO, 0.0)
        assert guard.topology == "endpoint_minimum"
        assert guard.action == "warn"
        # ``band_rad`` is ``float | None`` — populated only for the
        # endpoint_minimum topology asserted above.  The explicit check both
        # narrows the type for ``mypy --strict`` and pins the contract.
        assert guard.band_rad is not None
        assert math.degrees(guard.band_rad) == pytest.approx(1.0, abs=1e-9)
        with pytest.warns(UserWarning):
            check_horizon_guard(math.radians(89.0), H_LEO, 0.0, where="test")

    def test_ordinary_slant_is_clean_and_silent(self) -> None:
        guard = classify_horizon_topology(math.radians(75.0), H_LEO, 0.0)
        assert guard.action == "clean"
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            check_horizon_guard(math.radians(75.0), H_LEO, 0.0, where="test")

    def test_vertical_up_looking_is_clean(self) -> None:
        guard = classify_horizon_topology(math.pi, H_LEO, H_GEO)
        assert guard.action == "clean"

    def test_band_thresholds_are_named_constants(self) -> None:
        # Stored in radians (Rule 2 / CU-222); the ratified degree values
        # are what the plan and ADR quote, so both readings are pinned.
        assert math.radians(0.5) == GUARD_HARD_RAD
        assert math.radians(2.0) == GUARD_WARN_RAD
        assert math.degrees(GUARD_HARD_RAD) == pytest.approx(0.5, abs=1e-12)
        assert math.degrees(GUARD_WARN_RAD) == pytest.approx(2.0, abs=1e-12)
        assert GUARD_DH_CLEAN_M == 100.0
        assert GUARD_DH_RAISE_M == 2000.0
