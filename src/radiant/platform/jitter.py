"""Jitter MTF: random pointing errors during integration.

Jitter is modelled as a zero-mean Gaussian random process, producing
a Gaussian PSF blur with MTF:

    MTF_jitter(f) = exp(-2 π² σ² f²)

where σ is the jitter RMS on the focal plane [m].

Jitter may be isotropic (same σ in x and y) or anisotropic (different
σ_x and σ_y). In the anisotropic case, the 2-D MTF is separable:

    MTF(fx, fy) = exp(-2π²σ_x²fx²) · exp(-2π²σ_y²fy²)

See RADIANT_Spatial_Complete.md §7 and §10.2.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt


def jitter_sigma_focal_m(
    jitter_rms_rad: float,
    focal_length_m: float,
) -> float:
    """Convert angular jitter RMS to focal-plane σ [m].

    Parameters
    ----------
    jitter_rms_rad:
        Jitter RMS in radians.
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    float
        σ on the focal plane [m].
    """
    if jitter_rms_rad < 0.0:
        raise ValueError(f"jitter_rms_rad must be non-negative, got {jitter_rms_rad}")
    if focal_length_m <= 0.0:
        raise ValueError(f"focal_length_m must be positive, got {focal_length_m}")
    return jitter_rms_rad * focal_length_m


def jitter_mtf_1d(
    freq: npt.NDArray[np.float64],
    sigma_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D jitter MTF.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/m].
    sigma_m:
        Jitter RMS on the focal plane [m].

    Returns
    -------
    ndarray
        MTF = exp(-2π²σ²f²). Returns all-ones if sigma_m is zero.

    Raises
    ------
    ValueError
        If sigma_m is negative.
    """
    if sigma_m < 0.0:
        raise ValueError(f"sigma_m must be non-negative, got {sigma_m}")
    if sigma_m == 0.0:
        return np.ones_like(freq)
    return np.exp(-2.0 * math.pi**2 * sigma_m**2 * freq**2)


def jitter_mtf_2d(
    freq_x: npt.NDArray[np.float64],
    freq_y: npt.NDArray[np.float64],
    sigma_x_m: float,
    sigma_y_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 2-D anisotropic jitter MTF.

    Parameters
    ----------
    freq_x:
        Spatial frequencies in x [cycles/m].
    freq_y:
        Spatial frequencies in y [cycles/m].
    sigma_x_m:
        Jitter RMS in x on the focal plane [m].
    sigma_y_m:
        Jitter RMS in y on the focal plane [m].

    Returns
    -------
    ndarray
        2-D MTF (separable: MTF_x × MTF_y).
    """
    return jitter_mtf_1d(freq_x, sigma_x_m) * jitter_mtf_1d(freq_y, sigma_y_m)


def jitter_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    sigma_x_m: float,
    sigma_y_m: float,
) -> npt.NDArray[np.float64]:
    """Generate a 2-D Gaussian jitter kernel.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    sigma_x_m:
        Jitter RMS in x [m].
    sigma_y_m:
        Jitter RMS in y [m].

    Returns
    -------
    ndarray of shape (npix, npix)
        Normalised kernel (sums to 1.0). Delta if both σ are zero.
    """
    if npix < 1 or npix % 2 == 0:
        raise ValueError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise ValueError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if sigma_x_m < 0.0:
        raise ValueError(f"sigma_x_m must be non-negative, got {sigma_x_m}")
    if sigma_y_m < 0.0:
        raise ValueError(f"sigma_y_m must be non-negative, got {sigma_y_m}")

    c = npix // 2
    kernel = np.zeros((npix, npix), dtype=np.float64)

    if sigma_x_m == 0.0 and sigma_y_m == 0.0:
        kernel[c, c] = 1.0
        return kernel

    x = (np.arange(npix) - c) * sample_spacing_m
    xx, yy = np.meshgrid(x, x, indexing="xy")

    # Handle degenerate 1-D cases.
    sx2 = sigma_x_m**2 if sigma_x_m > 0.0 else 1e-30
    sy2 = sigma_y_m**2 if sigma_y_m > 0.0 else 1e-30

    kernel = np.exp(-(xx**2) / (2.0 * sx2) - yy**2 / (2.0 * sy2))

    # Zero out the degenerate dimension if σ = 0.
    if sigma_x_m == 0.0:
        kernel[xx != 0.0] = 0.0
    if sigma_y_m == 0.0:
        kernel[yy != 0.0] = 0.0

    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
