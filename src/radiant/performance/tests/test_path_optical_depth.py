"""Level 0 tests for the path optical-depth profile (finding GF-15).

Covers the three solvable topologies, the refusal case, and the closed-form
column-exit geometry (verified against an independent chord construction).
"""

from __future__ import annotations

import math

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.performance.errors import PerformanceValidationError
from radiant.performance.path_optical_depth import (
    LEVEL_ARM_MAX_RANGE_M,
    LEVEL_ARM_SAG_CEILING_M,
    column_exit_range_m,
    resolve_path_optical_depth,
)


def _vertical_up(h_sensor_m: float, h_target_m: float) -> LineOfSightGeometry:
    """Sensor below the target, target straight overhead (θ_o = π)."""
    return LineOfSightGeometry(
        h_tgt=h_target_m,
        h_sensor=h_sensor_m,
        theta_o=math.pi,
    )


class TestColumnExitGeometry:
    @pytest.mark.level0
    def test_vertical_ray_exits_at_the_altitude_difference(self) -> None:
        """Anchor: straight up from 0 m, h_atm_top = 100 km ⇒ exit at 100 km."""
        los = _vertical_up(0.0, 3.0e5)
        assert column_exit_range_m(los) == pytest.approx(1.0e5, rel=1e-9)

    @pytest.mark.level0
    def test_vertical_ray_from_altitude(self) -> None:
        los = _vertical_up(2.0e4, 3.0e5)
        assert column_exit_range_m(los) == pytest.approx(8.0e4, rel=1e-9)

    @pytest.mark.level0
    def test_sensor_above_column_top_exits_immediately(self) -> None:
        los = _vertical_up(2.0e5, 4.0e7)
        assert column_exit_range_m(los) == 0.0

    @pytest.mark.level0
    def test_slant_ray_matches_independent_chord_solution(self) -> None:
        """Anchor: solve r(s) = r_top by direct root of the quadratic in s.

        Independent construction: walk the ray numerically and bisect on the
        radius, rather than using the closed form under test.
        """
        los = LineOfSightGeometry(h_tgt=5.0e5, h_sensor=1.0e4, theta_o=2.6)
        s_closed = column_exit_range_m(los)

        from radiant.core.viewing_triangle import eta_from_theta_o

        r_0 = R_EARTH_M + 1.0e4
        cos_zeta = math.cos(math.pi - eta_from_theta_o(2.6, 1.0e4, 5.0e5))

        def radius(s: float) -> float:
            return math.sqrt(r_0**2 + s**2 + 2.0 * r_0 * s * cos_zeta)

        lo, hi = 0.0, 5.0e6
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if radius(mid) < R_EARTH_M + 1.0e5:
                lo = mid
            else:
                hi = mid
        assert s_closed == pytest.approx(0.5 * (lo + hi), rel=1e-6)

    @pytest.mark.level0
    def test_slant_exit_exceeds_vertical_exit(self) -> None:
        """A slanted ray traverses more path before leaving the column."""
        vertical = column_exit_range_m(_vertical_up(0.0, 5.0e5))
        slant = column_exit_range_m(LineOfSightGeometry(h_tgt=5.0e5, h_sensor=0.0, theta_o=2.6))
        assert slant > vertical

    @pytest.mark.level0
    def test_level_los_is_rejected(self) -> None:
        """A constant-altitude arm never crosses the shell (CU-263)."""
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        with pytest.raises(PerformanceValidationError, match="level"):
            column_exit_range_m(los)

    @pytest.mark.level0
    def test_down_looking_nadir_exit_is_the_column_top(self) -> None:
        """θ_o = 0 from a ground target ⇒ exit at h_atm_top − h_tgt exactly.

        The down-looking ray's lower endpoint is the *target*, and its
        target-referenced zenith is already the lower-endpoint zenith
        (ADR-0011 decision 3), so no η conversion applies.
        """
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=5.0e5, theta_o=0.0)
        assert column_exit_range_m(los) == pytest.approx(los.h_atm_top, rel=1e-9)

    @pytest.mark.level0
    def test_down_looking_slant_exit_exceeds_the_nadir_exit(self) -> None:
        nadir = column_exit_range_m(LineOfSightGeometry(h_tgt=0.0, h_sensor=5.0e5, theta_o=0.0))
        slant = column_exit_range_m(LineOfSightGeometry(h_tgt=0.0, h_sensor=5.0e5, theta_o=0.6))
        assert slant > nadir


class TestUpLookingVacuumTail:
    @pytest.mark.level0
    def test_exo_target_freezes_the_optical_depth(self) -> None:
        """Target above h_atm_top ⇒ every further metre is vacuum."""
        los = _vertical_up(0.0, 5.0e5)
        res = resolve_path_optical_depth(los, ref_range_m=5.0e5, ref_optical_depth=0.7)
        assert res.ok
        profile = res.profile
        assert profile is not None
        assert profile.topology == "up_vacuum_tail"
        assert profile.optical_depth_at(5.0e5) == pytest.approx(0.7, rel=1e-14)
        assert profile.optical_depth_at(5.0e7) == pytest.approx(0.7, rel=1e-14)
        assert profile.transmittance_ratio(5.0e7) == pytest.approx(1.0, rel=1e-14)

    @pytest.mark.level0
    def test_transparent_path_is_pure_vacuum(self) -> None:
        los = _vertical_up(0.0, 5.0e4)
        res = resolve_path_optical_depth(los, ref_range_m=5.0e4, ref_optical_depth=0.0)
        assert res.ok
        assert res.profile is not None
        assert res.profile.topology == "vacuum"
        assert res.profile.transmittance_ratio(1.0e9) == 1.0

    @pytest.mark.level0
    def test_in_column_continuation_is_refused_not_guessed(self) -> None:
        """Rule 17: the constant-α model is not silently reused here."""
        los = _vertical_up(0.0, 3.0e4)  # target at 30 km, column top at 100 km
        res = resolve_path_optical_depth(los, ref_range_m=3.0e4, ref_optical_depth=0.9)
        assert not res.ok
        assert res.profile is None
        assert res.failure_reason is not None
        assert "GF-15" in res.failure_reason
        assert "h_atm_top" in res.failure_reason


