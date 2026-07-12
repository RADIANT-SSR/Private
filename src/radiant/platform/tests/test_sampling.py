"""Tests for pixel aperture MTF (rectangular sampling function).

Validates:
- MTF = |sinc(π·f·p·FF)| against analytic formula
- Kernel normalisation (sums to 1)
- Zero at Nyquist for FF=1 (sinc(π) = 0)
- Fill factor < 1 shifts the first zero

See RADIANT_Spatial_Complete.md §6 (step 1) and
RADIANT_Detector_Complete.md §3.3.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.platform.sampling import (
    pixel_aperture_kernel_1d,
    pixel_aperture_mtf_1d,
    pixel_aperture_mtf_2d,
)

# ---------------------------------------------------------------------------
# pixel_aperture_mtf_1d — Truth Anchor: analytic sinc
# ---------------------------------------------------------------------------


class TestPixelApertureMTF1D:
    @pytest.mark.level0
    def test_dc_is_one(self) -> None:
        freq = np.array([0.0])
        mtf = pixel_aperture_mtf_1d(freq, pixel_pitch_m=15e-6)
        assert mtf[0] == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_analytic_sinc(self) -> None:
        """MTF matches |sinc(π·f·p)| within 0.1%.

        Truth anchor: analytic sinc(π·f·p) for rectangular aperture.
        """
        pitch = 15e-6
        freq = np.linspace(0, 1.0 / pitch, 500)  # up to Nyquist at 1/p

        mtf_computed = pixel_aperture_mtf_1d(freq, pitch)
        # np.sinc(x) = sin(πx)/(πx), so sinc(f*p) = sin(π·f·p)/(π·f·p)
        mtf_analytic = np.abs(np.sinc(freq * pitch))

        np.testing.assert_allclose(mtf_computed, mtf_analytic, rtol=1e-10)

    @pytest.mark.level0
    def test_zero_at_nyquist(self) -> None:
        """MTF(1/p) = sinc(1) = 0 for FF=1."""
        pitch = 15e-6
        f_nyquist = 1.0 / pitch
        freq = np.array([f_nyquist])
        mtf = pixel_aperture_mtf_1d(freq, pitch)
        assert mtf[0] == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.level0
    def test_half_nyquist(self) -> None:
        """MTF(1/(2p)) = sinc(0.5) = 2/π ≈ 0.6366."""
        pitch = 15e-6
        freq = np.array([1.0 / (2.0 * pitch)])
        mtf = pixel_aperture_mtf_1d(freq, pitch)
        expected = 2.0 / math.pi
        assert mtf[0] == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_fill_factor_shifts_zero(self) -> None:
        """FF < 1 moves the first zero to 1/(p·√FF) — areal fill factor,
        square photosite of linear width p·√FF (CU-074)."""
        pitch = 15e-6
        ff = 0.5
        f_zero = 1.0 / (pitch * math.sqrt(ff))
        freq = np.array([f_zero])
        mtf = pixel_aperture_mtf_1d(freq, pitch, fill_factor=ff)
        assert mtf[0] == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.level0
    def test_fill_factor_increases_mtf_at_nyquist(self) -> None:
        """Smaller FF → less blurring → higher MTF at Nyquist."""
        pitch = 15e-6
        f_ny = 1.0 / (2.0 * pitch)
        freq = np.array([f_ny])
        mtf_full = pixel_aperture_mtf_1d(freq, pitch, fill_factor=1.0)
        mtf_half = pixel_aperture_mtf_1d(freq, pitch, fill_factor=0.5)
        assert mtf_half[0] > mtf_full[0]

    @pytest.mark.level0
    def test_negative_pitch_raises(self) -> None:
        with pytest.raises(ValueError, match="pixel_pitch_m must be positive"):
            pixel_aperture_mtf_1d(np.array([0.0]), -15e-6)

    @pytest.mark.level0
    def test_zero_fill_factor_raises(self) -> None:
        with pytest.raises(ValueError, match="fill_factor must be in"):
            pixel_aperture_mtf_1d(np.array([0.0]), 15e-6, fill_factor=0.0)

    @pytest.mark.level0
    def test_fill_factor_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="fill_factor must be in"):
            pixel_aperture_mtf_1d(np.array([0.0]), 15e-6, fill_factor=1.1)


# ---------------------------------------------------------------------------
# pixel_aperture_mtf_2d
# ---------------------------------------------------------------------------


class TestPixelApertureMTF2D:
    @pytest.mark.level0
    def test_separable(self) -> None:
        """2-D MTF = MTF_x × MTF_y (separable)."""
        pitch_x = 15e-6
        pitch_y = 18e-6
        fx = np.linspace(0, 5e4, 20)
        fy = np.linspace(0, 5e4, 20)
        FX, FY = np.meshgrid(fx, fy, indexing="xy")

        mtf_2d = pixel_aperture_mtf_2d(FX, FY, pitch_x, pitch_y)
        mtf_x = pixel_aperture_mtf_1d(FX, pitch_x)
        mtf_y = pixel_aperture_mtf_1d(FY, pitch_y)

        np.testing.assert_allclose(mtf_2d, mtf_x * mtf_y, rtol=1e-12)

    @pytest.mark.level0
    def test_dc_is_one(self) -> None:
        fx = np.array([[0.0]])
        fy = np.array([[0.0]])
        mtf = pixel_aperture_mtf_2d(fx, fy, 15e-6, 15e-6)
        assert mtf[0, 0] == pytest.approx(1.0, rel=1e-12)


# ---------------------------------------------------------------------------
# pixel_aperture_kernel_1d
# ---------------------------------------------------------------------------


class TestPixelApertureKernel:
    @pytest.mark.level0
    def test_unit_volume(self) -> None:
        kernel = pixel_aperture_kernel_1d(npix=65, sample_spacing_m=1e-6, pixel_pitch_m=15e-6)
        assert float(kernel.sum()) == pytest.approx(1.0, rel=1e-6)

    @pytest.mark.level0
    def test_non_negative(self) -> None:
        kernel = pixel_aperture_kernel_1d(npix=65, sample_spacing_m=1e-6, pixel_pitch_m=15e-6)
        assert np.all(kernel >= 0.0)

    @pytest.mark.level0
    def test_rect_width(self) -> None:
        """Number of nonzero samples ≈ pitch / spacing."""
        dx = 1e-6
        pitch = 15e-6
        kernel = pixel_aperture_kernel_1d(npix=65, sample_spacing_m=dx, pixel_pitch_m=pitch)
        n_nonzero = np.count_nonzero(kernel)
        expected = int(round(pitch / dx)) + 1  # +1 for boundary inclusion
        assert abs(n_nonzero - expected) <= 1

    @pytest.mark.level0
    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            pixel_aperture_kernel_1d(npix=64, sample_spacing_m=1e-6, pixel_pitch_m=15e-6)

    @pytest.mark.level0
    def test_zero_spacing_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_spacing_m must be positive"):
            pixel_aperture_kernel_1d(npix=65, sample_spacing_m=0.0, pixel_pitch_m=15e-6)


# ---------------------------------------------------------------------------
# Cross-model: FFT of kernel matches analytic MTF
# ---------------------------------------------------------------------------


class TestPixelApertureCrossModel:
    @pytest.mark.level0
    def test_convolution_equals_multiplication(self) -> None:
        """Convolution in real space ≡ multiplication in Fourier space.

        Create a 1-D signal, convolve with the rect kernel, and verify
        the result matches: IFFT(FFT(signal) × FFT(kernel)).
        """
        pitch = 15e-6
        dx = 0.5e-6
        n = 256

        kernel = pixel_aperture_kernel_1d(65, dx, pitch)

        # Simple test signal: Gaussian.
        x = (np.arange(n) - n // 2) * dx
        signal = np.exp(-(x**2) / (2 * (5e-6) ** 2))

        # Real-space convolution.
        from scipy.signal import fftconvolve  # type: ignore[import-untyped]

        conv_real = fftconvolve(signal, kernel, mode="same")

        # Frequency-domain multiplication.
        # Pad kernel to signal length for element-wise multiply.
        k_padded = np.zeros(n, dtype=np.float64)
        kc = len(kernel) // 2
        k_padded[: len(kernel)] = kernel
        k_padded = np.roll(k_padded, -kc)  # center the kernel at index 0

        S = np.fft.fft(signal)
        K = np.fft.fft(k_padded)
        conv_freq = np.real(np.fft.ifft(S * K))

        np.testing.assert_allclose(conv_real, conv_freq, atol=1e-10)
