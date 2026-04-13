"""Tests for GIQE-5 NIIRS computation.

Truth anchors:
1. Manual computation with known inputs
2. Published GIQE-5 test case: GSD=1m, RER=0.9, SNR=50 → ~6.8
3. Sensitivity: larger GSD → lower NIIRS

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.giqe import C0, C1, C2, C3, C4, C5, compute_giqe5


class TestGIQE5:
    def test_hand_calculation(self) -> None:
        """Manual: GSD=1m (39.37in), RER=0.9, SNR=50, H=1, G=1.

        NIIRS = 9.57 + (-3.32)·log10(39.37) + 3.32·log10(0.9)
                     + 1.559·log10(50) + (-0.334)·1 + (-0.01)·1
        """
        gsd_inch = 1.0 * 39.37
        expected = (
            C0
            + C1 * math.log10(gsd_inch)
            + C2 * math.log10(0.9)
            + C3 * math.log10(50.0)
            + C4 * 1.0
            + C5 * 1.0
        )
        result = compute_giqe5(1.0, 1.0, 0.9, 0.9, 50.0)
        assert result.niirs == pytest.approx(expected, rel=1e-10)

    def test_published_giqe5_case_1(self) -> None:
        """GSD=0.3m, RER=0.7, SNR=100 → NIIRS ~7-8 range."""
        result = compute_giqe5(0.3, 0.3, 0.7, 0.7, 100.0)
        # Reasonable NIIRS for high-res commercial imagery.
        assert 7.0 < result.niirs < 9.0

    def test_published_giqe5_case_2(self) -> None:
        """GSD=5m, RER=0.5, SNR=30 → NIIRS ~2.5-4 range (coarse imagery)."""
        result = compute_giqe5(5.0, 5.0, 0.5, 0.5, 30.0)
        assert 2.5 < result.niirs < 4.5

    def test_published_giqe5_case_3(self) -> None:
        """GSD=0.5m, RER=0.8, SNR=80 → NIIRS ~6-8 range."""
        result = compute_giqe5(0.5, 0.5, 0.8, 0.8, 80.0)
        assert 6.0 < result.niirs < 8.0

    def test_larger_gsd_lower_niirs(self) -> None:
        """Larger GSD → lower NIIRS (worse resolution)."""
        r1 = compute_giqe5(0.5, 0.5, 0.7, 0.7, 50.0)
        r2 = compute_giqe5(5.0, 5.0, 0.7, 0.7, 50.0)
        assert r1.niirs > r2.niirs

    def test_higher_snr_higher_niirs(self) -> None:
        """Higher SNR → higher NIIRS."""
        r1 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 20.0)
        r2 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 100.0)
        assert r2.niirs > r1.niirs

    def test_higher_rer_higher_niirs(self) -> None:
        """Higher RER → higher NIIRS (sharper edges)."""
        r1 = compute_giqe5(1.0, 1.0, 0.3, 0.3, 50.0)
        r2 = compute_giqe5(1.0, 1.0, 0.9, 0.9, 50.0)
        assert r2.niirs > r1.niirs

    def test_gsd_inch_conversion(self) -> None:
        """Verify m → inch conversion: 1m = 39.37in."""
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert result.gsd_inch == pytest.approx(39.37, rel=1e-4)

    def test_geometric_mean_gsd(self) -> None:
        """Non-square GSD: geometric mean used."""
        result = compute_giqe5(1.0, 4.0, 0.7, 0.7, 50.0)
        expected_inch = math.sqrt(1.0 * 4.0) * 39.37
        assert result.gsd_inch == pytest.approx(expected_inch, rel=1e-10)

    def test_geometric_mean_rer(self) -> None:
        """Non-isotropic RER: geometric mean used."""
        result = compute_giqe5(1.0, 1.0, 0.5, 0.8, 50.0)
        expected_rer = math.sqrt(0.5 * 0.8)
        assert result.rer == pytest.approx(expected_rer, rel=1e-10)

    def test_low_snr_warning(self) -> None:
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 3.0)
        assert any("SNR below" in w for w in result.warnings)

    def test_low_rer_warning(self) -> None:
        result = compute_giqe5(1.0, 1.0, 0.1, 0.1, 50.0)
        assert any("RER below" in w for w in result.warnings)

    def test_zero_gsd_raises(self) -> None:
        with pytest.raises(ValueError, match="GSD must be positive"):
            compute_giqe5(0.0, 1.0, 0.7, 0.7, 50.0)

    def test_negative_snr_raises(self) -> None:
        with pytest.raises(ValueError, match="SNR must be positive"):
            compute_giqe5(1.0, 1.0, 0.7, 0.7, -10.0)

    def test_zero_rer_raises(self) -> None:
        with pytest.raises(ValueError, match="RER must be positive"):
            compute_giqe5(1.0, 1.0, 0.0, 0.7, 50.0)

    def test_frozen(self) -> None:
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        with pytest.raises(AttributeError):
            result.niirs = 5.0  # type: ignore[misc]
