"""Level 0 tests for polychromatic PSF computation.

Truth anchors:
1. N=1 identity: polychromatic with single wavelength == monochromatic
2. Normalisation: polychromatic PSF sums to 1.0 for any N
3. FWHM broadening: poly FWHM > mono FWHM for MWIR (3.5–5.0 µm)
4. Convergence: FWHM stable as N increases (N=11 vs N=21 < 1%)

See RADIANT_Spatial_Complete.md §3.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.diffraction import compute_polychromatic_psf, compute_psf
from radiant.optics.sampling import compute_sampling

# Reference system: MWIR, D=0.30m, f=1.20m, pitch=18µm
D = 0.30
F = 1.20
PITCH = 18e-6
PUPIL_NPIX = 128
PSF_OVERSAMPLE = 8

FILTER_MIN_UM = 3.5
FILTER_MAX_UM = 5.0
LAM_CENTER_UM = (FILTER_MIN_UM + FILTER_MAX_UM) / 2.0  # 4.25 µm
LAM_CENTER_M = LAM_CENTER_UM * 1e-6


def _fwhm_from_psf(psf_2d: np.ndarray, dx: float) -> float:
    """Compute FWHM along x-axis of a 2-D PSF."""
    n = psf_2d.shape[0]
    center = n // 2
    row = psf_2d[center, :]
    peak = row.max()
    half_max = peak / 2.0
    above = np.where(row >= half_max)[0]
    return float(above[-1] - above[0]) * dx


class TestPolychromaticIdentity:
    """N=1 must reproduce the monochromatic result exactly."""

    def test_single_wavelength_matches_mono(self) -> None:
        """Polychromatic with one wavelength == compute_psf at that wavelength."""
        config = compute_sampling(
            wavelength_m=LAM_CENTER_M,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        mono_psf = compute_psf(config)

        wavelengths = np.array([LAM_CENTER_M])
        weights = np.array([1.0])
        poly_psf, poly_dx = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )

        # Same sample spacing
        assert poly_dx == pytest.approx(config.focal_spacing_m, rel=1e-10)
        # Same PSF data (within floating-point)
        np.testing.assert_allclose(poly_psf, mono_psf, atol=1e-12)


class TestPolychromaticNormalization:
    """Polychromatic PSF must sum to 1.0."""

    @pytest.mark.parametrize("n_wl", [3, 5, 11])
    def test_unit_volume(self, n_wl: int) -> None:
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, n_wl)
        weights = np.ones(n_wl)
        poly_psf, _ = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        assert poly_psf.sum() == pytest.approx(1.0, abs=1e-10)


def _second_moment(psf_2d: np.ndarray, dx: float) -> float:
    """Compute the radial second moment (variance) of a 2-D PSF."""
    n = psf_2d.shape[0]
    center = n // 2
    y, x = np.mgrid[:n, :n]
    r2 = ((x - center) * dx) ** 2 + ((y - center) * dx) ** 2
    return float(np.sum(psf_2d * r2))


def _ensquared_energy_1x1(psf_2d: np.ndarray, dx: float, pitch: float) -> float:
    """Fraction of PSF energy within a 1×1 pixel box centered on peak."""
    n = psf_2d.shape[0]
    center = n // 2
    half_pix = pitch / 2.0
    n_half = int(half_pix / dx)
    lo = max(center - n_half, 0)
    hi = min(center + n_half + 1, n)
    return float(psf_2d[lo:hi, lo:hi].sum())


class TestPolychromaticBroadening:
    """Polychromatic PSF has more energy in wings than band-center mono.

    When averaging Airy patterns of different widths (λ ∝ FWHM), the
    narrow-λ components have higher peaks and dominate the FWHM. But
    the broad-λ components push energy into the wings. The correct
    signature is: larger second moment (variance) and lower ensquared
    energy in the central pixel, not necessarily wider FWHM.
    """

    def test_poly_second_moment_larger(self) -> None:
        """Polychromatic radial variance > monochromatic at band center."""
        config = compute_sampling(
            wavelength_m=LAM_CENTER_M,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        mono_psf = compute_psf(config)
        mono_var = _second_moment(mono_psf, config.focal_spacing_m)

        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 11)
        weights = np.ones(11)
        poly_psf, poly_dx = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        poly_var = _second_moment(poly_psf, poly_dx)

        assert poly_var > mono_var

    def test_poly_ee1x1_lower(self) -> None:
        """Polychromatic EE(1×1) < monochromatic EE(1×1) — more energy in wings."""
        config = compute_sampling(
            wavelength_m=LAM_CENTER_M,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        mono_psf = compute_psf(config)
        mono_ee = _ensquared_energy_1x1(mono_psf, config.focal_spacing_m, PITCH)

        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 11)
        weights = np.ones(11)
        poly_psf, poly_dx = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        poly_ee = _ensquared_energy_1x1(poly_psf, poly_dx, PITCH)

        assert poly_ee < mono_ee

    def test_poly_peak_lower(self) -> None:
        """Polychromatic peak < monochromatic peak (averaging different widths)."""
        config = compute_sampling(
            wavelength_m=LAM_CENTER_M,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        mono_psf = compute_psf(config)

        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 11)
        weights = np.ones(11)
        poly_psf, _ = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )

        assert poly_psf.max() < mono_psf.max()


class TestPolychromaticSymmetry:
    """Circular aperture with uniform weights → symmetric PSF."""

    def test_x_y_symmetric(self) -> None:
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 5)
        weights = np.ones(5)
        poly_psf, _ = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        # PSF should be symmetric: PSF == PSF^T
        np.testing.assert_allclose(poly_psf, poly_psf.T, atol=1e-12)


class TestPolychromaticConvergence:
    """FWHM should converge as N increases."""

    def test_fwhm_converges(self) -> None:
        fwhms = []
        for n_wl in [5, 11, 21]:
            wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, n_wl)
            weights = np.ones(n_wl)
            poly_psf, poly_dx = compute_polychromatic_psf(
                wavelengths_m=wavelengths,
                weights=weights,
                focal_length_m=F,
                aperture_diameter_m=D,
                pixel_pitch_m=PITCH,
                pupil_npix=PUPIL_NPIX,
                psf_oversample=PSF_OVERSAMPLE,
            )
            fwhms.append(_fwhm_from_psf(poly_psf, poly_dx))

        # N=11 vs N=21 should differ < 1%
        assert fwhms[1] == pytest.approx(fwhms[2], rel=0.01)


class TestPolychromaticWeights:
    """Weight handling edge cases."""

    def test_all_positive_weights(self) -> None:
        """All weights must be positive for physical radiance."""
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 5)
        weights = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        poly_psf, _ = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        assert poly_psf.sum() == pytest.approx(1.0, abs=1e-10)

    def test_zero_weight_raises(self) -> None:
        """Zero or negative weight should raise."""
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 3)
        weights = np.array([1.0, 0.0, 1.0])
        with pytest.raises(ValueError, match="positive"):
            compute_polychromatic_psf(
                wavelengths_m=wavelengths,
                weights=weights,
                focal_length_m=F,
                aperture_diameter_m=D,
                pixel_pitch_m=PITCH,
                pupil_npix=PUPIL_NPIX,
                psf_oversample=PSF_OVERSAMPLE,
            )

    def test_negative_weight_raises(self) -> None:
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 3)
        weights = np.array([1.0, -0.5, 1.0])
        with pytest.raises(ValueError, match="positive"):
            compute_polychromatic_psf(
                wavelengths_m=wavelengths,
                weights=weights,
                focal_length_m=F,
                aperture_diameter_m=D,
                pixel_pitch_m=PITCH,
                pupil_npix=PUPIL_NPIX,
                psf_oversample=PSF_OVERSAMPLE,
            )

    def test_mismatched_lengths_raises(self) -> None:
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 5)
        weights = np.array([1.0, 1.0, 1.0])
        with pytest.raises(ValueError, match="length"):
            compute_polychromatic_psf(
                wavelengths_m=wavelengths,
                weights=weights,
                focal_length_m=F,
                aperture_diameter_m=D,
                pixel_pitch_m=PITCH,
                pupil_npix=PUPIL_NPIX,
                psf_oversample=PSF_OVERSAMPLE,
            )


class TestPolychromaticNonNegative:
    """PSF values must be non-negative."""

    def test_no_negative_values(self) -> None:
        wavelengths = np.linspace(FILTER_MIN_UM * 1e-6, FILTER_MAX_UM * 1e-6, 7)
        weights = np.ones(7)
        poly_psf, _ = compute_polychromatic_psf(
            wavelengths_m=wavelengths,
            weights=weights,
            focal_length_m=F,
            aperture_diameter_m=D,
            pixel_pitch_m=PITCH,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=PSF_OVERSAMPLE,
        )
        assert np.all(poly_psf >= 0.0)
