"""Tests for radiant.optics.scatter (Gap 31).

Category C truth anchors:
  1. Hand calculation: σ_s = 50 nm at λ = 4.25 µm →
     (4π·0.05/4.25)² = 0.0218567; TIS = 1 − exp(−0.0218567) = 0.0216196.
  2. Small-σ limit (Bennett & Porteus): TIS ≈ (4πσ/λ)² to < 2% when
     TIS < 0.02.
  3. Fourier pair: |FT{kernel}| must equal the analytic MTF —
     independent numerical path through the same model.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.scatter import (
    scatter_kernel_2d,
    scatter_mtf_1d,
    total_integrated_scatter,
)

SIGMA_S = 50e-9  # m
LAM = 4.25e-6  # m
SIGMA_HALO = 100e-6  # m


class TestTis:
    @pytest.mark.level0
    def test_hand_anchor(self) -> None:
        tis = total_integrated_scatter(SIGMA_S, LAM)
        assert tis == pytest.approx(0.0216196, rel=1e-5)

    @pytest.mark.level0
    def test_small_sigma_limit(self) -> None:
        """Anchor 2: TIS → (4πσ/λ)² as σ → 0."""
        sigma = 5e-9
        approx = (4.0 * math.pi * sigma / LAM) ** 2
        tis = total_integrated_scatter(sigma, LAM)
        assert tis == pytest.approx(approx, rel=2e-2)

    def test_zero_roughness_zero_tis(self) -> None:
        assert total_integrated_scatter(0.0, LAM) == 0.0

    def test_validity_warning_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """σ_s comparable to λ: warn, don't fail (Rule 17 — no silent clip)."""
        with caplog.at_level("WARNING"):
            tis = total_integrated_scatter(300e-9, 0.5e-6)
        assert tis > 0.3
        assert any("validity" in r.message for r in caplog.records)

    def test_negative_roughness_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            total_integrated_scatter(-1e-9, LAM)

    def test_zero_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            total_integrated_scatter(SIGMA_S, 0.0)


class TestKernelAndMtf:
    def test_kernel_unit_volume(self) -> None:
        """Energy conservation: scatter redistributes, never absorbs."""
        k = scatter_kernel_2d(129, 4e-6, SIGMA_HALO, 0.02)
        assert k.sum() == pytest.approx(1.0, rel=1e-12)

    def test_zero_tis_is_delta(self) -> None:
        k = scatter_kernel_2d(5, 4e-6, SIGMA_HALO, 0.0)
        assert k[2, 2] == 1.0

    def test_specular_core_fraction(self) -> None:
        """Centre pixel keeps ≈ (1 − TIS) plus the halo's centre sample."""
        tis = 0.02
        k = scatter_kernel_2d(257, 4e-6, SIGMA_HALO, tis)
        c = 257 // 2
        assert k[c, c] > (1.0 - tis) * 0.999
        assert k[c, c] < 1.0

    @pytest.mark.level0
    def test_fourier_pair(self) -> None:
        """Anchor 3: |FT{kernel row-sum}| matches the analytic MTF."""
        tis = 0.05
        dx = 2e-6
        n = 513
        k = scatter_kernel_2d(n, dx, SIGMA_HALO, tis)
        proj = k.sum(axis=0)  # 1-D projection → 1-D MTF along x
        mtf_num = np.abs(np.fft.rfft(np.fft.ifftshift(proj)))
        freq = np.fft.rfftfreq(n, d=dx)
        mtf_ana = scatter_mtf_1d(freq, SIGMA_HALO, tis)
        np.testing.assert_allclose(mtf_num, mtf_ana, atol=2e-3)

    def test_mtf_dc_unity_and_floor(self) -> None:
        tis = 0.1
        freq = np.array([0.0, 1e9])
        mtf = scatter_mtf_1d(freq, SIGMA_HALO, tis)
        assert mtf[0] == pytest.approx(1.0, abs=1e-15)
        assert mtf[1] == pytest.approx(1.0 - tis, rel=1e-12)

    def test_bad_tis_raises(self) -> None:
        with pytest.raises(ValueError, match="tis"):
            scatter_mtf_1d(np.array([0.0]), SIGMA_HALO, 1.5)
