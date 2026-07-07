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
    @pytest.mark.level0
    def test_hand_calculation(self) -> None:
        """Manual: GSD=1m, RER=0.9, SNR=50, H=1, G=1.

        NIIRS = 9.57 + (-3.32)·log10(GSD_in) + 3.32·log10(0.9)
                     + 1.559·log10(50) + (-0.334)·1 + (-0.01)·1
        """
        gsd_inch = 1.0 / 0.0254  # exact m → inches
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

    @pytest.mark.level0
    def test_published_giqe5_case_1(self) -> None:
        """GSD=0.3m, RER=0.7, SNR=100 → NIIRS ~7-8 range."""
        result = compute_giqe5(0.3, 0.3, 0.7, 0.7, 100.0)
        # Reasonable NIIRS for high-res commercial imagery.
        assert 7.0 < result.niirs < 9.0

    @pytest.mark.level0
    def test_published_giqe5_case_2(self) -> None:
        """GSD=5m, RER=0.5, SNR=30 → NIIRS ~2.5-4 range (coarse imagery)."""
        result = compute_giqe5(5.0, 5.0, 0.5, 0.5, 30.0)
        assert 2.5 < result.niirs < 4.5

    @pytest.mark.level0
    def test_published_giqe5_case_3(self) -> None:
        """GSD=0.5m, RER=0.8, SNR=80 → NIIRS ~6-8 range."""
        result = compute_giqe5(0.5, 0.5, 0.8, 0.8, 80.0)
        assert 6.0 < result.niirs < 8.0

    @pytest.mark.level0
    def test_larger_gsd_lower_niirs(self) -> None:
        """Larger GSD → lower NIIRS (worse resolution)."""
        r1 = compute_giqe5(0.5, 0.5, 0.7, 0.7, 50.0)
        r2 = compute_giqe5(5.0, 5.0, 0.7, 0.7, 50.0)
        assert r1.niirs > r2.niirs

    @pytest.mark.level0
    def test_higher_snr_higher_niirs(self) -> None:
        """Higher SNR → higher NIIRS."""
        r1 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 20.0)
        r2 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 100.0)
        assert r2.niirs > r1.niirs

    @pytest.mark.level0
    def test_higher_rer_higher_niirs(self) -> None:
        """Higher RER → higher NIIRS (sharper edges)."""
        r1 = compute_giqe5(1.0, 1.0, 0.3, 0.3, 50.0)
        r2 = compute_giqe5(1.0, 1.0, 0.9, 0.9, 50.0)
        assert r2.niirs > r1.niirs

    @pytest.mark.level0
    def test_gsd_inch_conversion(self) -> None:
        """Verify m → inch conversion: 1m = 39.37in."""
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert result.gsd_inch == pytest.approx(1.0 / 0.0254, rel=1e-10)

    @pytest.mark.level0
    def test_geometric_mean_gsd(self) -> None:
        """Non-square GSD: geometric mean used."""
        result = compute_giqe5(1.0, 4.0, 0.7, 0.7, 50.0)
        expected_inch = math.sqrt(1.0 * 4.0) / 0.0254
        assert result.gsd_inch == pytest.approx(expected_inch, rel=1e-10)

    @pytest.mark.level0
    def test_geometric_mean_rer(self) -> None:
        """Non-isotropic RER: geometric mean used."""
        result = compute_giqe5(1.0, 1.0, 0.5, 0.8, 50.0)
        expected_rer = math.sqrt(0.5 * 0.8)
        assert result.rer == pytest.approx(expected_rer, rel=1e-10)

    @pytest.mark.level0
    def test_low_snr_warning(self) -> None:
        # Below the published GIQE-5 fit range [2, 130] (Harrington 2015).
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 1.5)
        assert any("SNR" in w and "calibration range" in w for w in result.warnings)

    @pytest.mark.level0
    def test_low_rer_warning(self) -> None:
        result = compute_giqe5(1.0, 1.0, 0.1, 0.1, 50.0)
        assert any("RER" in w and "calibration range" in w for w in result.warnings)

    @pytest.mark.level0
    def test_zero_gsd_raises(self) -> None:
        with pytest.raises(ValueError, match="GSD must be positive"):
            compute_giqe5(0.0, 1.0, 0.7, 0.7, 50.0)

    @pytest.mark.level0
    def test_negative_snr_raises(self) -> None:
        with pytest.raises(ValueError, match="SNR must be positive"):
            compute_giqe5(1.0, 1.0, 0.7, 0.7, -10.0)

    @pytest.mark.level0
    def test_zero_rer_raises(self) -> None:
        with pytest.raises(ValueError, match="RER must be positive"):
            compute_giqe5(1.0, 1.0, 0.0, 0.7, 50.0)

    @pytest.mark.level0
    def test_frozen(self) -> None:
        result = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        with pytest.raises(AttributeError):
            result.niirs = 5.0  # type: ignore[misc]


class TestCalibrationRange:
    """Gap 22: GIQE-5 results outside the published fit range are flagged.

    Fit ranges per GIQE-5 (Harrington et al., 2015): GSD 3-80 cm
    (1.18-31.5 inch), RER 0.2-0.95, SNR 2-130.
    """

    def _nominal(self, **overrides):
        kwargs = dict(
            gsd_m_along=0.3,
            gsd_m_cross=0.3,
            rer_along=0.5,
            rer_cross=0.5,
            snr=50.0,
        )
        kwargs.update(overrides)
        return compute_giqe5(**kwargs)

    @pytest.mark.level0
    def test_in_range_not_extrapolated(self) -> None:
        result = self._nominal()
        assert result.extrapolated is False
        assert result.warnings == ()

    def test_rer_below_range(self) -> None:
        result = self._nominal(rer_along=0.1, rer_cross=0.1)
        assert result.extrapolated is True
        assert any("RER" in w for w in result.warnings)

    def test_rer_above_range(self) -> None:
        result = self._nominal(rer_along=0.98, rer_cross=0.98)
        assert result.extrapolated is True
        assert any("RER" in w for w in result.warnings)

    def test_snr_below_range(self) -> None:
        result = self._nominal(snr=1.5)
        assert result.extrapolated is True
        assert any("SNR" in w for w in result.warnings)

    def test_snr_above_range(self) -> None:
        result = self._nominal(snr=500.0)
        assert result.extrapolated is True
        assert any("SNR" in w for w in result.warnings)

    def test_gsd_below_range(self) -> None:
        result = self._nominal(gsd_m_along=0.01, gsd_m_cross=0.01)
        assert result.extrapolated is True
        assert any("GSD" in w for w in result.warnings)

    def test_gsd_above_range(self) -> None:
        result = self._nominal(gsd_m_along=5.0, gsd_m_cross=5.0)
        assert result.extrapolated is True
        assert any("GSD" in w for w in result.warnings)

    def test_niirs_still_computed_when_extrapolated(self) -> None:
        """Extrapolation reduces confidence; it does not suppress the value."""
        result = self._nominal(rer_along=0.1, rer_cross=0.1)
        assert math.isfinite(result.niirs)
