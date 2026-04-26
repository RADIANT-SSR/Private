"""Tests for PSF sampling configuration and FFT sizing.

Validates the coupled constraint Δx_focal = λ·f / (N · Δx_pupil)
and edge-case handling in compute_sampling().

See RADIANT_Spatial_Complete.md §4 for the derivation.
"""

from __future__ import annotations

import pytest

from radiant.optics.sampling import PSFSamplingConfig, _next_power_of_2, compute_sampling

# ---------------------------------------------------------------------------
# Reference parameters (MWIR, f/5)
# ---------------------------------------------------------------------------

WAVELENGTH_M = 4.0e-6
FOCAL_LENGTH_M = 1.50
APERTURE_M = 0.30
PIXEL_PITCH_M = 15e-6
PUPIL_NPIX = 128
OVERSAMPLE = 8


@pytest.fixture()
def ref_config() -> PSFSamplingConfig:
    """Standard MWIR sampling config for reuse."""
    return compute_sampling(
        wavelength_m=WAVELENGTH_M,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=APERTURE_M,
        pixel_pitch_m=PIXEL_PITCH_M,
        pupil_npix=PUPIL_NPIX,
        psf_oversample=OVERSAMPLE,
    )


# ---------------------------------------------------------------------------
# _next_power_of_2
# ---------------------------------------------------------------------------


class TestNextPowerOf2:
    @pytest.mark.level0
    def test_exact_power(self) -> None:
        assert _next_power_of_2(256) == 256

    @pytest.mark.level0
    def test_just_above(self) -> None:
        assert _next_power_of_2(257) == 512

    @pytest.mark.level0
    def test_one(self) -> None:
        assert _next_power_of_2(1) == 1

    @pytest.mark.level0
    def test_zero(self) -> None:
        assert _next_power_of_2(0) == 1

    @pytest.mark.level0
    def test_negative(self) -> None:
        assert _next_power_of_2(-5) == 1


# ---------------------------------------------------------------------------
# compute_sampling — basic
# ---------------------------------------------------------------------------


class TestComputeSampling:
    @pytest.mark.level0
    def test_pupil_spacing(self, ref_config: PSFSamplingConfig) -> None:
        """Pupil spacing = D / pupil_npix."""
        expected = APERTURE_M / PUPIL_NPIX
        assert ref_config.pupil_spacing_m == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_padded_is_power_of_2(self, ref_config: PSFSamplingConfig) -> None:
        n = ref_config.padded_npix
        assert n & (n - 1) == 0, f"{n} is not a power of 2"

    @pytest.mark.level0
    def test_padded_ge_pupil(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.padded_npix >= ref_config.pupil_npix

    @pytest.mark.level0
    def test_fft_constraint(self, ref_config: PSFSamplingConfig) -> None:
        """Δx_focal = λ·f / (N · Δx_pupil)."""
        expected = (
            ref_config.wavelength_m
            * ref_config.focal_length_m
            / (ref_config.padded_npix * ref_config.pupil_spacing_m)
        )
        assert ref_config.focal_spacing_m == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_focal_spacing_um(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.focal_spacing_um == pytest.approx(
            ref_config.focal_spacing_m * 1e6, rel=1e-12
        )

    @pytest.mark.level0
    def test_psf_fov(self, ref_config: PSFSamplingConfig) -> None:
        expected = ref_config.padded_npix * ref_config.focal_spacing_m
        assert ref_config.psf_fov_m == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_psf_fov_um(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.psf_fov_um == pytest.approx(
            ref_config.psf_fov_m * 1e6, rel=1e-12
        )

    @pytest.mark.level0
    def test_oversample_stored(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.psf_oversample == OVERSAMPLE

    @pytest.mark.level0
    def test_wavelength_stored(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.wavelength_m == WAVELENGTH_M

    @pytest.mark.level0
    def test_focal_length_stored(self, ref_config: PSFSamplingConfig) -> None:
        assert ref_config.focal_length_m == FOCAL_LENGTH_M


# ---------------------------------------------------------------------------
# compute_sampling — different wavelengths
# ---------------------------------------------------------------------------


class TestSamplingWavelengthDependence:
    @pytest.mark.level0
    def test_longer_wave_needs_larger_pad(self) -> None:
        """Longer λ → larger padded grid (to maintain target spacing)."""
        cfg_short = compute_sampling(
            wavelength_m=1.0e-6,
            focal_length_m=1.0,
            aperture_diameter_m=0.20,
            pixel_pitch_m=10e-6,
        )
        cfg_long = compute_sampling(
            wavelength_m=10.0e-6,
            focal_length_m=1.0,
            aperture_diameter_m=0.20,
            pixel_pitch_m=10e-6,
        )
        assert cfg_long.padded_npix >= cfg_short.padded_npix


# ---------------------------------------------------------------------------
# compute_sampling — input validation
# ---------------------------------------------------------------------------


class TestSamplingValidation:
    @pytest.mark.level0
    def test_zero_wavelength(self) -> None:
        with pytest.raises(ValueError, match="wavelength_m must be positive"):
            compute_sampling(0, 1.0, 0.1, 10e-6)

    @pytest.mark.level0
    def test_negative_focal_length(self) -> None:
        with pytest.raises(ValueError, match="focal_length_m must be positive"):
            compute_sampling(1e-6, -1.0, 0.1, 10e-6)

    @pytest.mark.level0
    def test_zero_aperture(self) -> None:
        with pytest.raises(ValueError, match="aperture_diameter_m must be positive"):
            compute_sampling(1e-6, 1.0, 0.0, 10e-6)

    @pytest.mark.level0
    def test_negative_pixel_pitch(self) -> None:
        with pytest.raises(ValueError, match="pixel_pitch_m must be positive"):
            compute_sampling(1e-6, 1.0, 0.1, -10e-6)

    @pytest.mark.level0
    def test_pupil_npix_too_small(self) -> None:
        with pytest.raises(ValueError, match="pupil_npix must be >= 4"):
            compute_sampling(1e-6, 1.0, 0.1, 10e-6, pupil_npix=2)

    @pytest.mark.level0
    def test_oversample_too_small(self) -> None:
        with pytest.raises(ValueError, match="psf_oversample must be >= 2"):
            compute_sampling(1e-6, 1.0, 0.1, 10e-6, psf_oversample=1)


# ---------------------------------------------------------------------------
# PSFSamplingConfig — immutability
# ---------------------------------------------------------------------------


class TestSamplingFrozen:
    @pytest.mark.level0
    def test_frozen(self, ref_config: PSFSamplingConfig) -> None:
        with pytest.raises(AttributeError):
            ref_config.pupil_npix = 256  # type: ignore[misc]
