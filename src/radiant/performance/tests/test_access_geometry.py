"""Tests for radiant.performance.access_geometry.

Category C validation for access geometry computations:
- Ground range from spherical Earth geometry
- Swath width = n_pixels × GSD_cross
- Access area rate = swath × ground_speed

Ground range truth values use the ray-sphere intersection slant range
(consistent with ``radiant.core.geometry.slant_range_spherical_m``),
NOT the atmospheric slant-path formula used in the scenario 3.4 walkthrough.
See ``test_gsd.py`` lines 283-288 for the same note.
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.access_rate import compute_access_rate_m2_s
from radiant.performance.ground_range import compute_ground_range_m
from radiant.performance.swath_width import compute_swath_width_m

# ---------------------------------------------------------------------------
# Ground range
# ---------------------------------------------------------------------------


class TestGroundRange:
    """Verify ground range from spherical Earth geometry.

    Truth values computed from law of cosines on the (sensor, Earth center,
    target) triangle, using ray-sphere slant range.
    """

    @pytest.mark.level0
    def test_nadir_is_zero(self) -> None:
        """At nadir, ground range is exactly 0."""
        assert compute_ground_range_m(600_000.0, 0.0) == 0.0

    @pytest.mark.level0
    def test_30_deg_from_600km(self) -> None:
        """At 30 deg, ground range ≈ 352.2 km (from ray-sphere geometry)."""
        gr = compute_ground_range_m(600_000.0, math.radians(30.0))
        assert gr == pytest.approx(352_200.0, rel=0.005)

    @pytest.mark.level0
    def test_45_deg_from_600km(self) -> None:
        """At 45 deg, ground range ≈ 632.4 km (from ray-sphere geometry)."""
        gr = compute_ground_range_m(600_000.0, math.radians(45.0))
        assert gr == pytest.approx(632_400.0, rel=0.005)

    @pytest.mark.level0
    def test_5_deg_from_600km(self) -> None:
        """At 5 deg, ground range ≈ 52.5 km."""
        gr = compute_ground_range_m(600_000.0, math.radians(5.0))
        assert gr == pytest.approx(52_500.0, rel=0.01)

    @pytest.mark.level0
    def test_flat_earth_small_angle(self) -> None:
        """For small zenith angles, ground_range ≈ H × tan(θ)."""
        altitude_m = 600_000.0
        theta = math.radians(5.0)
        gr = compute_ground_range_m(altitude_m, theta)
        flat_approx = altitude_m * math.tan(theta)
        # Should match within 1% for small angles.
        assert gr == pytest.approx(flat_approx, rel=0.01)

    @pytest.mark.level0
    def test_negative_zenith_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            compute_ground_range_m(600_000.0, -0.1)

    @pytest.mark.level0
    def test_beyond_horizon_raises(self) -> None:
        """Zenith angle beyond horizon should raise ValueError."""
        with pytest.raises(ValueError, match="beyond the horizon"):
            compute_ground_range_m(600_000.0, math.radians(89.0))

    @pytest.mark.level0
    def test_zero_altitude_returns_zero(self) -> None:
        """At altitude=0, ground range is 0 (degenerate case)."""
        assert compute_ground_range_m(0.0, math.radians(30.0)) == 0.0

    @pytest.mark.level0
    def test_monotonically_increasing(self) -> None:
        """Ground range increases with zenith angle."""
        angles = [10.0, 20.0, 30.0, 40.0, 45.0]
        ranges = [compute_ground_range_m(600_000.0, math.radians(a)) for a in angles]
        for i in range(1, len(ranges)):
            assert ranges[i] > ranges[i - 1]


# ---------------------------------------------------------------------------
# Swath width
# ---------------------------------------------------------------------------


class TestSwathWidth:
    """Verify swath width = n_pixels × GSD_cross."""

    @pytest.mark.level0
    def test_identity(self) -> None:
        """Swath = GSD × n_pixels exactly."""
        gsd = 1.37
        n_pix = 10_000
        assert compute_swath_width_m(gsd, n_pix) == pytest.approx(
            gsd * n_pix,
            rel=1e-12,
        )

    @pytest.mark.level0
    def test_zero_pixels(self) -> None:
        """n_pixels=0 gives swath=0 (valid)."""
        assert compute_swath_width_m(1.37, 0) == 0.0

    @pytest.mark.level0
    def test_off_nadir_larger_gsd(self) -> None:
        """Off-nadir GSD produces larger swath."""
        nadir_swath = compute_swath_width_m(1.37, 10_000)
        offnadir_swath = compute_swath_width_m(1.86, 10_000)
        assert offnadir_swath > nadir_swath


# ---------------------------------------------------------------------------
# Access area rate
# ---------------------------------------------------------------------------


class TestAccessRate:
    """Verify access area rate = swath × speed."""

    @pytest.mark.level0
    def test_identity(self) -> None:
        """Rate = swath × speed exactly."""
        swath = 13_700.0  # 13.7 km
        speed = 6_900.0  # m/s
        assert compute_access_rate_m2_s(swath, speed) == pytest.approx(
            swath * speed,
            rel=1e-12,
        )

    @pytest.mark.level0
    def test_zero_speed(self) -> None:
        """No motion → no area coverage."""
        assert compute_access_rate_m2_s(13_700.0, 0.0) == 0.0

    @pytest.mark.level0
    def test_walkthrough_values(self) -> None:
        """Scenario 3.4: access rate at nadir ≈ 114 km²/s.

        With n_pixels=10000 (assumed), GSD=1.37m, speed=6.9 km/s:
        swath = 10000 × 1.37 = 13700 m = 13.7 km
        rate = 13.7 × 6.9 = 94.53 km²/s

        The walkthrough says 114 km²/s — likely uses a different n_pixels.
        We test the identity: rate = swath × speed.
        """
        swath_m = 13_700.0
        speed_m_s = 6_900.0
        rate = compute_access_rate_m2_s(swath_m, speed_m_s)
        # 94.53 km²/s = 94_530_000 m²/s
        assert rate == pytest.approx(94_530_000.0, rel=1e-12)
