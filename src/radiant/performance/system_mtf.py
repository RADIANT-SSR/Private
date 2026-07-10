"""System MTF and Nyquist reporting.

Extracts system-level MTF metrics from the EffectivePSF:
- MTF at Nyquist frequency
- MTF at half-Nyquist
- Nyquist frequency for the detector

See RADIANT_Metrics.md and RADIANT_Spatial_Complete.md §9.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.performance.errors import PerformanceValidationError


def nyquist_freq(pixel_pitch_m: float) -> float:
    """Nyquist frequency for the detector [cycles/m].

    f_Nyquist = 1 / (2 × pixel_pitch).

    Parameters
    ----------
    pixel_pitch_m:
        Detector pixel pitch [m].

    Returns
    -------
    float
        Nyquist frequency [cycles/m].
    """
    if pixel_pitch_m <= 0.0:
        raise PerformanceValidationError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    return 1.0 / (2.0 * pixel_pitch_m)


def mtf_at_freq(
    freq_target: float,
    freq_array: npt.NDArray[np.float64],
    mtf_array: npt.NDArray[np.float64],
) -> float:
    """Interpolate MTF at a specific frequency.

    Parameters
    ----------
    freq_target:
        Target frequency [cycles/m].
    freq_array:
        Frequency values from mtf_1d().
    mtf_array:
        Corresponding MTF values.

    Returns
    -------
    float
        Interpolated MTF at freq_target.
    """
    return float(np.interp(freq_target, freq_array, mtf_array))


def mtf_at_nyquist(
    freq_array: npt.NDArray[np.float64],
    mtf_array: npt.NDArray[np.float64],
    pixel_pitch_m: float,
) -> float:
    """MTF at the Nyquist frequency.

    Parameters
    ----------
    freq_array:
        Frequency values from mtf_1d().
    mtf_array:
        Corresponding MTF values.
    pixel_pitch_m:
        Detector pixel pitch [m].

    Returns
    -------
    float
        MTF at Nyquist.
    """
    f_ny = nyquist_freq(pixel_pitch_m)
    return mtf_at_freq(f_ny, freq_array, mtf_array)


def mtf_at_half_nyquist(
    freq_array: npt.NDArray[np.float64],
    mtf_array: npt.NDArray[np.float64],
    pixel_pitch_m: float,
) -> float:
    """MTF at half the Nyquist frequency.

    Parameters
    ----------
    freq_array:
        Frequency values from mtf_1d().
    mtf_array:
        Corresponding MTF values.
    pixel_pitch_m:
        Detector pixel pitch [m].

    Returns
    -------
    float
        MTF at half-Nyquist.
    """
    f_half = nyquist_freq(pixel_pitch_m) / 2.0
    return mtf_at_freq(f_half, freq_array, mtf_array)
