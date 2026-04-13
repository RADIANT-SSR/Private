"""Solar irradiance for reflected-source computation.

Wraps ``radiant.core.solar.toa_solar_spectral_irradiance`` with
distance scaling for non-Earth scenarios and provides the spectral
irradiance at the target surface.

Per RADIANT_Source_Target_System.md §3.3, the solar irradiance at
target distance ``d`` is:

    E_sun(λ, d) = E_sun(λ, 1 AU) × (1 AU / d)²

See also ``radiant.core.solar`` for the underlying TOA model.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.constants import au_m
from radiant.core.solar import toa_solar_spectral_irradiance


def solar_irradiance_at_target(
    wavelength_um: npt.NDArray[np.float64],
    distance_au: float = 1.0,
    model: str = "blackbody_5778",
) -> npt.NDArray[np.float64]:
    """Solar spectral irradiance at target distance [W/m²/µm].

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm].
    distance_au:
        Distance from the Sun in AU. Must be positive.
        Default 1.0 (Earth orbit).
    model:
        Solar spectrum model passed to ``toa_solar_spectral_irradiance``.

    Returns
    -------
    ndarray
        Spectral irradiance [W/m²/µm] at the target distance.

    Raises
    ------
    ValueError
        If ``distance_au`` is not positive.
    """
    if distance_au <= 0.0:
        raise ValueError(
            f"distance_au must be positive, got {distance_au}"
        )
    e_sun_1au = toa_solar_spectral_irradiance(wavelength_um, model=model)
    scale = (1.0 / distance_au) ** 2
    return np.asarray(e_sun_1au * scale, dtype=np.float64)
