"""Level-0 tests for the spherical-shell crossing range (CU-237).

The computation was duplicated between ``viewing_triangle.solve_from_lower_zenith``
and ``performance.path_optical_depth.column_exit_range_m``; these pin the shared
function against closed-form values that need no RADIANT code to derive.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.shell_crossing import slant_range_to_shell_m


class TestShellCrossing:
    @pytest.mark.level0
    def test_straight_up_is_the_altitude_difference(self) -> None:
        """ζ = 0: the ray is radial, so the range is exactly Δh."""
        assert slant_range_to_shell_m(1_000.0, 0.0, 101_000.0) == pytest.approx(
            100_000.0, rel=1e-12
        )

    @pytest.mark.level0
    def test_horizontal_launch_matches_the_tangent_construction(self) -> None:
        """ζ = π/2: a right triangle on the Earth centre gives √(r_shell² − r_0²)."""
        h0, h_shell = 0.0, 100_000.0
        r0, rs = R_EARTH_M + h0, R_EARTH_M + h_shell
        assert slant_range_to_shell_m(h0, math.pi / 2, h_shell) == pytest.approx(
            math.sqrt(rs * rs - r0 * r0), rel=1e-12
        )

    @pytest.mark.level0
    def test_start_at_or_above_the_shell_has_no_crossing(self) -> None:
        """A sensor already outside the modelled column: 0, not a raise."""
        assert slant_range_to_shell_m(120_000.0, 0.3, 100_000.0) == 0.0
        assert slant_range_to_shell_m(100_000.0, 0.3, 100_000.0) == 0.0

    @pytest.mark.level0
    def test_range_grows_monotonically_with_launch_zenith(self) -> None:
        """A shallower ray travels further to reach the same shell."""
        ranges = [
            slant_range_to_shell_m(0.0, math.radians(d), 80_000.0)
            for d in (0.0, 30.0, 60.0, 85.0, 89.9)
        ]
        assert ranges == sorted(ranges)
        assert ranges[0] == pytest.approx(80_000.0, rel=1e-12)

    @pytest.mark.level0
    def test_agrees_with_the_law_of_cosines_it_inverts(self) -> None:
        """Round-trip: r(s) at the returned s must land back on the shell radius."""
        h0, zeta, h_shell = 2_000.0, math.radians(115.0), 90_000.0
        s = slant_range_to_shell_m(h0, zeta, h_shell)
        r0 = R_EARTH_M + h0
        r_at_s = math.sqrt(r0 * r0 + s * s + 2.0 * r0 * s * math.cos(zeta))
        assert r_at_s == pytest.approx(R_EARTH_M + h_shell, rel=1e-12)
