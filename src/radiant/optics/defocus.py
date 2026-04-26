"""Defocus PSF degradation — Gaussian blur approximation.

For small defocus (wave-optics regime, Strehl > 0.5), the defocus blur
is well approximated by an isotropic Gaussian with:

    σ_defocus = |δ| / (4 × f/# × √3)

where δ is the linear defocus [m] and the √3 comes from the RMS radius
of a uniformly illuminated circle (the geometric defocus spot).

The corresponding defocus MTF is:

    MTF_defocus(f) = exp(-2π² σ² f²)

Limitation: for large defocus (> several waves of Z4), the true defocus
PSF approaches a pill-box (uniform disk), not a Gaussian.  Use Zernike Z4
wavefront error for accurate large-defocus modelling.

See RADIANT docs/gaps.md Gap 29.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


def defocus_sigma_m(defocus_m: float, f_number: float) -> float:
    """Compute the defocus Gaussian blur sigma on the focal plane.

    Parameters
    ----------
    defocus_m:
        Linear defocus [m].  Sign is irrelevant (absolute value used).
    f_number:
        Working f-number of the optical system.

    Returns
    -------
    float
        Defocus blur sigma [m].
    """
    if f_number <= 0.0:
        raise ValueError(f"defocus_sigma_m: f_number must be positive, got {f_number}.")
    return abs(defocus_m) / (4.0 * f_number * math.sqrt(3.0))


def defocus_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    sigma_m: float,
) -> npt.NDArray[np.float64]:
    """Generate a 2-D isotropic Gaussian defocus kernel.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    sigma_m:
        Defocus blur sigma [m].

    Returns
    -------
    ndarray of shape (npix, npix)
        Normalised kernel (sums to 1.0).  Delta if sigma is zero.
    """
    if npix < 1 or npix % 2 == 0:
        raise ValueError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise ValueError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if sigma_m < 0.0:
        raise ValueError(f"sigma_m must be non-negative, got {sigma_m}")

    c = npix // 2
    kernel = np.zeros((npix, npix), dtype=np.float64)

    if sigma_m == 0.0:
        kernel[c, c] = 1.0
        return kernel

    x = (np.arange(npix) - c) * sample_spacing_m
    xx, yy = np.meshgrid(x, x, indexing="xy")

    s2 = sigma_m**2
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * s2))

    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
