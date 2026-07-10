"""Platform, scan, and target motion smear MTF.

Uniform linear motion during integration produces a rect-function PSF
blur, yielding a sinc MTF:

    MTF_smear(f) = |sinc(π · f · smear_width)|

where ``smear_width = velocity × t_int`` is the motion extent on the
focal plane [m].

Three independent smear sources exist (see RADIANT_Spatial_Complete.md §7):
1. Platform along-track motion
2. Scan mechanism cross-track motion
3. Untracked target motion

Each produces its own sinc MTF along its respective axis.

See RADIANT_Spatial_Complete.md §6, §7.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.platform.errors import PlatformValidationError


def smear_mtf_1d(
    freq: npt.NDArray[np.float64],
    smear_width_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D smear MTF.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/m].
    smear_width_m:
        Linear smear extent on the focal plane [m].
        Must be non-negative.

    Returns
    -------
    ndarray
        |sinc(π · f · smear_width)| at each frequency.
        Returns all-ones if smear_width_m is zero.

    Raises
    ------
    ValueError
        If smear_width_m is negative.
    """
    if smear_width_m < 0.0:
        raise PlatformValidationError(f"smear_width_m must be non-negative, got {smear_width_m}")
    if smear_width_m == 0.0:
        return np.ones_like(freq)
    # np.sinc(x) = sin(πx)/(πx)
    return np.abs(np.sinc(freq * smear_width_m))


def smear_width_m(
    velocity_m_s: float,
    t_int_s: float,
    focal_length_m: float,
    altitude_m: float,
) -> float:
    """Compute the smear extent on the focal plane.

    For an object at range ``altitude_m`` (slant range approximation),
    the angular rate is ``velocity / altitude`` rad/s, and the focal-
    plane motion is ``angular_rate × focal_length × t_int``.

    Parameters
    ----------
    velocity_m_s:
        Platform (or target) velocity [m/s].
    t_int_s:
        Integration time [s].
    focal_length_m:
        Effective focal length [m].
    altitude_m:
        Platform altitude (or slant range) [m].

    Returns
    -------
    float
        Smear width on the focal plane [m].

    Raises
    ------
    ValueError
        If t_int_s < 0, focal_length_m <= 0, or altitude_m <= 0.
    """
    if t_int_s < 0.0:
        raise PlatformValidationError(f"t_int_s must be non-negative, got {t_int_s}")
    if focal_length_m <= 0.0:
        raise PlatformValidationError(f"focal_length_m must be positive, got {focal_length_m}")
    if altitude_m <= 0.0:
        raise PlatformValidationError(f"altitude_m must be positive, got {altitude_m}")

    angular_rate = abs(velocity_m_s) / altitude_m  # rad/s
    return angular_rate * focal_length_m * t_int_s


def smear_kernel_1d(
    npix: int,
    sample_spacing_m: float,
    smear_width_m: float,
) -> npt.NDArray[np.float64]:
    """Generate a 1-D rect smear kernel.

    Parameters
    ----------
    npix:
        Length of the kernel (must be odd).
    sample_spacing_m:
        Sample spacing [m].
    smear_width_m:
        Smear extent [m]. Must be non-negative.

    Returns
    -------
    ndarray of shape (npix,)
        Normalised rect kernel (sums to 1.0). Delta if smear is zero.

    Raises
    ------
    ValueError
        If npix is not positive odd, sample_spacing_m <= 0, or
        smear_width_m < 0.
    """
    if npix < 1 or npix % 2 == 0:
        raise PlatformValidationError(f"npix must be a positive odd integer, got {npix}")
    if sample_spacing_m <= 0.0:
        raise PlatformValidationError(f"sample_spacing_m must be positive, got {sample_spacing_m}")
    if smear_width_m < 0.0:
        raise PlatformValidationError(f"smear_width_m must be non-negative, got {smear_width_m}")

    c = npix // 2
    kernel = np.zeros(npix, dtype=np.float64)

    if smear_width_m == 0.0:
        kernel[c] = 1.0
        return kernel

    half_width = smear_width_m / 2.0
    x = (np.arange(npix) - c) * sample_spacing_m
    kernel = np.where(np.abs(x) <= half_width, 1.0, 0.0)

    total = kernel.sum()
    if total > 0.0:
        kernel /= total

    return kernel
