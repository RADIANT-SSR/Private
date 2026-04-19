"""Pixel aperture kernel for PSF convolution.

The pixel integrates light over its active area, which is equivalent
to convolving the PSF with a 2-D rect function of dimensions
``(pitch_x × fill_factor, pitch_y × fill_factor)``.

This is a separable kernel: the 2-D result is the outer product of
two 1-D rect kernels.

See RADIANT_Spatial_Complete.md §6 step 1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def make_pixel_aperture_kernel_2d(
    npix: int,
    sample_spacing_m: float,
    pixel_pitch_x_m: float,
    pixel_pitch_y_m: float,
    fill_factor: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Build a 2-D pixel aperture rect kernel.

    Parameters
    ----------
    npix:
        Side length of the square kernel grid (must be odd).
    sample_spacing_m:
        Physical spacing between kernel samples [m].
    pixel_pitch_x_m:
        Pixel pitch along x [m].
    pixel_pitch_y_m:
        Pixel pitch along y [m].
    fill_factor:
        Photosensitive fraction of the pixel cell, in (0, 1].

    Returns
    -------
    ndarray of shape ``(npix, npix)``
        Normalised 2-D rect kernel (sums to 1.0).
    """
    kx = _rect_1d(npix, sample_spacing_m, pixel_pitch_x_m * fill_factor)
    ky = _rect_1d(npix, sample_spacing_m, pixel_pitch_y_m * fill_factor)

    kernel = np.outer(ky, kx)
    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel


def _rect_1d(
    npix: int,
    sample_spacing_m: float,
    width_m: float,
) -> npt.NDArray[np.float64]:
    """1-D rect function centred on the grid."""
    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m
    half = width_m / 2.0
    kernel = np.where(np.abs(x) <= half, 1.0, 0.0)
    total = kernel.sum()
    if total > 0.0:
        kernel /= total
    return kernel
