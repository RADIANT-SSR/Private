"""Tests for point-source detection range solver."""

from __future__ import annotations

import math

import pytest

from radiant.performance.detection_beer_lambert import detection_range_beer_lambert
from radiant.performance.detection_generic import detection_range_generic


class TestBeerLambertDetection:
    """Beer-Lambert atmosphere: S(R) = S_ref·(R_ref/R)²·exp(-α·ΔR)."""

    @pytest.mark.level0
    def test_no_atmosphere_inverse_square(self) -> None:
        """No extinction: detection range follows inverse-square law.

        S_ref = 10000 e- at R_ref = 1000 m, noise = 100 e-.
        SNR_ref = 100. Detection at SNR=5 → S = 500 → R² = 10000·1e6/500 = 2e7
        R = √(2e7) ≈ 4472 m.
        """
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        assert result.ok is True
        # R_detect = R_ref × √(SNR_ref / SNR_threshold)
        expected = 1000.0 * math.sqrt(10000.0 / (100.0 * 5.0))
        assert result.range_m == pytest.approx(expected, rel=1e-3)

    @pytest.mark.level1
    def test_with_extinction(self) -> None:
        """Extinction reduces detection range below inverse-square prediction."""
        no_atm = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        with_atm = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=1e-4,
            snr_threshold=5.0,
        )
        assert with_atm.ok is True
        assert with_atm.range_m < no_atm.range_m

    @pytest.mark.level0
    def test_convergence(self) -> None:
        """Result converges to within tolerance."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
            tol_m=0.1,
        )
        assert result.ok is True
        # SNR at result should be close to threshold
        assert result.snr_at_range == pytest.approx(5.0, rel=0.01)

    @pytest.mark.level1
    def test_undetectable_at_ref(self) -> None:
        """Signal too weak even at reference range."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=1.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        assert not result.ok
        assert "not detectable" in result.failure_reason

    @pytest.mark.level1
    def test_zero_signal_fails(self) -> None:
        result = detection_range_beer_lambert(
            signal_e_at_ref=0.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
        )
        assert not result.ok

    @pytest.mark.level1
    def test_zero_noise_fails(self) -> None:
        result = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=0.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
        )
        assert not result.ok

    @pytest.mark.level1
    def test_exceeds_max_range(self) -> None:
        """Very bright source detectable beyond max_range."""
        result = detection_range_beer_lambert(
            signal_e_at_ref=1e12,
            noise_e=1.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
            max_range_m=100000.0,
        )
        assert result.range_m == 100000.0
        assert result.failure_reason is not None
        assert "exceeds" in result.failure_reason

    @pytest.mark.level1
    def test_threshold_sensitivity(self) -> None:
        """Higher threshold → shorter detection range."""
        r5 = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=5.0,
        )
        r10 = detection_range_beer_lambert(
            signal_e_at_ref=10000.0,
            noise_e=100.0,
            ref_range_m=1000.0,
            extinction_coeff=0.0,
            snr_threshold=10.0,
        )
        assert r10.range_m < r5.range_m


class TestGenericDetection:
    """Generic detection range with user-supplied SNR(R) function."""

    @pytest.mark.level0
    def test_simple_inverse_square(self) -> None:
        """SNR(R) = 1000·(100/R)² for consistency with Beer-Lambert."""
        snr_ref = 1000.0
        r_ref = 100.0

        def snr_fn(r: float) -> float:
            return snr_ref * (r_ref / r) ** 2

        result = detection_range_generic(
            snr_at_range_fn=snr_fn,
            snr_threshold=5.0,
            r_min_m=100.0,
            r_max_m=1e6,
            tol_m=0.1,
        )
        assert result.ok is True
        expected = r_ref * math.sqrt(snr_ref / 5.0)
        assert result.range_m == pytest.approx(expected, rel=1e-3)

    @pytest.mark.level1
    def test_undetectable(self) -> None:
        def snr_fn(r: float) -> float:
            return 1.0  # Always below threshold

        result = detection_range_generic(snr_fn, snr_threshold=5.0, r_min_m=100.0)
        assert not result.ok
