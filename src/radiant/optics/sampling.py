"""PSF sampling configuration and FFT sizing helpers.

Implements the coupled sampling constraint from RADIANT_Spatial_Complete.md §4::

    Δx_focal = λ · f / (N · Δx_pupil)

where ``N`` is the padded FFT grid size. Only one of the three
sampling parameters (``psf_oversample``, ``psf_sample_spacing_um``,
``min_samples_per_psf_fwhm``) is independent — the rest are derived.

This module is pure geometry — no physics, no FFT execution.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PSFSamplingConfig:
    """Immutable PSF sampling configuration.

    Parameters
    ----------
    pupil_npix:
        Side length of the square pupil grid (before padding).
    padded_npix:
        Side length of the padded FFT grid (power of 2).
    psf_oversample:
        Samples per detector pixel in the focal-plane PSF grid.
    pupil_spacing_m:
        Physical spacing between pupil grid samples [m].
    focal_spacing_m:
        Physical spacing between focal-plane PSF samples [m].
    wavelength_m:
        Wavelength used for the sampling computation [m].
    focal_length_m:
        Focal length used for the sampling computation [m].
    """

    pupil_npix: int
    padded_npix: int
    psf_oversample: int
    pupil_spacing_m: float
    focal_spacing_m: float
    wavelength_m: float
    focal_length_m: float

    @property
    def focal_spacing_um(self) -> float:
        """Focal-plane sample spacing in µm."""
        return self.focal_spacing_m * 1e6

    @property
    def psf_fov_m(self) -> float:
        """Full field of view of the PSF grid [m]."""
        return self.padded_npix * self.focal_spacing_m

    @property
    def psf_fov_um(self) -> float:
        """Full field of view of the PSF grid [µm]."""
        return self.psf_fov_m * 1e6


def _next_power_of_2(n: int) -> int:
    """Return the smallest power of 2 >= n."""
    if n <= 0:
        return 1
    return 1 << (n - 1).bit_length()


def compute_sampling(
    wavelength_m: float,
    focal_length_m: float,
    aperture_diameter_m: float,
    pixel_pitch_m: float,
    pupil_npix: int = 128,
    psf_oversample: int = 8,
) -> PSFSamplingConfig:
    """Compute a consistent PSF sampling configuration.

    The pupil grid covers the aperture diameter, and the FFT pad size
    is chosen so that the focal-plane sample spacing equals
    ``pixel_pitch_m / psf_oversample``.

    Parameters
    ----------
    wavelength_m:
        Operating wavelength [m].
    focal_length_m:
        Effective focal length [m].
    aperture_diameter_m:
        Clear aperture diameter [m].
    pixel_pitch_m:
        Detector pixel pitch [m].
    pupil_npix:
        Side length of the pupil grid before padding. Default 128.
    psf_oversample:
        Samples per pixel in the focal plane. Default 8.

    Returns
    -------
    PSFSamplingConfig
        Immutable configuration with all derived quantities.

    Raises
    ------
    ValueError
        If any input is non-positive or psf_oversample < 2.
    """
    if wavelength_m <= 0:
        raise ValueError(f"wavelength_m must be positive, got {wavelength_m}")
    if focal_length_m <= 0:
        raise ValueError(f"focal_length_m must be positive, got {focal_length_m}")
    if aperture_diameter_m <= 0:
        raise ValueError(f"aperture_diameter_m must be positive, got {aperture_diameter_m}")
    if pixel_pitch_m <= 0:
        raise ValueError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    if pupil_npix < 4:
        raise ValueError(f"pupil_npix must be >= 4, got {pupil_npix}")
    if psf_oversample < 2:
        raise ValueError(f"psf_oversample must be >= 2 (Nyquist minimum), got {psf_oversample}")

    # Pupil sample spacing: aperture fills the grid.
    pupil_spacing_m = aperture_diameter_m / pupil_npix

    # Desired focal-plane spacing.
    focal_spacing_m = pixel_pitch_m / psf_oversample

    # FFT constraint: Δx_focal = λ·f / (N · Δx_pupil)
    # → N = λ·f / (Δx_focal · Δx_pupil)
    n_exact = (wavelength_m * focal_length_m) / (focal_spacing_m * pupil_spacing_m)
    n_padded = _next_power_of_2(max(int(math.ceil(n_exact)), pupil_npix))

    # Recompute focal spacing from the actual padded size for consistency.
    actual_focal_spacing_m = (wavelength_m * focal_length_m) / (n_padded * pupil_spacing_m)

    # Check sampling adequacy.
    airy_fwhm_m = 1.028 * wavelength_m * focal_length_m / aperture_diameter_m
    samples_across_fwhm = airy_fwhm_m / actual_focal_spacing_m
    if samples_across_fwhm < 2.0:
        logger.warning(
            "PSF undersampled: %.1f samples across Airy FWHM (minimum 2). "
            "Increase psf_oversample or pupil_npix.",
            samples_across_fwhm,
        )

    return PSFSamplingConfig(
        pupil_npix=pupil_npix,
        padded_npix=n_padded,
        psf_oversample=psf_oversample,
        pupil_spacing_m=pupil_spacing_m,
        focal_spacing_m=actual_focal_spacing_m,
        wavelength_m=wavelength_m,
        focal_length_m=focal_length_m,
    )
