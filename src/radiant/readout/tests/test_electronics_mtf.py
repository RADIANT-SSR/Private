"""Tests for radiant.readout.electronics_mtf (Gap 32).

Category C truth anchors:
  1. Hand calculation: sigma = 5 µm at f = 25,000 cy/m →
     exp(-2π² · (5e-6)² · 25000²) = exp(-0.308425) = 0.734610.
  2. Gaussian Fourier pair: FT of the discretised kernel row must match
     the analytic MTF (independent numerical path).
  3. Half-power frequency: MTF = 0.5 at f = sqrt(ln 2 / 2) / (π·σ).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.readout.electronics_mtf import electronics_kernel_2d, electronics_mtf_1d

SIGMA = 5.0e-6  # m


class TestAnalyticMtf:
    @pytest.mark.level0
    def test_hand_anchor(self) -> None:
        freq = np.array([25_000.0])
        mtf = electronics_mtf_1d(freq, SIGMA)
        assert mtf[0] == pytest.approx(0.734610, rel=1e-5)

    @pytest.mark.level0
    def test_half_power_frequency(self) -> None:
        """Anchor 3: MTF = 0.5 at f = sqrt(ln2/2)/(pi*sigma)."""
        f_half = math.sqrt(math.log(2.0) / 2.0) / (math.pi * SIGMA)
        mtf = electronics_mtf_1d(np.array([f_half]), SIGMA)
        assert mtf[0] == pytest.approx(0.5, rel=1e-12)

    def test_zero_sigma_is_unity(self) -> None:
        freq = np.linspace(0.0, 1e5, 50)
        np.testing.assert_array_equal(electronics_mtf_1d(freq, 0.0), 1.0)

    def test_dc_is_unity(self) -> None:
        assert electronics_mtf_1d(np.array([0.0]), SIGMA)[0] == pytest.approx(1.0, abs=1e-15)

    def test_negative_sigma_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            electronics_mtf_1d(np.array([0.0]), -1e-6)


class TestKernel:
    def test_normalised(self) -> None:
        k = electronics_kernel_2d(31, 1.0e-6, SIGMA)
        assert k.sum() == pytest.approx(1.0, rel=1e-12)

    def test_blur_is_x_only(self) -> None:
        """[row, col] = [y, x]: all mass on the centre row (delta in y)."""
        k = electronics_kernel_2d(31, 1.0e-6, SIGMA)
        c = 31 // 2
        assert k[c, :].sum() == pytest.approx(1.0, rel=1e-12)
        assert np.count_nonzero(k[np.arange(31) != c, :]) == 0

    def test_zero_sigma_delta(self) -> None:
        k = electronics_kernel_2d(5, 1.0e-6, 0.0)
        assert k[2, 2] == 1.0
        assert k.sum() == 1.0

    @pytest.mark.level0
    def test_kernel_fourier_matches_analytic(self) -> None:
        """Anchor 2: |FT| of the kernel row equals the analytic MTF."""
        dx = 0.25e-6
        n = 257
        k = electronics_kernel_2d(n, dx, SIGMA)
        row = k[n // 2, :]
        mtf_num = np.abs(np.fft.rfft(np.fft.ifftshift(row)))
        freq = np.fft.rfftfreq(n, d=dx)
        mtf_ana = electronics_mtf_1d(freq, SIGMA)
        # Compare where the analytic MTF is meaningfully non-zero.
        sel = mtf_ana > 1e-3
        np.testing.assert_allclose(mtf_num[sel], mtf_ana[sel], rtol=2e-3)

    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            electronics_kernel_2d(4, 1e-6, SIGMA)
