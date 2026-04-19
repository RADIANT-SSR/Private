"""Charge diffusion kernel for PSF convolution.

Charge carriers generated in the detector bulk diffuse laterally
before being collected, blurring the image. The kernel is a 2-D
Gaussian with σ = L_d / √2 where L_d is the diffusion length.

See RADIANT_Spatial_Complete.md §6 step 2.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt


def make_diffusion_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    diffusion_length_m: float,
) -> npt.NDArray[np.float64]:
    """Build a 2-D Gaussian charge diffusion kernel.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    diffusion_length_m:
        Characteristic diffusion length L_d [m]. Must be ≥ 0.

    Returns
    -------
    ndarray of shape ``(npix, npix)``
        Normalised 2-D Gaussian kernel (sums to 1.0).
        Returns a delta function if diffusion_length_m is zero.
    """
    sigma = diffusion_length_m / math.sqrt(2.0)

    kernel = np.zeros((npix, npix), dtype=np.float64)
    if sigma == 0.0:
        c = npix // 2
        kernel[c, c] = 1.0
        return kernel

    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m
    xx, yy = np.meshgrid(x, x, indexing="xy")
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))

    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
