"""Charge diffusion MTF for detector material.

Charge carriers generated in the detector bulk diffuse laterally before
being collected, blurring the image. For a uniform diffusion process,
the PSF is Gaussian and the MTF is:

    MTF_diffusion(f) = exp(-2 π² σ² f²)

where σ = L_d / √2 and L_d is the charge diffusion length [m].

See RADIANT_Detector_Complete.md §3.3 and RADIANT_Spatial_Complete.md §6.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.detector.errors import DetectorValidationError


def diffusion_sigma_m(diffusion_length_m: float) -> float:
    """Convert charge diffusion length to Gaussian σ [m].

    Parameters
    ----------
    diffusion_length_m:
        Characteristic diffusion length L_d [m].

    Returns
    -------
    float
        Gaussian sigma σ = L_d / √2 [m].

    Raises
    ------
    ValueError
        If diffusion_length_m is negative.
    """
    if diffusion_length_m < 0.0:
        raise DetectorValidationError(
            f"diffusion_length_m must be non-negative, got {diffusion_length_m}"
        )
    return diffusion_length_m / math.sqrt(2.0)


def diffusion_mtf_1d(
    freq: npt.NDArray[np.float64],
    diffusion_length_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D charge diffusion MTF.

    Parameters
    ----------
    freq:
        Spatial frequency array [cycles/m].
    diffusion_length_m:
        Characteristic diffusion length L_d [m].

    Returns
    -------
    ndarray
        MTF values at the given frequencies. Returns all-ones if
        diffusion_length_m is zero (no diffusion).

    Raises
    ------
    ValueError
        If diffusion_length_m is negative.
    """
    sigma = diffusion_sigma_m(diffusion_length_m)
    if sigma == 0.0:
        return np.ones_like(freq)
    return np.exp(-2.0 * math.pi**2 * sigma**2 * freq**2)


def diffusion_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    diffusion_length_m: float,
) -> npt.NDArray[np.float64]:
    """Generate a 2-D Gaussian charge diffusion kernel.

    The kernel is centred on the grid and normalised to unit volume
    (sums to 1.0). For zero diffusion, returns a delta function.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    diffusion_length_m:
        Characteristic diffusion length L_d [m].

    Returns
    -------
    ndarray of shape (npix, npix)
        Normalised 2-D Gaussian kernel.

    Raises
    ------
    ValueError
        If npix is not positive odd, or sample_spacing_m <= 0, or
        diffusion_length_m < 0.
    """
    if npix < 1 or npix % 2 == 0:
        raise DetectorValidationError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise DetectorValidationError(f"sample_spacing_m must be positive, got {sample_spacing_m}")

    sigma = diffusion_sigma_m(diffusion_length_m)

    kernel = np.zeros((npix, npix), dtype=np.float64)
    if sigma == 0.0:
        # Delta function at center.
        c = npix // 2
        kernel[c, c] = 1.0
        return kernel

    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m
    xx, yy = np.meshgrid(x, x, indexing="xy")
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))

    # Normalise to unit volume.
    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
