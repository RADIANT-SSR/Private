"""Kolmogorov turbulence MTF term for the MTF product path.

The long-exposure Kolmogorov turbulence MTF is:

    MTF(f) = exp(-3.44 * (lambda * f_angular / r0)^(5/3))

This module duplicates the formula from ``atmosphere/turbulence.py``
to avoid a cross-stage import (Rule 11). The formula is standard
Kolmogorov — see Fried (1966), Roggemann & Welsh Ch. 3.

See RADIANT_Spatial_Complete.md section 6 step 8, section 9 row 12.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def kolmogorov_mtf_1d(
    freq_m: npt.NDArray[np.float64],
    wavelength_m: float,
    r0_m: float,
    focal_length_m: float,
) -> npt.NDArray[np.float64]:
    """Compute 1-D Kolmogorov turbulence MTF.

    Parameters
    ----------
    freq_m:
        Spatial frequencies on the focal plane [cycles/m].
    wavelength_m:
        Operating wavelength [m].
    r0_m:
        Fried coherence diameter [m]. Must be positive.
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    ndarray
        MTF values, same shape as ``freq_m``.
    """
    # Convert focal-plane frequency to angular frequency [cycles/rad].
    f_angular = freq_m * focal_length_m
    arg = wavelength_m * f_angular / r0_m
    return np.exp(-3.44 * np.abs(arg) ** (5.0 / 3.0))
