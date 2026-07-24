"""Tests for pupil autocorrelation MTF.

Validates that the optical MTF computed via pupil autocorrelation
matches the MTF derived from FFT of the PSF (Wiener-Khinchin theorem).

Both x and y axes are tested throughout.

See RADIANT_Spatial_Complete.md §1.2 and §9.1.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf_mono import compute_psf
from radiant.optics.psf_poly import compute_polychromatic_psf
from radiant.optics.pupil_amplitude import make_pupil_amplitude
from radiant.optics.pupil_mtf import (
    polychromatic_pupil_mtf,
    pupil_autocorrelation_mtf_1d,
    pupil_autocorrelation_mtf_2d,
)
from radiant.optics.pupil_phase import make_pupil_phase_zernike
from radiant.optics.sampling import PSFSamplingConfig, compute_sampling
from radiant.optics.wavefront import WavefrontError, WfeMode

# ---------------------------------------------------------------------------
# Standard config — matches test_psf.py for consistency
# ---------------------------------------------------------------------------

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.50
APERTURE_M = 0.30
PIXEL_PITCH_M = 15e-6
PUPIL_NPIX = 256
OVERSAMPLE = 16


@pytest.fixture()
def config() -> PSFSamplingConfig:
    return compute_sampling(
        wavelength_m=WAVELENGTH_M,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=APERTURE_M,
        pixel_pitch_m=PIXEL_PITCH_M,
        pupil_npix=PUPIL_NPIX,
        psf_oversample=OVERSAMPLE,
    )


# ---------------------------------------------------------------------------
# Test: Clear circular aperture — cross-check against PSF-FFT
# ---------------------------------------------------------------------------


class TestClearCircularAperture:
    """Pupil autocorrelation MTF must match FFT(PSF) for a perfect optic."""

    @pytest.mark.level1
    def test_2d_matches_psf_fft(self, config: PSFSamplingConfig) -> None:
        """2-D MTF from autocorrelation ≈ 2-D MTF from FFT(PSF)."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        # Autocorrelation path.
        mtf_auto = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)

        # PSF-FFT path.
        psf = compute_psf(config)
        epsf = build_effective_psf(
            psf, [], config.focal_spacing_m, PIXEL_PITCH_M, WAVELENGTH_M * 1e6
        )
        mtf_psf = epsf.mtf_2d()

        # Both should agree to numerical precision.
        np.testing.assert_allclose(mtf_auto, mtf_psf, atol=1e-6)

    @pytest.mark.level1
    @pytest.mark.parametrize("axis", ["x", "y"])
    def test_1d_matches_psf_fft(self, config: PSFSamplingConfig, axis: str) -> None:
        """1-D slice from autocorrelation ≈ 1-D slice from FFT(PSF)."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        freq_auto, mtf_auto = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, axis)

        psf = compute_psf(config)
        epsf = build_effective_psf(
            psf, [], config.focal_spacing_m, PIXEL_PITCH_M, WAVELENGTH_M * 1e6
        )
        freq_psf, mtf_psf = epsf.mtf_1d(axis)

        np.testing.assert_allclose(freq_auto, freq_psf, atol=1e-10)
        np.testing.assert_allclose(mtf_auto, mtf_psf, atol=1e-6)

    @pytest.mark.level1
    def test_dc_equals_one(self, config: PSFSamplingConfig) -> None:
        """MTF(0,0) = 1 for a clear aperture."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        center = config.padded_npix // 2
        assert mtf_2d[center, center] == pytest.approx(1.0, rel=1e-10)

    @pytest.mark.level1
    @pytest.mark.parametrize("axis", ["x", "y"])
    def test_analytic_circular_mtf_anchor(self, config: PSFSamplingConfig, axis: str) -> None:
        """Optical MTF pinned to the analytic circular-aperture closed form (R1.6).

        The other tests here cross-check the pupil-autocorrelation MTF against
        FFT(PSF) — genuinely independent paths, but neither is pinned to an
        external number, so a shared-convention slip in the cutoff or the
        autocorrelation normalization escapes. Anchor against the analytic
        incoherent circular-aperture MTF (Goodman; Track A2 §2):

            MTF(ν̃) = (2/π)[arccos(ν̃) − ν̃·√(1−ν̃²)],  ν̃ = ν/ν_c

        at ν̃ = 0.25, 0.5, 0.75 → 0.685038, 0.391002, 0.144294. ν_c = 1/(λF#).
        The autocorrelation MTF is interpolated to those frequencies; the
        residual (~2e-4) is interpolation + pupil-grid discretization.
        """
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))
        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        freq, mtf = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, axis)

        nu_c = 1.0 / (WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M)  # cy/m
        for nu_tilde, expected in ((0.25, 0.685038), (0.5, 0.391002), (0.75, 0.144294)):
            value = float(np.interp(nu_tilde * nu_c, freq, mtf))
            analytic = (2.0 / math.pi) * (
                math.acos(nu_tilde) - nu_tilde * math.sqrt(1.0 - nu_tilde**2)
            )
            assert analytic == pytest.approx(expected, rel=1e-5)  # literal ↔ formula
            assert value == pytest.approx(expected, rel=1e-3)

    @pytest.mark.level1
    def test_non_negative(self, config: PSFSamplingConfig) -> None:
        """MTF must be non-negative (physical requirement for incoherent)."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        assert np.all(mtf_2d >= -1e-15)  # allow tiny numerical noise

    @pytest.mark.level1
    @pytest.mark.parametrize("axis", ["x", "y"])
    def test_symmetric_for_clear_aperture(self, config: PSFSamplingConfig, axis: str) -> None:
        """Clear circular aperture is symmetric → x and y slices match."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        _, mtf_x = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "x")
        _, mtf_y = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "y")

        np.testing.assert_allclose(mtf_x, mtf_y, atol=1e-10)


