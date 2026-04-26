"""Tests for radiant.optics.defocus.

Category C validation for defocus PSF degradation:
- σ_defocus formula: |δ| / (4 × f/# × √3)
- Isotropic 2-D Gaussian kernel normalisation
- Symmetry: +δ and -δ produce identical σ
- MTF degradation matches analytical exp(-2π²σ²f²)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.defocus import defocus_kernel_2d, defocus_sigma_m

# ---------------------------------------------------------------------------
# defocus_sigma_m
# ---------------------------------------------------------------------------


class TestDefocusSigma:
    """Verify σ_defocus = |δ| / (4 × f/# × √3)."""

    @pytest.mark.level0
    def test_analytical_f3_10um(self) -> None:
        """Truth anchor 1: f/3, δ=10 µm → σ = 10e-6 / (4×3×√3) = 0.481 µm."""
        sigma = defocus_sigma_m(10e-6, 3.0)
        expected = 10e-6 / (4.0 * 3.0 * math.sqrt(3.0))
        assert sigma == pytest.approx(expected, rel=1e-12)
        assert sigma == pytest.approx(0.481e-6, rel=0.005)

    @pytest.mark.level0
    def test_analytical_f10_5um(self) -> None:
        """Truth anchor 2: f/10, δ=5 µm → σ = 5e-6 / (4×10×√3) = 0.0722 µm."""
        sigma = defocus_sigma_m(5e-6, 10.0)
        expected = 5e-6 / (4.0 * 10.0 * math.sqrt(3.0))
        assert sigma == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_symmetry_positive_negative(self) -> None:
        """Positive and negative defocus give identical σ."""
        sigma_pos = defocus_sigma_m(10e-6, 5.0)
        sigma_neg = defocus_sigma_m(-10e-6, 5.0)
        assert sigma_pos == sigma_neg

    @pytest.mark.level0
    def test_zero_defocus_zero_sigma(self) -> None:
        assert defocus_sigma_m(0.0, 5.0) == 0.0

    @pytest.mark.level0
    def test_sigma_scales_with_defocus(self) -> None:
        """σ is linear in |δ|."""
        s1 = defocus_sigma_m(5e-6, 5.0)
        s2 = defocus_sigma_m(10e-6, 5.0)
        assert s2 == pytest.approx(2.0 * s1, rel=1e-12)

    @pytest.mark.level0
    def test_sigma_inversely_proportional_to_fnumber(self) -> None:
        """σ ∝ 1/f/#."""
        s1 = defocus_sigma_m(10e-6, 5.0)
        s2 = defocus_sigma_m(10e-6, 10.0)
        assert s1 == pytest.approx(2.0 * s2, rel=1e-12)

    @pytest.mark.level0
    def test_zero_fnumber_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            defocus_sigma_m(10e-6, 0.0)

    @pytest.mark.level0
    def test_negative_fnumber_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            defocus_sigma_m(10e-6, -1.0)


# ---------------------------------------------------------------------------
# defocus_kernel_2d
# ---------------------------------------------------------------------------


class TestDefocusKernel:
    """Verify 2-D isotropic Gaussian defocus kernel."""

    @pytest.mark.level0
    def test_normalisation(self) -> None:
        """Kernel sums to 1.0."""
        k = defocus_kernel_2d(31, 1e-6, 3e-6)
        assert k.sum() == pytest.approx(1.0, abs=1e-10)

    @pytest.mark.level0
    def test_delta_at_zero_sigma(self) -> None:
        """Zero sigma → delta function."""
        k = defocus_kernel_2d(11, 1e-6, 0.0)
        assert k[5, 5] == 1.0
        assert k.sum() == 1.0

    @pytest.mark.level0
    def test_isotropic(self) -> None:
        """Kernel is symmetric: k[r] depends only on distance from center."""
        k = defocus_kernel_2d(21, 1e-6, 3e-6)
        c = 10
        # Check four points equidistant from center.
        assert k[c, c + 3] == pytest.approx(k[c + 3, c], rel=1e-12)
        assert k[c, c + 3] == pytest.approx(k[c, c - 3], rel=1e-12)
        assert k[c, c + 3] == pytest.approx(k[c - 3, c], rel=1e-12)

    @pytest.mark.level0
    def test_peak_at_center(self) -> None:
        """Maximum value is at the center."""
        k = defocus_kernel_2d(21, 1e-6, 3e-6)
        assert k[10, 10] == k.max()

    @pytest.mark.level0
    def test_even_npix_raises(self) -> None:
        with pytest.raises(ValueError, match="odd"):
            defocus_kernel_2d(10, 1e-6, 3e-6)

    @pytest.mark.level0
    def test_negative_spacing_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            defocus_kernel_2d(11, -1e-6, 3e-6)

    @pytest.mark.level0
    def test_negative_sigma_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            defocus_kernel_2d(11, 1e-6, -3e-6)


# ---------------------------------------------------------------------------
# MTF validation
# ---------------------------------------------------------------------------


class TestDefocusMTF:
    """Verify kernel MTF matches analytical Gaussian MTF.

    Truth anchor 3: MTF_defocus(f) = exp(-2π² σ² f²).
    Compute the MTF of the kernel via FFT and compare at several frequencies.
    """

    @pytest.mark.level0
    def test_kernel_mtf_matches_analytical(self) -> None:
        """At f/3, δ=10 µm: compare kernel MTF to exp(-2π²σ²f²) at 5 frequencies."""
        sigma = defocus_sigma_m(10e-6, 3.0)
        spacing = 0.5e-6  # 0.5 µm sample spacing
        npix = 127  # large enough to capture the kernel
        k = defocus_kernel_2d(npix, spacing, sigma)

        # 1-D MTF: project kernel along y (sum columns), then FFT.
        # This gives the line-spread function whose FT is the 1-D MTF.
        projection = k.sum(axis=0)
        mtf_fft = np.abs(np.fft.fft(projection))
        # Normalise so MTF(0) = 1.
        mtf_fft = mtf_fft / mtf_fft[0]
        freqs = np.fft.fftfreq(npix, d=spacing)

        # Test at 5 positive frequencies up to Nyquist/2.
        f_nyquist = 1.0 / (2.0 * spacing)
        test_freqs = np.linspace(0.1 * f_nyquist, 0.5 * f_nyquist, 5)

        for f_test in test_freqs:
            # Analytical.
            mtf_analytical = math.exp(-2.0 * math.pi**2 * sigma**2 * f_test**2)

            # Interpolate FFT MTF.
            mtf_interp = float(np.interp(f_test, freqs[:npix // 2], mtf_fft[:npix // 2]))

            assert mtf_interp == pytest.approx(mtf_analytical, rel=0.01), (
                f"At f={f_test:.0f} cy/m: kernel MTF={mtf_interp:.4f}, "
                f"analytical={mtf_analytical:.4f}"
            )
