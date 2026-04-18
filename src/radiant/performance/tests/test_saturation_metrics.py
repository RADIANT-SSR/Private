"""Tests for saturation margin and dynamic range metrics."""

from __future__ import annotations

import math

import pytest

from radiant.performance.adc_margin import compute_adc_margin
from radiant.performance.dynamic_range import compute_dynamic_range
from radiant.performance.well_margin import compute_well_margin


class TestWellMargin:
    def test_half_full(self) -> None:
        """50000 e- in 100000 FWC → 20·log10(2) ≈ 6.02 dB."""
        result = compute_well_margin(50000.0, 100000.0)
        assert result.ok is True
        assert result.margin_dB == pytest.approx(20.0 * math.log10(2.0), rel=1e-10)
        assert not result.is_saturated

    def test_at_capacity(self) -> None:
        """Signal = FWC → 0 dB margin."""
        result = compute_well_margin(100000.0, 100000.0)
        assert result.margin_dB == pytest.approx(0.0, abs=1e-10)

    def test_saturated(self) -> None:
        """Signal > FWC → negative margin."""
        result = compute_well_margin(200000.0, 100000.0)
        assert result.ok is True
        assert result.is_saturated
        assert result.margin_dB < 0.0

    def test_zero_signal(self) -> None:
        result = compute_well_margin(0.0, 100000.0)
        assert result.failure_reason is not None

    def test_zero_fwc(self) -> None:
        result = compute_well_margin(10000.0, 0.0)
        assert not result.ok


class TestADCMargin:
    def test_half_scale(self) -> None:
        """32768 DN in 65535 max → ~6 dB margin."""
        result = compute_adc_margin(32768.0, 65535)
        assert result.ok is True
        expected = 20.0 * math.log10(65535.0 / 32768.0)
        assert result.margin_dB == pytest.approx(expected, rel=1e-10)

    def test_at_max(self) -> None:
        result = compute_adc_margin(65535.0, 65535)
        assert result.margin_dB == pytest.approx(0.0, abs=1e-10)

    def test_saturated(self) -> None:
        result = compute_adc_margin(70000.0, 65535)
        assert result.ok is True
        assert result.is_saturated

    def test_zero_signal(self) -> None:
        result = compute_adc_margin(0.0, 65535)
        assert result.failure_reason is not None


class TestDynamicRange:
    def test_basic(self) -> None:
        """FWC=100000, noise=5 → DR = 20·log10(20000) ≈ 86 dB."""
        result = compute_dynamic_range(100000.0, 5.0)
        assert result.ok is True
        expected = 20.0 * math.log10(100000.0 / 5.0)
        assert result.value_dB == pytest.approx(expected, rel=1e-10)

    def test_typical_scientific_cmos(self) -> None:
        """100 ke- FWC, 2 e- read → ~94 dB dynamic range.

        Truth anchor: typical sCMOS specs quote 88-96 dB.
        """
        result = compute_dynamic_range(100000.0, 2.0)
        assert 90.0 < result.value_dB < 100.0

    def test_zero_fwc(self) -> None:
        result = compute_dynamic_range(0.0, 5.0)
        assert not result.ok

    def test_zero_noise(self) -> None:
        result = compute_dynamic_range(100000.0, 0.0)
        assert not result.ok
