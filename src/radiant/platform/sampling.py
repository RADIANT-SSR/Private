"""Pixel aperture MTF (rectangular sampling function).

The detector pixel integrates light over its physical area, acting as a
spatial low-pass filter. For a rectangular pixel of width p and fill
factor FF, the MTF along one axis is:

    MTF_pixel(f) = |sinc(π · f · p · FF)|

where sinc(x) = sin(x)/x.

This is placed in the platform module because it represents how the
continuous image is sampled by the pixel geometry — a spatial/sampling
concern that feeds into the PSF cascade.

See RADIANT_Spatial_Complete.md §6 (step 1) and
RADIANT_Detector_Complete.md §3.3.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.platform.errors import PlatformValidationError


def pixel_aperture_mtf_1d(
    freq: npt.NDArray[np.float64],
    pixel_pitch_m: float,
    fill_factor: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D pixel aperture MTF.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/m].
    pixel_pitch_m:
        Pixel pitch along this axis [m].
    fill_factor:
        Fill factor in [0, 1]. Default 1.0 (100% fill).

    Returns
    -------
    ndarray
        |sinc(π · f · p · FF)| at each frequency.

    Raises
    ------
    ValueError
        If pixel_pitch_m <= 0 or fill_factor out of (0, 1].
    """
    if pixel_pitch_m <= 0.0:
        raise PlatformValidationError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    if not (0.0 < fill_factor <= 1.0):
        raise PlatformValidationError(f"fill_factor must be in (0, 1], got {fill_factor}")

    effective_width = pixel_pitch_m * fill_factor
    # np.sinc(x) = sin(πx)/(πx), so sinc(π·f·w) = np.sinc(f·w)
    return np.abs(np.sinc(freq * effective_width))


def pixel_aperture_mtf_2d(
    freq_x: npt.NDArray[np.float64],
    freq_y: npt.NDArray[np.float64],
    pixel_pitch_x_m: float,
    pixel_pitch_y_m: float,
    fill_factor: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Compute the 2-D pixel aperture MTF (separable).

    MTF(fx, fy) = |sinc(π·fx·px·FF)| · |sinc(π·fy·py·FF)|

    Parameters
    ----------
    freq_x:
        Spatial frequencies in x [cycles/m].
    freq_y:
        Spatial frequencies in y [cycles/m]. Same shape as freq_x.
    pixel_pitch_x_m:
        Pixel pitch in x [m].
    pixel_pitch_y_m:
        Pixel pitch in y [m].
    fill_factor:
        Fill factor in (0, 1]. Default 1.0.

    Returns
    -------
    ndarray
        2-D MTF values (same shape as freq_x).
    """
    mtf_x = pixel_aperture_mtf_1d(freq_x, pixel_pitch_x_m, fill_factor)
    mtf_y = pixel_aperture_mtf_1d(freq_y, pixel_pitch_y_m, fill_factor)
    return mtf_x * mtf_y


def pixel_aperture_kernel_1d(
    npix: int,
    sample_spacing_m: float,
    pixel_pitch_m: float,
    fill_factor: float = 1.0,
) -> npt.NDArray[np.float64]:
    """Generate a 1-D rectangular pixel aperture kernel.

    The kernel is a normalised rect function of width ``pixel_pitch_m *
    fill_factor``, sampled at ``sample_spacing_m``.

    Parameters
    ----------
    npix:
        Length of the kernel (must be odd).
    sample_spacing_m:
        Sample spacing [m].
    pixel_pitch_m:
        Pixel pitch [m].
    fill_factor:
        Fill factor in (0, 1].

    Returns
    -------
    ndarray of shape (npix,)
        Normalised 1-D rect kernel (sums to 1.0).
    """
    if npix < 1 or npix % 2 == 0:
        raise PlatformValidationError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise PlatformValidationError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if pixel_pitch_m <= 0.0:
        raise PlatformValidationError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    if not (0.0 < fill_factor <= 1.0):
        raise PlatformValidationError(f"fill_factor must be in (0, 1], got {fill_factor}")

    effective_width = pixel_pitch_m * fill_factor
    half_width = effective_width / 2.0

    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m

    # Rect function: 1 inside [-half_width, +half_width], 0 outside.
    kernel = np.where(np.abs(x) <= half_width, 1.0, 0.0)

    # Normalise.
    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
