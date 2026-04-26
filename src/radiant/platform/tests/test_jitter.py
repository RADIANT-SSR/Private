"""Tests for jitter MTF (Gaussian random pointing errors).

Validates:
- MTF = exp(-2π²σ²f²) against analytic formula
- Isotropic = anisotropic with σ_x = σ_y
- Zero jitter → unity MTF
- Kernel normalisation and σ measurement

See RADIANT_Spatial_Complete.md §7.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.platform.jitter import (
    jitter_kernel_2d,
    jitter_mtf_1d,
    jitter_mtf_2d,
    jitter_sigma_focal_m,
)

# ---------------------------------------------------------------------------
# jitter_sigma_focal_m
# ---------------------------------------------------------------------------


class TestJitterSigma:
    @pytest.mark.level0
    def test_basic(self) -> None:
        sigma = jitter_sigma_focal_m(1e-6, 1.5)
        assert sigma == pytest.approx(1.5e-6, rel=1e-12)

    @pytest.mark.level0
    def test_zero(self) -> None:
        assert jitter_sigma_focal_m(0.0, 1.5) == 0.0

    @pytest.mark.level0
    def test_negative_jitter_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            jitter_sigma_focal_m(-1e-6, 1.5)

    @pytest.mark.level0
    def test_zero_focal_length_raises(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m"):
            jitter_sigma_focal_m(1e-6, 0.0)


# ---------------------------------------------------------------------------
# jitter_mtf_1d — Truth Anchor: analytic Gaussian MTF
# ---------------------------------------------------------------------------


class TestJitterMTF1D:
    @pytest.mark.level0
    def test_dc_is_one(self) -> None:
        freq = np.array([0.0])
        mtf = jitter_mtf_1d(freq, sigma_m=5e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_analytic_match(self) -> None:
        """MTF matches exp(-2π²σ²f²) within machine precision."""
        sigma = 3e-6
        freq = np.linspace(0, 1e5, 500)
        mtf_computed = jitter_mtf_1d(freq, sigma)
        mtf_analytic = np.exp(-2.0 * math.pi**2 * sigma**2 * freq**2)
        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-12)

    @pytest.mark.level0
    def test_zero_sigma_is_unity(self) -> None:
        freq = np.linspace(0, 1e5, 100)
        mtf = jitter_mtf_1d(freq, 0.0)
        np.testing.assert_array_equal(mtf, np.ones_like(freq))

    @pytest.mark.level0
    def test_larger_sigma_lower_mtf(self) -> None:
        freq = np.array([5e4])
        mtf_small = jitter_mtf_1d(freq, 1e-6)
        mtf_large = jitter_mtf_1d(freq, 10e-6)
        assert mtf_large[0] < mtf_small[0]

    @pytest.mark.level0
    def test_negative_sigma_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            jitter_mtf_1d(np.array([0.0]), -1e-6)

    @pytest.mark.level0
    def test_1_over_e_halfwidth(self) -> None:
        """1/e point of Gaussian MTF at f = 1/(√2·π·σ).

        exp(-2π²σ²f²) = 1/e when 2π²σ²f² = 1 → f = 1/(√(2)πσ).
        """
        sigma = 5e-6
        f_1e = 1.0 / (math.sqrt(2) * math.pi * sigma)
        mtf = jitter_mtf_1d(np.array([f_1e]), sigma)
        assert mtf[0] == pytest.approx(1.0 / math.e, rel=1e-10)


# ---------------------------------------------------------------------------
# jitter_mtf_2d
# ---------------------------------------------------------------------------


class TestJitterMTF2D:
    @pytest.mark.level0
    def test_isotropic_equals_anisotropic(self) -> None:
        """Isotropic jitter = anisotropic with σ_x = σ_y."""
        sigma = 3e-6
        freq = np.linspace(0, 5e4, 20)
        FX, FY = np.meshgrid(freq, freq, indexing="xy")

        mtf_iso = jitter_mtf_2d(FX, FY, sigma, sigma)
        mtf_x = jitter_mtf_1d(FX, sigma)
        mtf_y = jitter_mtf_1d(FY, sigma)
        np.testing.assert_allclose(mtf_iso, mtf_x * mtf_y, rtol=1e-12)

    @pytest.mark.level0
    def test_anisotropic_sigma_x_zero(self) -> None:
        """σ_x = 0 → no blur in x, only in y."""
        freq = np.linspace(0, 5e4, 20)
        FX, FY = np.meshgrid(freq, freq, indexing="xy")

        mtf = jitter_mtf_2d(FX, FY, 0.0, 5e-6)
        # Along x-axis (fy=0): should be 1.0 everywhere.
        mtf_x_slice = mtf[0, :]
        np.testing.assert_allclose(mtf_x_slice, np.ones_like(mtf_x_slice), rtol=1e-12)


# ---------------------------------------------------------------------------
# jitter_kernel_2d
# ---------------------------------------------------------------------------


class TestJitterKernel:
    @pytest.mark.level0
    def test_unit_volume(self) -> None:
        kernel = jitter_kernel_2d(65, 1e-6, 3e-6, 3e-6)
        assert float(kernel.sum()) == pytest.approx(1.0, rel=1e-6)

    @pytest.mark.level0
    def test_non_negative(self) -> None:
        kernel = jitter_kernel_2d(33, 1e-6, 5e-6, 5e-6)
        assert np.all(kernel >= 0.0)

    @pytest.mark.level0
    def test_zero_sigma_is_delta(self) -> None:
        kernel = jitter_kernel_2d(11, 1e-6, 0.0, 0.0)
        c = 11 // 2
        assert kernel[c, c] == 1.0
        kernel[c, c] = 0.0
        assert float(kernel.sum()) == 0.0

    @pytest.mark.level0
    def test_peak_at_center(self) -> None:
        kernel = jitter_kernel_2d(33, 1e-6, 3e-6, 3e-6)
        peak = np.unravel_index(kernel.argmax(), kernel.shape)
        c = 33 // 2
        assert peak == (c, c)

    @pytest.mark.level0
    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            jitter_kernel_2d(32, 1e-6, 3e-6, 3e-6)

    @pytest.mark.level0
    def test_negative_sigma_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            jitter_kernel_2d(33, 1e-6, -1e-6, 3e-6)
