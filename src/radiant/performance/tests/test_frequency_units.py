"""Tests for radiant.performance.frequency_units (Gap 27).

Truth anchors (18 µm pixel, f = 1.2 m system):
  1. Detector Nyquist 27778 cy/m ↔ 0.5 cy/pixel (definition of Nyquist).
  2. 27778 cy/m ↔ 33.33 cy/mrad (IFOV = 15 µrad → Nyquist = 1/(2·0.015 mrad)).
  3. 27778 cy/m ↔ 27.78 cy/mm (SI prefix).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.frequency_units import (
    FrequencyUnitError,
    convert_spatial_frequency,
)

PITCH = 18e-6  # m
FOCAL = 1.2  # m
NYQ_M = 1.0 / (2.0 * PITCH)  # 27777.8 cy/m


class TestAnchors:
    @pytest.mark.level0
    def test_nyquist_is_half_cycle_per_pixel(self) -> None:
        out = convert_spatial_frequency(NYQ_M, "cy/m", "cy/pixel", pixel_pitch_m=PITCH)
        assert out == pytest.approx(0.5, rel=1e-12)

    @pytest.mark.level0
    def test_cy_mrad_via_ifov(self) -> None:
        """IFOV = 18µm/1.2m = 15 µrad → Nyquist = 1/(2·0.015 mrad) = 33.333 cy/mrad."""
        out = convert_spatial_frequency(NYQ_M, "cy/m", "cy/mrad", focal_length_m=FOCAL)
        assert out == pytest.approx(33.3333, rel=1e-4)

    @pytest.mark.level0
    def test_cy_mm(self) -> None:
        out = convert_spatial_frequency(NYQ_M, "cy/m", "cy/mm")
        assert out == pytest.approx(27.7778, rel=1e-4)


class TestRoundTrips:
    def test_all_pairs_round_trip(self) -> None:
        freq = np.linspace(0.0, 1e5, 11)
        units = ("cy/m", "cy/mm", "cy/mrad", "cy/pixel")
        for u1 in units:
            for u2 in units:
                fwd = convert_spatial_frequency(
                    freq, u1, u2, pixel_pitch_m=PITCH, focal_length_m=FOCAL
                )
                back = convert_spatial_frequency(
                    fwd, u2, u1, pixel_pitch_m=PITCH, focal_length_m=FOCAL
                )
                np.testing.assert_allclose(back, freq, rtol=1e-12)

    def test_identity(self) -> None:
        assert convert_spatial_frequency(123.0, "cy/m", "cy/m") == pytest.approx(
            123.0, rel=1e-15
        )


class TestFailureModes:
    def test_mrad_without_focal_length_raises(self) -> None:
        with pytest.raises(FrequencyUnitError, match="focal_length_m"):
            convert_spatial_frequency(1.0, "cy/m", "cy/mrad")

    def test_pixel_without_pitch_raises(self) -> None:
        with pytest.raises(FrequencyUnitError, match="pixel_pitch_m"):
            convert_spatial_frequency(1.0, "cy/pixel", "cy/m")

    def test_unknown_unit_raises(self) -> None:
        with pytest.raises(FrequencyUnitError, match="unknown unit"):
            convert_spatial_frequency(1.0, "cy/m", "cy/furlong")  # type: ignore[arg-type]

    def test_negative_focal_length_raises(self) -> None:
        with pytest.raises(FrequencyUnitError, match="positive focal_length_m"):
            convert_spatial_frequency(1.0, "cy/mrad", "cy/m", focal_length_m=-1.0)


class TestChainGridConsistency:
    """The utility must agree with the chain's own mrad grid convention."""

    @pytest.mark.level1
    def test_matches_optics_stage_convention(self) -> None:
        # OpticsStage: freq_cycles_per_mrad = freq_m * focal_length_m * 1e-3
        freq_m = np.array([27778.0])
        expected = freq_m * FOCAL * 1e-3
        out = convert_spatial_frequency(freq_m, "cy/m", "cy/mrad", focal_length_m=FOCAL)
        np.testing.assert_allclose(out, expected, rtol=1e-12)
