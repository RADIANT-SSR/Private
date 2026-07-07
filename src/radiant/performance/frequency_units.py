"""Spatial-frequency unit conversion — cycles/m, cycles/mm, cycles/mrad, cycles/pixel.

RADIANT stores PSF-path MTF curves in cycles/m on the focal plane
(``mtf_freq_x/y``) and the MTF-product grid in cycles/mrad
(``ChainState.spatial_freq_cycles_per_mrad``). Optical designers think
in cycles/mm (focal plane) or cycles/mrad (angular); detector engineers
in cycles/pixel. Conversions (hub unit: cycles/m):

    cycles/mm    = cycles/m × 1e-3
    cycles/mrad  = cycles/m × focal_length_m × 1e-3
    cycles/pixel = cycles/m × pixel_pitch_m

See RADIANT docs/tracking/gaps.md Gap 27.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError

FrequencyUnit = Literal["cy/m", "cy/mm", "cy/mrad", "cy/pixel"]

_UNITS: tuple[str, ...] = ("cy/m", "cy/mm", "cy/mrad", "cy/pixel")


class FrequencyUnitError(RadiantError):
    """Raised for unknown units or missing conversion context."""


def _to_cy_per_m_factor(
    unit: FrequencyUnit,
    pixel_pitch_m: float | None,
    focal_length_m: float | None,
) -> float:
    """Multiplier taking a value in *unit* to cycles/m."""
    if unit == "cy/m":
        return 1.0
    if unit == "cy/mm":
        return 1e3
    if unit == "cy/mrad":
        if focal_length_m is None or focal_length_m <= 0.0:
            raise FrequencyUnitError(
                "convert_spatial_frequency: converting cy/mrad requires a "
                "positive focal_length_m (angular ↔ focal-plane mapping is "
                f"through the focal length), got {focal_length_m}."
            )
        return 1.0 / (focal_length_m * 1e-3)
    if unit == "cy/pixel":
        if pixel_pitch_m is None or pixel_pitch_m <= 0.0:
            raise FrequencyUnitError(
                "convert_spatial_frequency: converting cy/pixel requires a "
                f"positive pixel_pitch_m, got {pixel_pitch_m}."
            )
        return 1.0 / pixel_pitch_m
    raise FrequencyUnitError(
        f"convert_spatial_frequency: unknown unit '{unit}'. Supported: {', '.join(_UNITS)}."
    )


def convert_spatial_frequency(
    freq: npt.NDArray[np.float64] | float,
    from_unit: FrequencyUnit,
    to_unit: FrequencyUnit,
    *,
    pixel_pitch_m: float | None = None,
    focal_length_m: float | None = None,
) -> npt.NDArray[np.float64] | float:
    """Convert spatial frequency between focal-plane, angular, and pixel units.

    Parameters
    ----------
    freq:
        Frequency value(s) in *from_unit*.
    from_unit, to_unit:
        One of ``"cy/m"``, ``"cy/mm"``, ``"cy/mrad"``, ``"cy/pixel"``.
    pixel_pitch_m:
        Detector pixel pitch [m]; required for ``cy/pixel``.
    focal_length_m:
        Effective focal length [m]; required for ``cy/mrad``.

    Returns
    -------
    Converted value(s), same shape as input.

    Raises
    ------
    FrequencyUnitError
        On unknown units or missing pitch / focal length context.
    """
    to_m = _to_cy_per_m_factor(from_unit, pixel_pitch_m, focal_length_m)
    from_m = _to_cy_per_m_factor(to_unit, pixel_pitch_m, focal_length_m)
    factor = to_m / from_m
    if isinstance(freq, np.ndarray):
        return freq * factor
    return float(freq) * factor
