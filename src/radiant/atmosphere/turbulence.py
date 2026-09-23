"""Atmospheric turbulence MTF (Kolmogorov long-exposure).

For long-exposure imaging through Kolmogorov turbulence, the MTF is:

    MTF_turb(f) = exp(-3.44 · (λ · f / r₀)^(5/3))

where r₀ is the Fried parameter (coherence diameter) and f is spatial
frequency in cycles per radian (angular) or cycles per metre (focal
plane, after converting via f_focal = f_angular / focal_length).

Which r₀ the chain uses is decided by :mod:`radiant.atmosphere.r0_resolution`:
``atmosphere.cn2_profile = "direct"`` takes ``atmosphere.r0_m`` as entered
(rescaled to the band centre when ``r0_reference_wavelength_um`` says what it
was quoted at), while ``"hufnagel_valley"`` and ``"tabulated"`` integrate a
Cn²(h) profile along the line of sight
(:mod:`radiant.atmosphere.r0_path`) — Gap 110, delivered. This module owns the
MTF and nothing else.

See RADIANT_Spatial_Complete.md §6 (step 8), §9 row 12, and the Theory
Manual's atmosphere chapter §4 for the r₀ resolution policy.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.atmosphere.errors import AtmosphereValidationError


def turbulence_mtf_1d(
    freq: npt.NDArray[np.float64],
    wavelength_m: float,
    r0_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the 1-D long-exposure Kolmogorov turbulence MTF.

    Parameters
    ----------
    freq:
        Spatial frequencies [cycles/rad] (angular frequency).
    wavelength_m:
        Operating wavelength [m].
    r0_m:
        Fried parameter [m]. Must be positive.

    Returns
    -------
    ndarray
        MTF = exp(-3.44 · (λ·f / r₀)^(5/3)).

    Raises
    ------
    ValueError
        If r0_m <= 0 or wavelength_m <= 0.
    """
    if r0_m <= 0.0:
        raise AtmosphereValidationError(f"r0_m must be positive, got {r0_m}")
    if wavelength_m <= 0.0:
        raise AtmosphereValidationError(f"wavelength_m must be positive, got {wavelength_m}")

    arg = wavelength_m * freq / r0_m
    return np.exp(-3.44 * np.abs(arg) ** (5.0 / 3.0))


def turbulence_mtf_focal(
    freq_focal: npt.NDArray[np.float64],
    wavelength_m: float,
    r0_m: float,
    focal_length_m: float,
) -> npt.NDArray[np.float64]:
    """Compute the turbulence MTF for focal-plane spatial frequencies.

    Converts focal-plane frequencies [cycles/m] to angular frequencies
    [cycles/rad] via f_angular = f_focal × focal_length, then applies
    the Kolmogorov formula.

    Parameters
    ----------
    freq_focal:
        Spatial frequencies in the focal plane [cycles/m].
    wavelength_m:
        Operating wavelength [m].
    r0_m:
        Fried parameter [m].
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    ndarray
        Turbulence MTF values.
    """
    if focal_length_m <= 0.0:
        raise AtmosphereValidationError(f"focal_length_m must be positive, got {focal_length_m}")
    freq_angular = freq_focal * focal_length_m
    return turbulence_mtf_1d(freq_angular, wavelength_m, r0_m)