class TestLevelArm:
    @pytest.mark.level0
    def test_constant_extinction_is_exact_for_a_level_arm(self) -> None:
        """OD(R) = α R with α = OD_ref / R_ref — the arm's own model."""
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        res = resolve_path_optical_depth(los, ref_range_m=1.5e5, ref_optical_depth=0.6)
        assert res.ok
        profile = res.profile
        assert profile is not None
        assert profile.topology == "level"
        assert profile.extinction_per_m == pytest.approx(0.6 / 1.5e5, rel=1e-14)
        assert profile.optical_depth_at(3.0e5) == pytest.approx(1.2, rel=1e-12)
        assert profile.transmittance_ratio(3.0e5) == pytest.approx(math.exp(-0.6), rel=1e-12)

    @pytest.mark.level0
    def test_validity_bound_is_the_two_km_sag_threshold(self) -> None:
        """L = sqrt(8 R_E Δh) with Δh = 2 km ⇒ ≈ 319 km."""
        expected = math.sqrt(8.0 * R_EARTH_M * LEVEL_ARM_SAG_CEILING_M)
        assert pytest.approx(expected, rel=1e-14) == LEVEL_ARM_MAX_RANGE_M
        assert pytest.approx(3.19e5, rel=2e-2) == LEVEL_ARM_MAX_RANGE_M

    @pytest.mark.level0
    def test_level_profile_carries_the_validity_bound(self) -> None:
        los = LineOfSightGeometry(h_tgt=5.0e3, h_sensor=5.0e3, theta_o=math.pi / 2.0)
        res = resolve_path_optical_depth(los, ref_range_m=5.0e4, ref_optical_depth=0.2)
        assert res.profile is not None
        assert res.profile.max_valid_range_m == LEVEL_ARM_MAX_RANGE_M


class TestMonotonicityAndFailureModes:
    @pytest.mark.level0
    def test_optical_depth_is_monotone_non_decreasing(self) -> None:
        los = LineOfSightGeometry(h_tgt=1.0e4, h_sensor=1.0e4, theta_o=math.pi / 2.0)
        profile = resolve_path_optical_depth(los, 5.0e4, 0.3).profile
        assert profile is not None
        previous = -1.0
        for r in (5.0e4, 1.0e5, 2.0e5, 3.0e5):
            value = profile.optical_depth_at(r)
            assert value >= previous
            previous = value

    @pytest.mark.level0
    def test_evaluating_inside_the_measured_leg_raises(self) -> None:
        los = _vertical_up(0.0, 5.0e5)
        profile = resolve_path_optical_depth(los, 5.0e5, 0.4).profile
        assert profile is not None
        with pytest.raises(PerformanceValidationError, match="inside the measured leg"):
            profile.optical_depth_at(1.0e5)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_non_physical_range_raises(self, bad: float) -> None:
        los = _vertical_up(0.0, 5.0e5)
        profile = resolve_path_optical_depth(los, 5.0e5, 0.4).profile
        assert profile is not None
        with pytest.raises(PerformanceValidationError):
            profile.optical_depth_at(bad)

    @pytest.mark.level0
    def test_down_looking_resolves_to_a_vacuum_tail(self) -> None:
        """CU-263 (ex-CU-236): the down arm is resolved here, not refused."""
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=5.0e5, theta_o=0.2)
        resolution = resolve_path_optical_depth(los, 5.1e5, 0.4)
        assert resolution.ok
        assert resolution.profile is not None
        assert resolution.profile.topology == "down_vacuum_tail"
        assert resolution.profile.extinction_per_m == 0.0

    @pytest.mark.level0
    def test_down_looking_from_inside_the_column_is_refused(self) -> None:
        """An airborne sensor's receding leg is in air the metric layer cannot model."""
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=8.0e3, theta_o=0.2)
        resolution = resolve_path_optical_depth(los, 8.2e3, 0.4)
        assert not resolution.ok
        assert resolution.profile is None
        assert resolution.failure_reason is not None
        assert "down-looking" in resolution.failure_reason

    @pytest.mark.level0
    @pytest.mark.parametrize("bad_range", [0.0, -1.0, float("nan")])
    def test_non_physical_reference_range_raises(self, bad_range: float) -> None:
        los = _vertical_up(0.0, 5.0e5)
        with pytest.raises(PerformanceValidationError, match="ref_range_m"):
            resolve_path_optical_depth(los, bad_range, 0.4)

    @pytest.mark.level0
    def test_negative_optical_depth_raises(self) -> None:
        los = _vertical_up(0.0, 5.0e5)
        with pytest.raises(PerformanceValidationError, match="ref_optical_depth"):
            resolve_path_optical_depth(los, 5.0e5, -0.1)
