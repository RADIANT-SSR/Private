"""Tests for GSD, IFOV, slant range geometry helpers.

Truth anchors:
- GSD = pitch × altitude / focal_length (trivial)
- IFOV = pitch / focal_length (trivial)
- GSD = IFOV × altitude (consistency check)

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

import math

import pytest

from radiant.platform.geometry import (
    gsd_at_angle_m,
    gsd_m,
    ifov_rad,
    slant_range_m,
)


# ---------------------------------------------------------------------------
# GSD
# ---------------------------------------------------------------------------


class TestGSD:
    def test_basic(self) -> None:
        """GSD for typical LEO: pitch=15µm, alt=700km, f=1.5m → 7.0m."""
        g = gsd_m(15e-6, 700e3, 1.5)
        expected = 15e-6 * 700e3 / 1.5
        assert g == pytest.approx(expected, rel=1e-12)
        assert g == pytest.approx(7.0, rel=1e-10)

    def test_known_value(self) -> None:
        """GSD for pitch=10µm, alt=500km, f=2.0m → 2.5m."""
        g = gsd_m(10e-6, 500e3, 2.0)
        assert g == pytest.approx(2.5, rel=1e-10)

    def test_zero_focal_length_raises(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m"):
            gsd_m(15e-6, 700e3, 0.0)

    def test_negative_pitch_raises(self) -> None:
        with pytest.raises(ValueError, match="pixel_pitch_m"):
            gsd_m(-15e-6, 700e3, 1.5)

    def test_zero_altitude_raises(self) -> None:
        with pytest.raises(ValueError, match="altitude_m"):
            gsd_m(15e-6, 0.0, 1.5)


# ---------------------------------------------------------------------------
# IFOV
# ---------------------------------------------------------------------------


class TestIFOV:
    def test_basic(self) -> None:
        """IFOV = 15µm / 1.5m = 10µrad."""
        ifov = ifov_rad(15e-6, 1.5)
        assert ifov == pytest.approx(10e-6, rel=1e-12)

    def test_zero_focal_length_raises(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m"):
            ifov_rad(15e-6, 0.0)


# ---------------------------------------------------------------------------
# Cross-model: GSD = IFOV × altitude
# ---------------------------------------------------------------------------


class TestGSDIFOVConsistency:
    def test_gsd_equals_ifov_times_altitude(self) -> None:
        """GSD and IFOV are redundant representations of the same quantity."""
        pitch = 15e-6
        alt = 700e3
        f = 1.5
        g = gsd_m(pitch, alt, f)
        ifov = ifov_rad(pitch, f)
        assert g == pytest.approx(ifov * alt, rel=1e-12)


# ---------------------------------------------------------------------------
# Slant range
# ---------------------------------------------------------------------------


class TestSlantRange:
    def test_nadir(self) -> None:
        """Nadir: slant range = altitude."""
        sr = slant_range_m(700e3)
        assert sr == 700e3

    def test_off_nadir(self) -> None:
        """30° off-nadir: SR = alt / cos(30°)."""
        alt = 700e3
        angle = math.radians(30)
        sr = slant_range_m(alt, angle)
        assert sr == pytest.approx(alt / math.cos(angle), rel=1e-12)

    def test_large_angle_raises(self) -> None:
        with pytest.raises(ValueError, match="look_angle_rad"):
            slant_range_m(700e3, math.pi / 2)


# ---------------------------------------------------------------------------
# GSD at angle
# ---------------------------------------------------------------------------


class TestGSDAtAngle:
    def test_nadir_equals_basic(self) -> None:
        g1 = gsd_m(15e-6, 700e3, 1.5)
        g2 = gsd_at_angle_m(15e-6, 700e3, 1.5, 0.0)
        assert g1 == pytest.approx(g2, rel=1e-12)

    def test_off_nadir_larger(self) -> None:
        """Off-nadir GSD > nadir GSD."""
        g_nadir = gsd_at_angle_m(15e-6, 700e3, 1.5, 0.0)
        g_off = gsd_at_angle_m(15e-6, 700e3, 1.5, math.radians(30))
        assert g_off > g_nadir
