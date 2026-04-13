"""Tests for readout.coadds — sum, average, median coadd modes."""

from __future__ import annotations

import math

import pytest

from radiant.readout.coadds import (
    CoaddMode,
    coadd_scale_fpn,
    coadd_scale_signal,
    coadd_scale_temporal_noise,
)


class TestCoaddSignal:
    def test_sum_scales_k(self) -> None:
        assert coadd_scale_signal(1000.0, 4, CoaddMode.SUM) == pytest.approx(
            4000.0,
            rel=1e-12,
        )

    def test_average_unchanged(self) -> None:
        assert coadd_scale_signal(1000.0, 4, CoaddMode.AVERAGE) == pytest.approx(
            1000.0,
            rel=1e-12,
        )

    def test_median_unchanged(self) -> None:
        assert coadd_scale_signal(1000.0, 4, CoaddMode.MEDIAN) == pytest.approx(
            1000.0,
            rel=1e-12,
        )

    def test_k1_identity(self) -> None:
        for mode in CoaddMode:
            assert coadd_scale_signal(1000.0, 1, mode) == pytest.approx(
                1000.0,
                rel=1e-12,
            )


class TestCoaddTemporalNoise:
    def test_sum_sqrt_k(self) -> None:
        assert coadd_scale_temporal_noise(10.0, 4, CoaddMode.SUM) == pytest.approx(
            20.0,
            rel=1e-12,
        )

    def test_average_div_sqrt_k(self) -> None:
        assert coadd_scale_temporal_noise(10.0, 4, CoaddMode.AVERAGE) == pytest.approx(
            5.0,
            rel=1e-12,
        )

    def test_median_pi_factor(self) -> None:
        """Median: × √(π/(2K))."""
        K = 9
        expected = 10.0 * math.sqrt(math.pi / (2.0 * K))
        assert coadd_scale_temporal_noise(10.0, K, CoaddMode.MEDIAN) == pytest.approx(
            expected,
            rel=1e-12,
        )

    def test_k1_all_modes_identity(self) -> None:
        for mode in CoaddMode:
            assert coadd_scale_temporal_noise(10.0, 1, mode) == pytest.approx(
                10.0,
                rel=1e-12,
            )

    def test_sum_snr_improvement(self) -> None:
        """SUM K=4: signal ×4, noise ×2 → SNR doubles."""
        s = 1000.0
        n = 10.0
        K = 4
        s_coadd = coadd_scale_signal(s, K, CoaddMode.SUM)
        n_coadd = coadd_scale_temporal_noise(n, K, CoaddMode.SUM)
        snr_ratio = (s_coadd / n_coadd) / (s / n)
        assert snr_ratio == pytest.approx(math.sqrt(K), rel=1e-10)


class TestCoaddFPN:
    def test_sum_scales_k(self) -> None:
        assert coadd_scale_fpn(10.0, 4, CoaddMode.SUM) == pytest.approx(
            40.0,
            rel=1e-12,
        )

    def test_average_unchanged(self) -> None:
        assert coadd_scale_fpn(10.0, 4, CoaddMode.AVERAGE) == pytest.approx(
            10.0,
            rel=1e-12,
        )

    def test_median_unchanged(self) -> None:
        assert coadd_scale_fpn(10.0, 4, CoaddMode.MEDIAN) == pytest.approx(
            10.0,
            rel=1e-12,
        )


class TestCoaddValidation:
    def test_invalid_k(self) -> None:
        with pytest.raises(ValueError, match="n_coadds"):
            coadd_scale_signal(1000.0, 0, CoaddMode.SUM)
