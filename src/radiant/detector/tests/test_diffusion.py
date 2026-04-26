"""Tests for charge diffusion MTF and kernel.

Validates:
- MTF = exp(-2π²σ²f²) against analytic formula
- Kernel normalisation (sums to 1)
- Zero diffusion → delta kernel / unity MTF
- σ = L_d / √2

See RADIANT_Detector_Complete.md §3.3.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.detector.diffusion import (
    diffusion_kernel_2d,
    diffusion_mtf_1d,
    diffusion_sigma_m,
)

# ---------------------------------------------------------------------------
# diffusion_sigma_m
# ---------------------------------------------------------------------------


class TestDiffusionSigma:
    @pytest.mark.level0
    def test_basic(self) -> None:
        L_d = 5.0e-6  # 5 µm diffusion length
        assert diffusion_sigma_m(L_d) == pytest.approx(L_d / math.sqrt(2), rel=1e-12)

    @pytest.mark.level0
    def test_zero(self) -> None:
        assert diffusion_sigma_m(0.0) == 0.0

    @pytest.mark.level0
    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            diffusion_sigma_m(-1e-6)


# ---------------------------------------------------------------------------
# diffusion_mtf_1d — Truth Anchor: analytic Gaussian MTF
# ---------------------------------------------------------------------------


class TestDiffusionMTF:
    @pytest.mark.level0
    def test_dc_is_one(self) -> None:
        """MTF(0) = 1.0 for any diffusion length."""
        freq = np.array([0.0])
        mtf = diffusion_mtf_1d(freq, diffusion_length_m=5e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_analytic_match(self) -> None:
        """MTF matches exp(-2π²σ²f²) within 0.1%.

        Truth anchor: analytic Gaussian MTF formula.
        """
        L_d = 5.0e-6
        sigma = L_d / math.sqrt(2)
        freq = np.linspace(0, 1e5, 1000)

        mtf_computed = diffusion_mtf_1d(freq, L_d)
        mtf_analytic = np.exp(-2.0 * math.pi**2 * sigma**2 * freq**2)

        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-10)

    @pytest.mark.level0
    def test_zero_diffusion_is_unity(self) -> None:
        """Zero diffusion → MTF = 1 everywhere."""
        freq = np.linspace(0, 1e5, 100)
        mtf = diffusion_mtf_1d(freq, 0.0)
        np.testing.assert_array_equal(mtf, np.ones_like(freq))

    @pytest.mark.level0
    def test_larger_diffusion_lower_mtf(self) -> None:
        """Larger L_d → lower MTF at a given frequency."""
        freq = np.array([5e4])
        mtf_small = diffusion_mtf_1d(freq, 2e-6)
        mtf_large = diffusion_mtf_1d(freq, 10e-6)
        assert mtf_large[0] < mtf_small[0]

    @pytest.mark.level0
    def test_negative_diffusion_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            diffusion_mtf_1d(np.array([0.0]), -1e-6)


# ---------------------------------------------------------------------------
# diffusion_kernel_2d
# ---------------------------------------------------------------------------


class TestDiffusionKernel:
    @pytest.mark.level1
    def test_unit_volume(self) -> None:
        """Kernel sums to 1.0."""
        kernel = diffusion_kernel_2d(npix=65, sample_spacing_m=1e-6, diffusion_length_m=5e-6)
        assert float(kernel.sum()) == pytest.approx(1.0, rel=1e-6)

    @pytest.mark.level1
    def test_non_negative(self) -> None:
        kernel = diffusion_kernel_2d(npix=33, sample_spacing_m=1e-6, diffusion_length_m=3e-6)
        assert np.all(kernel >= 0.0)

    @pytest.mark.level1
    def test_peak_at_center(self) -> None:
        kernel = diffusion_kernel_2d(npix=33, sample_spacing_m=1e-6, diffusion_length_m=3e-6)
        peak = np.unravel_index(kernel.argmax(), kernel.shape)
        c = 33 // 2
        assert peak == (c, c)

    @pytest.mark.level1
    def test_zero_diffusion_is_delta(self) -> None:
        """Zero diffusion → delta function."""
        kernel = diffusion_kernel_2d(npix=11, sample_spacing_m=1e-6, diffusion_length_m=0.0)
        c = 11 // 2
        assert kernel[c, c] == 1.0
        kernel[c, c] = 0.0
        assert float(kernel.sum()) == 0.0

    @pytest.mark.level1
    def test_symmetric(self) -> None:
        kernel = diffusion_kernel_2d(npix=33, sample_spacing_m=1e-6, diffusion_length_m=5e-6)
        c = 33 // 2
        np.testing.assert_allclose(
            kernel[c, c:], kernel[c, c::-1][: len(kernel[c, c:])], rtol=1e-10
        )

    @pytest.mark.level1
    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            diffusion_kernel_2d(npix=32, sample_spacing_m=1e-6, diffusion_length_m=5e-6)

    @pytest.mark.level1
    def test_zero_spacing_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_spacing_m must be positive"):
            diffusion_kernel_2d(npix=33, sample_spacing_m=0.0, diffusion_length_m=5e-6)

    @pytest.mark.level1
    def test_negative_diffusion_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            diffusion_kernel_2d(npix=33, sample_spacing_m=1e-6, diffusion_length_m=-1e-6)


# ---------------------------------------------------------------------------
# Cross-model: FFT of kernel matches analytic MTF
# ---------------------------------------------------------------------------


class TestDiffusionCrossModel:
    @pytest.mark.level1
    def test_kernel_fft_matches_analytic_mtf(self) -> None:
        """Convolution in real space ≡ multiplication in Fourier space.

        FFT of the Gaussian kernel should match the analytic MTF formula.
        """
        L_d = 5.0e-6
        npix = 129
        dx = 0.5e-6
        kernel = diffusion_kernel_2d(npix, dx, L_d)

        # FFT of kernel → OTF (normalised).
        otf = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(kernel)))
        mtf_from_fft = np.abs(otf)
        # Normalise DC to 1.
        mtf_from_fft /= mtf_from_fft.max()

        # 1-D slice through center.
        c = npix // 2
        mtf_slice = mtf_from_fft[c, c:]

        # Frequency grid.
        freq = np.arange(len(mtf_slice)) / (npix * dx)

        # Analytic MTF.
        mtf_analytic = diffusion_mtf_1d(freq, L_d)

        # Compare over the range where MTF > 0.01 (avoid noise floor).
        mask = mtf_analytic > 0.01
        np.testing.assert_allclose(mtf_slice[mask], mtf_analytic[mask], rtol=0.005)