# ---------------------------------------------------------------------------
# Test: Obscured aperture
# ---------------------------------------------------------------------------


class TestObscuredAperture:
    """Pupil autocorrelation with central obscuration matches PSF-FFT path."""

    OBSCURATION = 0.33

    @pytest.mark.level1
    @pytest.mark.parametrize("axis", ["x", "y"])
    def test_matches_psf_fft(self, config: PSFSamplingConfig, axis: str) -> None:
        amplitude = make_pupil_amplitude(config.pupil_npix, self.OBSCURATION)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        freq_auto, mtf_auto = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, axis)

        psf = compute_psf(config, obscuration_ratio=self.OBSCURATION)
        epsf = build_effective_psf(
            psf, [], config.focal_spacing_m, PIXEL_PITCH_M, WAVELENGTH_M * 1e6
        )
        _, mtf_psf = epsf.mtf_1d(axis)

        np.testing.assert_allclose(mtf_auto, mtf_psf, atol=1e-6)

    @pytest.mark.level1
    def test_dc_equals_one(self, config: PSFSamplingConfig) -> None:
        amplitude = make_pupil_amplitude(config.pupil_npix, self.OBSCURATION)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        center = config.padded_npix // 2
        assert mtf_2d[center, center] == pytest.approx(1.0, rel=1e-10)


# ---------------------------------------------------------------------------
# Test: Zernike WFE — asymmetric aberrations
# ---------------------------------------------------------------------------


