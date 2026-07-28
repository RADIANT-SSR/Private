"""Level 0 tests for the target-plane sample distance (GF-13).

The key equation is ``d = pitch × R / f`` — pixel angular subtense projected at
the slant range, with **no** ground-plane ``cos`` projection. Truth anchors are
hand calculations and the GSD identity at nadir.
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.errors import PerformanceValidationError
from radiant.performance.gsd import compute_gsd_from_geometry
from radiant.performance.target_plane_sample_distance import (
    target_plane_sample_distance,
)


class TestKeyEquation:
    @pytest.mark.level0
    def test_hand_calculation_round_numbers(self) -> None:
        """Anchor: 20 µm pitch, f = 2 m, R = 500 km ⇒ IFOV = 10 µrad ⇒ 5.0 m.

        IFOV = 20e-6 / 2.0 = 1.0e-5 rad; d = 1.0e-5 × 5.0e5 = 5.0 m exactly.
        """
        result = target_plane_sample_distance(20e-6, 20e-6, 2.0, 5.0e5)
        assert result.x_m == pytest.approx(5.0, rel=1e-12)
        assert result.y_m == pytest.approx(5.0, rel=1e-12)
        assert result.geometric_mean_m == pytest.approx(5.0, rel=1e-12)

    @pytest.mark.level0
    def test_rectangular_pixel_geometric_mean(self) -> None:
        """Anchor: 15 × 30 µm at f = 0.5 m, R = 100 km ⇒ 3 m × 6 m, mean √18."""
        result = target_plane_sample_distance(15e-6, 30e-6, 0.5, 1.0e5)
        assert result.x_m == pytest.approx(3.0, rel=1e-12)
        assert result.y_m == pytest.approx(6.0, rel=1e-12)
        assert result.geometric_mean_m == pytest.approx(math.sqrt(18.0), rel=1e-12)

    @pytest.mark.level0
    def test_equals_slant_range_times_ifov(self) -> None:
        """Anchor: the definition itself, evaluated independently."""
        pitch, focal, slant = 8.5e-6, 1.37, 2.34e6
        ifov = pitch / focal
        result = target_plane_sample_distance(pitch, pitch, focal, slant)
        assert result.x_m == pytest.approx(slant * ifov, rel=1e-14)

    @pytest.mark.level0
    def test_linear_in_range(self) -> None:
        a = target_plane_sample_distance(10e-6, 10e-6, 1.0, 1.0e5)
        b = target_plane_sample_distance(10e-6, 10e-6, 1.0, 3.0e5)
        assert b.x_m == pytest.approx(3.0 * a.x_m, rel=1e-14)


class TestRelationToGsd:
    @pytest.mark.level0
    def test_matches_gsd_at_zero_incidence(self) -> None:
        """At incidence = 0 the ground plane is normal to the LOS: identical."""
        args = (13e-6, 13e-6, 0.8, 7.5e5)
        tp = target_plane_sample_distance(*args)
        gsd = compute_gsd_from_geometry(13e-6, 13e-6, 0.8, 7.5e5, 0.0)
        assert tp.x_m == pytest.approx(gsd.cross_track_m, rel=1e-14)
        assert tp.y_m == pytest.approx(gsd.along_track_m, rel=1e-14)

    @pytest.mark.level0
    def test_no_cos_projection_off_axis(self) -> None:
        """Off-axis, GSD's along-track axis stretches by 1/cos; this does not."""
        inc = 0.6  # rad
        tp = target_plane_sample_distance(13e-6, 13e-6, 0.8, 7.5e5)
        gsd = compute_gsd_from_geometry(13e-6, 13e-6, 0.8, 7.5e5, inc)
        assert gsd.along_track_m == pytest.approx(tp.y_m / math.cos(inc), rel=1e-12)
        assert gsd.cross_track_m == pytest.approx(tp.x_m, rel=1e-14)

    @pytest.mark.level0
    def test_defined_where_gsd_is_not(self) -> None:
        """An up-looking incidence (> π/2) breaks GSD; the target plane is fine."""
        with pytest.raises(PerformanceValidationError):
            compute_gsd_from_geometry(13e-6, 13e-6, 0.8, 7.5e5, 2.0)
        assert target_plane_sample_distance(13e-6, 13e-6, 0.8, 7.5e5).x_m > 0.0


class TestFailureModes:
    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    @pytest.mark.parametrize("index", [0, 1, 2, 3])
    def test_non_positive_or_non_finite_inputs_raise(self, bad: float, index: int) -> None:
        args = [10e-6, 10e-6, 1.0, 1.0e5]
        args[index] = bad
        with pytest.raises(PerformanceValidationError):
            target_plane_sample_distance(*args)

    @pytest.mark.level0
    def test_very_short_range_stays_finite_and_positive(self) -> None:
        result = target_plane_sample_distance(10e-6, 10e-6, 1.0, 1e-3)
        assert math.isfinite(result.x_m) and result.x_m > 0.0

    @pytest.mark.level0
    def test_geo_range_does_not_overflow(self) -> None:
        result = target_plane_sample_distance(10e-6, 10e-6, 1.0, 3.6e7)
        assert result.x_m == pytest.approx(360.0, rel=1e-12)
