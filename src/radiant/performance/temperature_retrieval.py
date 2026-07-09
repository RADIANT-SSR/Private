"""Temperature retrieval and the emissivity/temperature Jacobian.

LWIR surface-temperature retrieval inverts a measured in-band radiance for
the surface temperature, given an *assumed* emissivity:

    L_meas = ε_true · B̄(T_true)         (forward, band-averaged Planck)
    T_ret  = B̄⁻¹( L_meas / ε_assumed )  (inverse, solved for T)

When the assumed emissivity is wrong, the retrieved temperature is biased.
The sensitivity of the band radiance to the two scene variables at an
operating point is the Jacobian:

    ∂L/∂ε = B̄(T)              (radiance is linear in emissivity)
    ∂L/∂T = ε · dB̄/dT         (Planck temperature derivative)

so a first-order emissivity-error → temperature-error map is
``ΔT ≈ −(∂L/∂ε / ∂L/∂T) · Δε = −(B̄ / (ε·dB̄/dT)) · Δε``, which the exact
inverse below refines. Band quantities are trapezoidal integrals of the
monochromatic Planck functions over the filter band. Gap for scenario 6.5.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq  # type: ignore[import-untyped]

from radiant.core.blackbody import planck_spectral_radiance, planck_spectral_radiance_dT
from radiant.core.exceptions import RadiantError

__all__ = [
    "TemperatureRetrievalError",
    "band_planck_radiance",
    "emissivity_jacobian",
    "retrieve_temperature_K",
    "temperature_jacobian",
]

FloatArray = npt.NDArray[np.float64]
_T_MIN_K = 1.0
_T_MAX_K = 5000.0


class TemperatureRetrievalError(RadiantError):
    """Raised for out-of-range retrieval inputs or a failed inversion."""


def band_planck_radiance(temperature_K: float, wavelength_um_band: npt.ArrayLike) -> float:
    """Band-integrated Planck radiance ``∫ B(λ,T) dλ`` [W/m²/sr] over the band."""
    wl = np.asarray(wavelength_um_band, dtype=np.float64)
    if wl.ndim != 1 or wl.size < 2:
        raise TemperatureRetrievalError("wavelength_um_band must be a 1-D array with ≥ 2 points.")
    if temperature_K <= 0.0:
        raise TemperatureRetrievalError(f"temperature_K must be positive, got {temperature_K}.")
    return float(np.trapezoid(planck_spectral_radiance(wl, temperature_K), wl))


def emissivity_jacobian(temperature_K: float, wavelength_um_band: npt.ArrayLike) -> float:
    """∂L/∂ε [W/m²/sr] = band-integrated ``B̄(T)`` (radiance is linear in ε)."""
    return band_planck_radiance(temperature_K, wavelength_um_band)


def temperature_jacobian(
    temperature_K: float, emissivity: float, wavelength_um_band: npt.ArrayLike
) -> float:
    """∂L/∂T [W/m²/sr/K] = ``ε · ∫ dB/dT dλ`` over the band."""
    wl = np.asarray(wavelength_um_band, dtype=np.float64)
    if not 0.0 <= emissivity <= 1.0:
        raise TemperatureRetrievalError(f"emissivity must be in [0, 1], got {emissivity}.")
    if temperature_K <= 0.0:
        raise TemperatureRetrievalError(f"temperature_K must be positive, got {temperature_K}.")
    return float(emissivity * np.trapezoid(planck_spectral_radiance_dT(wl, temperature_K), wl))


def retrieve_temperature_K(
    measured_band_radiance: float,
    assumed_emissivity: float,
    wavelength_um_band: npt.ArrayLike,
) -> float:
    """Retrieve the surface temperature [K] from a measured band radiance.

    Solves ``ε_assumed · B̄(T) = measured_band_radiance`` for T by Brent
    root-finding over [1, 5000] K. Raises if the emissivity is non-positive
    or the target radiance is unreachable in the bracket.
    """
    if not 0.0 < assumed_emissivity <= 1.0:
        raise TemperatureRetrievalError(
            f"assumed_emissivity must be in (0, 1], got {assumed_emissivity}."
        )
    if measured_band_radiance <= 0.0:
        raise TemperatureRetrievalError(
            f"measured_band_radiance must be positive, got {measured_band_radiance}."
        )
    target = measured_band_radiance / assumed_emissivity

    def _resid(t_k: float) -> float:
        return band_planck_radiance(t_k, wavelength_um_band) - target

    if _resid(_T_MIN_K) > 0.0 or _resid(_T_MAX_K) < 0.0:
        raise TemperatureRetrievalError(
            f"measured radiance / ε = {target:.4g} W/m²/sr is outside the "
            f"retrievable band radiance over [{_T_MIN_K}, {_T_MAX_K}] K."
        )
    return float(brentq(_resid, _T_MIN_K, _T_MAX_K, xtol=1e-6, rtol=1e-10))