class TestZernikeWFE:
    """Pupil autocorrelation with Zernike WFE matches PSF-FFT path.

    Uses coma (Z7) and defocus (Z4) — coma breaks x/y symmetry.
    """

    ZERNIKE_COEFFS = {4: 0.1, 7: 0.2}  # waves at reference wavelength
    REF_WAVELENGTH_UM = WAVELENGTH_M * 1e6  # same as operating

    @pytest.mark.level1
    @pytest.mark.parametrize("axis", ["x", "y"])
    def test_matches_psf_fft(self, config: PSFSamplingConfig, axis: str) -> None:
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = make_pupil_phase_zernike(
            config.pupil_npix,
            self.ZERNIKE_COEFFS,
            reference_wavelength_m=self.REF_WAVELENGTH_UM * 1e-6,
            operating_wavelength_m=config.wavelength_m,
        )

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        _, mtf_auto = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, axis)

        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs=self.ZERNIKE_COEFFS,
            reference_wavelength_um=self.REF_WAVELENGTH_UM,
        )
        psf = compute_psf(config, wfe=wfe)
        epsf = build_effective_psf(
            psf, [], config.focal_spacing_m, PIXEL_PITCH_M, WAVELENGTH_M * 1e6
        )
        _, mtf_psf = epsf.mtf_1d(axis)

        np.testing.assert_allclose(mtf_auto, mtf_psf, atol=1e-5)

    @pytest.mark.level1
    def test_coma_breaks_symmetry(self, config: PSFSamplingConfig) -> None:
        """Coma (Z7) is asymmetric — x and y MTF should differ."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        # Only coma, no defocus — pure asymmetry.
        phase = make_pupil_phase_zernike(
            config.pupil_npix,
            {7: 0.3},
            reference_wavelength_m=config.wavelength_m,
            operating_wavelength_m=config.wavelength_m,
        )

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        _, mtf_x = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "x")
        _, mtf_y = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "y")

        # Coma Z7 (vertical coma) degrades y more than x.
        # The two slices should not be equal.
        assert not np.allclose(mtf_x, mtf_y, atol=1e-3)

    @pytest.mark.level1
    def test_dc_equals_one(self, config: PSFSamplingConfig) -> None:
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = make_pupil_phase_zernike(
            config.pupil_npix,
            self.ZERNIKE_COEFFS,
            reference_wavelength_m=self.REF_WAVELENGTH_UM * 1e-6,
            operating_wavelength_m=config.wavelength_m,
        )

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        center = config.padded_npix // 2
        assert mtf_2d[center, center] == pytest.approx(1.0, rel=1e-10)

    @pytest.mark.level1
    def test_non_negative(self, config: PSFSamplingConfig) -> None:
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = make_pupil_phase_zernike(
            config.pupil_npix,
            self.ZERNIKE_COEFFS,
            reference_wavelength_m=self.REF_WAVELENGTH_UM * 1e-6,
            operating_wavelength_m=config.wavelength_m,
        )

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        assert np.all(mtf_2d >= -1e-15)


# ---------------------------------------------------------------------------
# Test: Invalid axis
# ---------------------------------------------------------------------------


class TestInvalidAxis:
    @pytest.mark.level1
    def test_invalid_axis_raises(self, config: PSFSamplingConfig) -> None:
        mtf_2d = np.ones((config.padded_npix, config.padded_npix))
        with pytest.raises(ValueError, match="axis must be"):
            pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "z")


# ---------------------------------------------------------------------------
# Phase 2: Polychromatic optical MTF
# ---------------------------------------------------------------------------


class TestPolychromaticPupilMTF:
    """Tests for polychromatic pupil autocorrelation MTF."""

    @pytest.mark.level1
    def test_single_wavelength_matches_mono(self, config: PSFSamplingConfig) -> None:
        """Polychromatic with 1 wavelength = monochromatic result."""
        amplitude = make_pupil_amplitude(config.pupil_npix)
        phase = np.zeros((config.pupil_npix, config.pupil_npix))

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        _, mtf_mono_x = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "x")
        _, mtf_mono_y = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, "y")

        freq_poly, mtf_poly_x, mtf_poly_y = polychromatic_pupil_mtf(
            wavelengths_m=np.array([WAVELENGTH_M]),
            weights=np.array([1.0]),
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )

        # Interpolate mono onto poly's grid for comparison.
        freq_mono = np.arange(len(mtf_mono_x)) / (config.padded_npix * config.focal_spacing_m)
        mtf_mono_x_interp = np.interp(freq_poly, freq_mono, mtf_mono_x, right=0.0)
        mtf_mono_y_interp = np.interp(freq_poly, freq_mono, mtf_mono_y, right=0.0)

        # Where both have signal, they should match closely.
        mask = mtf_mono_x_interp > 0.01
        np.testing.assert_allclose(mtf_poly_x[mask], mtf_mono_x_interp[mask], atol=1e-4)
        np.testing.assert_allclose(mtf_poly_y[mask], mtf_mono_y_interp[mask], atol=1e-4)

    @pytest.mark.level1
    @pytest.mark.parametrize("axis_idx", [0, 1], ids=["x", "y"])
    def test_multi_wavelength_matches_psf_fft(self, axis_idx: int) -> None:
        """Polychromatic pupil MTF ≈ FFT of polychromatic PSF."""
        axis = "x" if axis_idx == 0 else "y"
        wl_m = np.array([3.5e-6, 4.0e-6, 4.5e-6, 5.0e-6])
        weights = np.ones(len(wl_m))

        # Pupil autocorrelation path.
        freq_auto, mtf_x, mtf_y = polychromatic_pupil_mtf(
            wavelengths_m=wl_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )
        mtf_auto = mtf_x if axis == "x" else mtf_y

        # PSF-FFT path (polychromatic PSF → EffectivePSF → mtf_1d).
        poly_result = compute_polychromatic_psf(
            wavelengths_m=wl_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )
        epsf = build_effective_psf(
            poly_result.combined_psf,
            [],
            poly_result.pixel_scale_m,
            PIXEL_PITCH_M,
            float(np.mean(wl_m)) * 1e6,
        )
        freq_psf, mtf_psf = epsf.mtf_1d(axis)

        # Interpolate PSF-path MTF onto autocorrelation frequency grid.
        mtf_psf_interp = np.interp(freq_auto, freq_psf, mtf_psf, right=0.0)

        # Compare where both have significant values.
        mask = (mtf_auto > 0.01) & (mtf_psf_interp > 0.01)
        np.testing.assert_allclose(mtf_auto[mask], mtf_psf_interp[mask], atol=5e-3)

    @pytest.mark.level1
    def test_dc_equals_one(self) -> None:
        """DC value of polychromatic MTF is 1.0."""
        wl_m = np.array([3.5e-6, 5.0e-6])
        weights = np.array([1.0, 1.0])

        freq, mtf_x, mtf_y = polychromatic_pupil_mtf(
            wavelengths_m=wl_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )

        assert mtf_x[0] == pytest.approx(1.0, rel=1e-6)
        assert mtf_y[0] == pytest.approx(1.0, rel=1e-6)

    @pytest.mark.level1
    def test_weight_sensitivity(self) -> None:
        """Different weight distributions produce different MTFs."""
        wl_m = np.array([3.5e-6, 5.0e-6])

        _, mtf_blue_x, _ = polychromatic_pupil_mtf(
            wavelengths_m=wl_m,
            weights=np.array([10.0, 1.0]),  # blue-weighted
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )

        _, mtf_red_x, _ = polychromatic_pupil_mtf(
            wavelengths_m=wl_m,
            weights=np.array([1.0, 10.0]),  # red-weighted
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            pupil_npix=PUPIL_NPIX,
            psf_oversample=OVERSAMPLE,
        )

        # Shapes should differ — blue emphasis gives different MTF profile.
        assert not np.allclose(mtf_blue_x, mtf_red_x, atol=1e-3)
