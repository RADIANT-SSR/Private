"""Tests for diffraction engine: pupil function and FFT-based PSF.

Validates against Airy pattern analytic results:
- Peak at origin
- First zero at r = 1.22 λ f/D
- FWHM at 1.028 λ f/D
- Strehl ratio = 1.0 for unaberrated system
- Maréchal Strehl ≈ exp(-(2π·σ)²) for small WFE

See RADIANT_Spatial_Complete.md §3.1.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.special import j1  # type: ignore[import-untyped]

from radiant.optics.psf_mono import compute_psf
from radiant.optics.psf_poly import (
    PolychromaticPSFResult,
    compute_polychromatic_psf,
)
from radiant.optics.pupil_amplitude import make_pupil_amplitude
from radiant.optics.pupil_phase import make_pupil_phase
from radiant.optics.sampling import PSFSamplingConfig, compute_sampling
from radiant.optics.strehl import compute_strehl
from radiant.optics.wavefront import WavefrontError, WfeMode

# ---------------------------------------------------------------------------
# Standard test configuration — high-resolution for accuracy
# ---------------------------------------------------------------------------

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.50
APERTURE_M = 0.30
PIXEL_PITCH_M = 15e-6
PUPIL_NPIX = 256
OVERSAMPLE = 16  # high oversample for accurate Airy comparison


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


@pytest.fixture()
def psf_unaberrated(config: PSFSamplingConfig) -> np.ndarray:
    return compute_psf(config, obscuration_ratio=0.0)


# ---------------------------------------------------------------------------
# Pupil amplitude
# ---------------------------------------------------------------------------


class TestPupilAmplitude:
    def test_shape(self) -> None:
        mask = make_pupil_amplitude(64)
        assert mask.shape == (64, 64)

    def test_binary(self) -> None:
        mask = make_pupil_amplitude(64)
        unique = np.unique(mask)
        assert set(unique) <= {0.0, 1.0}

    def test_circular(self) -> None:
        """Mask should be approximately circular — fill fraction near π/4."""
        mask = make_pupil_amplitude(512)
        fill = mask.sum() / mask.size
        assert fill == pytest.approx(math.pi / 4, abs=0.01)

    def test_obscuration_removes_center(self) -> None:
        mask_clear = make_pupil_amplitude(128, obscuration_ratio=0.0)
        mask_obs = make_pupil_amplitude(128, obscuration_ratio=0.3)
        # Obscured mask has fewer clear pixels.
        assert mask_obs.sum() < mask_clear.sum()
        # Center should be zero.
        c = 64
        assert mask_obs[c, c] == 0.0

    def test_obscuration_ratio_bounds(self) -> None:
        with pytest.raises(ValueError, match="obscuration_ratio"):
            make_pupil_amplitude(64, obscuration_ratio=1.0)
        with pytest.raises(ValueError, match="obscuration_ratio"):
            make_pupil_amplitude(64, obscuration_ratio=-0.1)


# ---------------------------------------------------------------------------
# Pupil phase
# ---------------------------------------------------------------------------


class TestPupilPhase:
    def test_zero_wfe_returns_zeros(self) -> None:
        phase = make_pupil_phase(64, wfe_rms_waves=0.0)
        np.testing.assert_array_equal(phase, np.zeros((64, 64)))

    def test_nonzero_wfe_has_correct_rms(self) -> None:
        wfe = 0.07  # waves (~λ/14)
        phase = make_pupil_phase(128, wfe_rms_waves=wfe)
        expected_rms_rad = 2.0 * math.pi * wfe
        actual_rms = float(phase.std())
        assert actual_rms == pytest.approx(expected_rms_rad, rel=0.01)

    def test_deterministic(self) -> None:
        """Same seed → same phase screen."""
        p1 = make_pupil_phase(64, wfe_rms_waves=0.1)
        p2 = make_pupil_phase(64, wfe_rms_waves=0.1)
        np.testing.assert_array_equal(p1, p2)

    def test_negative_wfe_rejected(self) -> None:
        with pytest.raises(ValueError, match="wfe_rms_waves must be non-negative"):
            make_pupil_phase(64, wfe_rms_waves=-0.05)


# ---------------------------------------------------------------------------
# PSF — basic properties
# ---------------------------------------------------------------------------


class TestPSFBasic:
    def test_shape(self, config: PSFSamplingConfig, psf_unaberrated: np.ndarray) -> None:
        assert psf_unaberrated.shape == (config.padded_npix, config.padded_npix)

    def test_non_negative(self, psf_unaberrated: np.ndarray) -> None:
        assert np.all(psf_unaberrated >= 0.0)

    def test_unit_volume(self, psf_unaberrated: np.ndarray) -> None:
        """PSF sums to 1.0 (unit-volume normalised)."""
        assert float(psf_unaberrated.sum()) == pytest.approx(1.0, rel=1e-10)

    def test_peak_at_center(self, config: PSFSamplingConfig, psf_unaberrated: np.ndarray) -> None:
        """Peak should be at or very near the grid center."""
        peak_idx = np.unravel_index(psf_unaberrated.argmax(), psf_unaberrated.shape)
        center = config.padded_npix // 2
        assert abs(peak_idx[0] - center) <= 1
        assert abs(peak_idx[1] - center) <= 1

    def test_symmetric(self, psf_unaberrated: np.ndarray) -> None:
        """Unaberrated circular aperture PSF should be ~symmetric."""
        n = psf_unaberrated.shape[0]
        c = n // 2
        # Compare horizontal and vertical slices from center.
        h_slice = psf_unaberrated[c, c:]
        v_slice = psf_unaberrated[c:, c]
        np.testing.assert_allclose(h_slice, v_slice, rtol=1e-6)


# ---------------------------------------------------------------------------
# Truth Anchor 1: Airy first zero at 1.22 λf/D
# ---------------------------------------------------------------------------


class TestAiryFirstZero:
    def test_first_zero_location(
        self, config: PSFSamplingConfig, psf_unaberrated: np.ndarray
    ) -> None:
        """First zero of the Airy pattern at r = 1.22 λf/D.

        Truth anchor: Born & Wolf, Principles of Optics, §8.5.2.
        Exact: first zero of J_1(x)/x at x = 1.21966989...
        """
        n = config.padded_npix
        c = n // 2
        dx = config.focal_spacing_m

        # Radial profile from center.
        profile = psf_unaberrated[c, c:]

        # Expected first zero radius.
        r_zero_expected = 1.21966989 * WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M

        # Find the first minimum (proxy for first zero).
        # Look for where the profile first reaches a local minimum after the peak.
        for i in range(1, len(profile) - 1):
            if profile[i] < profile[i - 1] and profile[i] <= profile[i + 1]:
                r_min = i * dx
                break
        else:
            pytest.fail("No local minimum found in PSF profile")

        # The first minimum should be near the Airy first zero within 1%.
        assert r_min == pytest.approx(r_zero_expected, rel=0.01)


# ---------------------------------------------------------------------------
# Truth Anchor 2: Airy FWHM ≈ 1.028 λf/D
# ---------------------------------------------------------------------------


class TestAiryFWHM:
    def test_fwhm(self, config: PSFSamplingConfig, psf_unaberrated: np.ndarray) -> None:
        """FWHM of Airy pattern ≈ 1.028 λf/D.

        Truth anchor: Born & Wolf, Principles of Optics.
        """
        n = config.padded_npix
        c = n // 2
        dx = config.focal_spacing_m

        profile = psf_unaberrated[c, c:]
        peak = profile[0]
        half_max = peak / 2.0

        # Find half-max crossing via interpolation.
        below = np.where(profile < half_max)[0]
        assert len(below) > 0, "Profile never drops below half-max"
        idx = below[0]
        if idx > 0:
            y0, y1 = profile[idx - 1], profile[idx]
            frac = (half_max - y0) / (y1 - y0) if y1 != y0 else 0.0
            r_half = (idx - 1 + frac) * dx
        else:
            r_half = 0.0

        fwhm_measured = 2.0 * r_half
        fwhm_expected = 1.028 * WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M

        assert fwhm_measured == pytest.approx(fwhm_expected, rel=0.02)


# ---------------------------------------------------------------------------
# Truth Anchor 3: Strehl ratio
# ---------------------------------------------------------------------------


class TestStrehl:
    def test_unaberrated_strehl_is_one(self, config: PSFSamplingConfig) -> None:
        """Unaberrated system -> Strehl = 1.0."""
        psf = compute_psf(config)
        psf_ref = compute_psf(config)
        strehl = compute_strehl(psf, psf_ref)
        assert strehl == pytest.approx(1.0, rel=1e-10)

    def test_marechal_strehl(self, config: PSFSamplingConfig) -> None:
        """Marechal approximation: Strehl ~ exp(-(2*pi*sigma)^2) for small WFE.

        Truth anchor: Marechal (1947), valid for Strehl > 0.3.
        At WFE = lambda/14 = 0.0714 waves, Marechal predicts ~0.817.
        """
        wfe_waves = 1.0 / 14.0
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=wfe_waves)
        psf_ref = compute_psf(config)
        psf_aberrated = compute_psf(config, wfe=wfe)
        strehl = compute_strehl(psf_aberrated, psf_ref)

        marechal = math.exp(-(2 * math.pi * wfe_waves) ** 2)
        assert strehl == pytest.approx(marechal, rel=0.05)

    def test_strehl_decreases_with_wfe(self, config: PSFSamplingConfig) -> None:
        """More WFE -> lower Strehl."""
        psf_ref = compute_psf(config)
        wfe_small = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.05)
        wfe_large = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.15)
        psf_small = compute_psf(config, wfe=wfe_small)
        psf_large = compute_psf(config, wfe=wfe_large)
        s_small = compute_strehl(psf_small, psf_ref)
        s_large = compute_strehl(psf_large, psf_ref)
        assert s_small > s_large

    def test_zero_ref_raises(self) -> None:
        psf = np.ones((4, 4))
        psf_ref = np.zeros((4, 4))
        with pytest.raises(ValueError, match="Reference PSF peak is zero"):
            compute_strehl(psf, psf_ref)


# ---------------------------------------------------------------------------
# Obscuration
# ---------------------------------------------------------------------------


class TestObscuration:
    def test_obscuration_lowers_peak(self, config: PSFSamplingConfig) -> None:
        """Central obscuration redistributes energy -> lower peak."""
        psf_clear = compute_psf(config, obscuration_ratio=0.0)
        psf_obs = compute_psf(config, obscuration_ratio=0.3)
        assert psf_obs.max() < psf_clear.max()

    def test_obscuration_preserves_total(self, config: PSFSamplingConfig) -> None:
        """Both PSFs should sum to 1.0."""
        psf_obs = compute_psf(config, obscuration_ratio=0.3)
        assert float(psf_obs.sum()) == pytest.approx(1.0, rel=1e-10)


# ---------------------------------------------------------------------------
# Bessel function cross-check
# ---------------------------------------------------------------------------


class TestBesselComparison:
    def test_airy_profile_matches_bessel(
        self, config: PSFSamplingConfig, psf_unaberrated: np.ndarray
    ) -> None:
        """Compare FFT PSF radial profile to analytic Airy function.

        Airy(r) = [2·J_1(x)/x]² where x = π·D·r / (λ·f).
        """
        n = config.padded_npix
        c = n // 2
        dx = config.focal_spacing_m

        # FFT profile (normalised to peak=1).
        profile_fft = psf_unaberrated[c, c:].copy()
        profile_fft /= profile_fft[0]

        # Analytic Airy profile.
        r = np.arange(len(profile_fft)) * dx
        x = math.pi * APERTURE_M * r / (WAVELENGTH_M * FOCAL_LENGTH_M)

        airy = np.ones_like(x)
        mask = x > 0
        airy[mask] = (2.0 * j1(x[mask]) / x[mask]) ** 2

        # Compare over the main lobe (up to first zero + a bit).
        r_zero = 1.22 * WAVELENGTH_M * FOCAL_LENGTH_M / APERTURE_M
        n_compare = int(1.5 * r_zero / dx)
        n_compare = min(n_compare, len(profile_fft))

        # Allow 2% absolute tolerance due to discrete sampling.
        np.testing.assert_allclose(
            profile_fft[:n_compare], airy[:n_compare], atol=0.02
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_config_same_psf(self, config: PSFSamplingConfig) -> None:
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.05)
        psf1 = compute_psf(config, wfe=wfe)
        psf2 = compute_psf(config, wfe=wfe)
        np.testing.assert_array_equal(psf1, psf2)


# ---------------------------------------------------------------------------
# Zernike mode PSF
# ---------------------------------------------------------------------------


class TestZernikePSF:
    """Tests for compute_psf with WfeMode.ZERNIKE."""

    def test_zernike_defocus_lowers_strehl(self, config: PSFSamplingConfig) -> None:
        """Z4 (defocus) should reduce the Strehl ratio."""
        psf_ref = compute_psf(config)
        wfe_z = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.1},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf_z = compute_psf(config, wfe=wfe_z)
        strehl = compute_strehl(psf_z, psf_ref)
        assert strehl < 1.0

    def test_zernike_coma_asymmetric(self, config: PSFSamplingConfig) -> None:
        """Z7 (coma y) should produce an asymmetric PSF along y."""
        wfe_z = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={7: 0.15},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf_z = compute_psf(config, wfe=wfe_z)
        c = psf_z.shape[0] // 2
        upper = psf_z[:c, :].sum()
        lower = psf_z[c:, :].sum()
        assert upper != pytest.approx(lower, abs=0.01)

    def test_zernike_matches_scalar_strehl(self, config: PSFSamplingConfig) -> None:
        """Zernike with same RMS as scalar should give similar Strehl.

        Z4 with coefficient c has RMS = |c| (Noll normalisation).
        A scalar_rms with the same RMS should give the same Marechal Strehl.
        """
        c4 = 0.08  # waves
        rms = abs(c4)

        psf_ref = compute_psf(config)
        wfe_scalar = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=rms)
        wfe_zernike = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: c4},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf_s = compute_psf(config, wfe=wfe_scalar)
        psf_z = compute_psf(config, wfe=wfe_zernike)

        strehl_s = compute_strehl(psf_s, psf_ref)
        strehl_z = compute_strehl(psf_z, psf_ref)

        # Marechal Strehl depends only on RMS, so both should agree
        # (within limits — random vs deterministic phase shape).
        marechal = math.exp(-(2 * math.pi * rms) ** 2)
        assert strehl_z == pytest.approx(marechal, rel=0.10)
        assert strehl_s == pytest.approx(marechal, rel=0.10)

    def test_zernike_deterministic(self, config: PSFSamplingConfig) -> None:
        """Same coefficients -> identical PSF."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.1, 7: 0.05},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf1 = compute_psf(config, wfe=wfe)
        psf2 = compute_psf(config, wfe=wfe)
        np.testing.assert_array_equal(psf1, psf2)

    def test_zernike_unit_volume(self, config: PSFSamplingConfig) -> None:
        """Zernike PSF should still sum to 1.0."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.2, 5: 0.1},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf_z = compute_psf(config, wfe=wfe)
        assert float(psf_z.sum()) == pytest.approx(1.0, rel=1e-10)

    def test_zernike_differs_from_random(self, config: PSFSamplingConfig) -> None:
        """Zernike PSF shape should differ from random-phase scalar PSF."""
        rms = 0.1
        wfe_scalar = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=rms)
        wfe_zernike = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: rms},
            reference_wavelength_um=WAVELENGTH_M * 1e6,
        )
        psf_s = compute_psf(config, wfe=wfe_scalar)
        psf_z = compute_psf(config, wfe=wfe_zernike)

        # They should NOT be identical (different phase screens)
        assert not np.allclose(psf_s, psf_z, atol=1e-10)


# ---------------------------------------------------------------------------
# PolychromaticPSFResult
# ---------------------------------------------------------------------------


class TestPolychromaticPSFResult:
    """Tests for the structured polychromatic PSF return type."""

    def test_returns_result_type(self) -> None:
        wavelengths_m = np.array([3.5e-6, 4.0e-6, 5.0e-6])
        weights = np.ones(3)
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        assert isinstance(result, PolychromaticPSFResult)

    def test_combined_psf_unit_volume(self) -> None:
        wavelengths_m = np.array([3.5e-6, 4.0e-6, 5.0e-6])
        weights = np.ones(3)
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        assert float(result.combined_psf.sum()) == pytest.approx(1.0, rel=1e-6)

    def test_per_wavelength_none_by_default(self) -> None:
        wavelengths_m = np.array([3.5e-6, 5.0e-6])
        weights = np.ones(2)
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        assert result.per_wavelength is None

    def test_per_wavelength_stored_when_requested(self) -> None:
        wavelengths_m = np.array([3.5e-6, 4.0e-6, 5.0e-6])
        weights = np.ones(3)
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            store_per_wavelength=True,
        )
        assert result.per_wavelength is not None
        assert len(result.per_wavelength) == 3
        # Keys should be wavelengths in um
        for wl_um in result.per_wavelength:
            assert 3.0 < wl_um < 6.0

    def test_blue_psf_narrower_than_red(self) -> None:
        """Shorter wavelength -> narrower Airy disk."""
        wavelengths_m = np.array([3.5e-6, 5.0e-6])
        weights = np.ones(2)
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            store_per_wavelength=True,
        )
        assert result.per_wavelength is not None
        blue_psf = result.per_wavelength[3.5]
        red_psf = result.per_wavelength[5.0]
        # Blue peak should be higher (narrower Airy -> more concentrated)
        assert blue_psf.max() > red_psf.max()

    def test_wavelengths_um_field(self) -> None:
        wavelengths_m = np.array([3.5e-6, 5.0e-6])
        weights = np.array([1.0, 2.0])
        result = compute_polychromatic_psf(
            wavelengths_m=wavelengths_m,
            weights=weights,
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        np.testing.assert_allclose(result.wavelengths_um, [3.5, 5.0], rtol=1e-10)
        np.testing.assert_allclose(result.weights, [1.0, 2.0], rtol=1e-10)

    def test_single_wavelength_result(self) -> None:
        """Single wavelength should still return PolychromaticPSFResult."""
        result = compute_polychromatic_psf(
            wavelengths_m=np.array([4.0e-6]),
            weights=np.array([1.0]),
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        assert isinstance(result, PolychromaticPSFResult)
        assert float(result.combined_psf.sum()) == pytest.approx(1.0, rel=1e-10)

    def test_wfe_threaded_to_polychromatic(self) -> None:
        """WavefrontError should propagate to polychromatic path."""
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.1)
        result_no_wfe = compute_polychromatic_psf(
            wavelengths_m=np.array([3.5e-6, 5.0e-6]),
            weights=np.ones(2),
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
        )
        result_wfe = compute_polychromatic_psf(
            wavelengths_m=np.array([3.5e-6, 5.0e-6]),
            weights=np.ones(2),
            focal_length_m=FOCAL_LENGTH_M,
            aperture_diameter_m=APERTURE_M,
            pixel_pitch_m=PIXEL_PITCH_M,
            wfe=wfe,
        )
        # WFE should lower the peak
        assert result_wfe.combined_psf.max() < result_no_wfe.combined_psf.max()
