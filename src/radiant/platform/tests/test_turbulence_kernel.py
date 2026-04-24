"""Tests for the Kolmogorov turbulence kernel.

Validates that the kernel built via inverse-FFT of the analytic MTF
is normalised, consistent with the MTF formula, and behaves correctly
at extreme r0 values.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.platform.turbulence_kernel import kolmogorov_kernel_2d

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.0
SAMPLE_SPACING_M = 2.5e-6


class TestKernelNormalisation:
    """Kernel sums to 1.0."""

    def test_sums_to_unity(self) -> None:
        kernel = kolmogorov_kernel_2d(
            npix=65,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=0.10,
            focal_length_m=FOCAL_LENGTH_M,
        )
        assert kernel.sum() == pytest.approx(1.0, abs=1e-10)


class TestKernelMTFConsistency:
    """FFT of kernel matches the analytic Kolmogorov MTF."""

    def test_fft_matches_analytic(self) -> None:
        r0_m = 0.10
        npix = 65
        kernel = kolmogorov_kernel_2d(
            npix=npix,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=r0_m,
            focal_length_m=FOCAL_LENGTH_M,
        )

        # FFT of the spatial kernel = MTF.
        mtf_from_kernel = np.abs(np.fft.fft2(np.fft.ifftshift(kernel)))

        # Build analytic MTF on the same frequency grid.
        freq_1d = np.fft.fftfreq(npix, d=SAMPLE_SPACING_M)
        fx, fy = np.meshgrid(freq_1d, freq_1d, indexing="xy")
        f_focal = np.sqrt(fx**2 + fy**2)
        f_angular = f_focal * FOCAL_LENGTH_M
        arg = WAVELENGTH_M * f_angular / r0_m
        mtf_analytic = np.exp(-3.44 * arg ** (5.0 / 3.0))

        np.testing.assert_allclose(mtf_from_kernel, mtf_analytic, atol=1e-6)


class TestKernelExtremes:
    """Kernel behaviour at extreme r0 values."""

    def test_large_r0_approaches_delta(self) -> None:
        """Weak turbulence (large r0) → kernel approaches delta function."""
        kernel = kolmogorov_kernel_2d(
            npix=33,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=10.0,  # Very large r0 = negligible turbulence
            focal_length_m=FOCAL_LENGTH_M,
        )
        c = 33 // 2
        # Center pixel should have nearly all energy.
        assert kernel[c, c] > 0.95

    def test_small_r0_is_broad(self) -> None:
        """Strong turbulence (small r0) → kernel is broad."""
        kernel = kolmogorov_kernel_2d(
            npix=65,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=0.02,  # Small r0 = strong turbulence
            focal_length_m=FOCAL_LENGTH_M,
        )
        c = 65 // 2
        # Center pixel should NOT have most energy.
        assert kernel[c, c] < 0.5


class TestKernelShape:
    """Kernel has correct shape and is non-negative."""

    def test_shape(self) -> None:
        kernel = kolmogorov_kernel_2d(
            npix=33,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=0.10,
            focal_length_m=FOCAL_LENGTH_M,
        )
        assert kernel.shape == (33, 33)

    def test_non_negative(self) -> None:
        kernel = kolmogorov_kernel_2d(
            npix=65,
            sample_spacing_m=SAMPLE_SPACING_M,
            wavelength_m=WAVELENGTH_M,
            r0_m=0.05,
            focal_length_m=FOCAL_LENGTH_M,
        )
        assert np.all(kernel >= 0.0)
