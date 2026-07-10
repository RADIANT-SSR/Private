"""Top-of-atmosphere solar spectrum.

Provides the TOA solar spectral irradiance ``E_sun(λ)`` used by the
atmosphere and source stages. Lives in ``core`` because it is pure
physics with no sensor or chain knowledge.

The only model implemented today is ``"blackbody_5778"``: a 5778 K
blackbody radiance scaled to the total solar irradiance ``S_0 = 1361
W/m²`` at 1 AU. The scaling is applied as a flat multiplicative
correction, so the spectral *shape* is exactly that of a 5778 K Planck
curve while the band-integrated irradiance over the full spectrum
recovers ``S_0`` to machine precision. Real solar spectra deviate from
the blackbody shape at the few-percent level (Fraunhofer lines, UV/VIS
deficit); a future ``"astm_e490"`` model will swap in a tabulated
reference spectrum without breaking the API.

Physics
-------
The TOA spectral irradiance is related to the Planck radiance by the
solid angle subtended by the Sun at 1 AU::

    E_sun(λ) = π · B(λ, T_sun) · (R_sun / AU)² · k_scale

where ``k_scale`` is the small correction needed to make the integral
match the nominal ``S_0`` exactly, given that an ideal 5778 K blackbody
with the IAU nominal ``R_sun`` and ``AU`` yields ~1365 W/m² (close to
but not identical to the observed ``S_0 = 1361 W/m²``).

The ``π`` factor is the integral of ``cos θ`` over the hemisphere — it
converts the Planck radiance (``W/m²/sr/µm``) to a flux
(``W/m²/µm``) as seen by a flat receiver, under the small-angle
approximation that the Sun is an isotropic emitter and
``(R_sun/AU)² ≪ 1``.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import R_sun_m, S_solar_W_per_m2, au_m
from radiant.core.exceptions import CoreStateError, CoreValidationError

SolarModel = Literal["blackbody_5778"]

# Effective photospheric temperature [K] chosen so that a blackbody of
# this temperature integrated over the full Planck curve with the IAU
# nominal R_sun / AU gives an irradiance very close to 1361 W/m².
_T_SOLAR_EFFECTIVE_K: float = 5778.0

# Geometric dilution factor (R_sun / AU)² — dimensionless, ~2.18e-5.
# This is the solid-angle-like factor that turns photospheric radiance
# (W/m²/sr/µm evaluated at the Sun's surface) into the radiance
# received per steradian at 1 AU. Wrapped in a module-level constant so
# the calibration factor below is inspectable.
_GEOMETRIC_DILUTION: float = (R_sun_m / au_m) ** 2

# Internal cache for the integral calibration factor. Computed lazily
# on first call; independent of wavelength, model, and geometry.
_K_SCALE_CACHE: dict[str, float] = {}


def _compute_k_scale(model: SolarModel) -> float:
    """Return the multiplicative factor that makes ``∫ E_sun dλ = S_0``.

    Computed by integrating the uncalibrated Planck irradiance over a
    wide wavelength range (0.05–50 µm, 10 001 points) and dividing the
    nominal ``S_0`` by the result. Cached per model so the integral
    runs only once per process.
    """
    if model in _K_SCALE_CACHE:
        return _K_SCALE_CACHE[model]
    if model != "blackbody_5778":
        raise CoreValidationError(
            f"radiant.core.solar: unknown model '{model}'. Supported: 'blackbody_5778'."
        )

    lam = np.linspace(0.05, 50.0, 10_001)
    radiance = planck_spectral_radiance(lam, _T_SOLAR_EFFECTIVE_K)
    raw_irradiance = np.pi * radiance * _GEOMETRIC_DILUTION
    total = float(np.trapezoid(raw_irradiance, lam))
    if total <= 0.0:
        raise CoreStateError(
            "radiant.core.solar: calibration integral is non-positive. "
            "Check the solar model constants."
        )
    k_scale = S_solar_W_per_m2 / total
    _K_SCALE_CACHE[model] = k_scale
    return k_scale


def toa_solar_spectral_irradiance(
    wavelength_um: np.ndarray | float,
    model: SolarModel = "blackbody_5778",
) -> np.ndarray:
    """Top-of-atmosphere solar spectral irradiance ``E_sun(λ)`` [W/m²/µm].

    Parameters
    ----------
    wavelength_um:
        Wavelength(s) in µm. Scalar or 1-D array. All values must be
        strictly positive.
    model:
        Solar spectrum model. Currently only ``"blackbody_5778"``.
        Future work will add ``"astm_e490"`` (tabulated reference).

    Returns
    -------
    numpy.ndarray
        Spectral irradiance at 1 AU, same shape as ``wavelength_um``
        (1-D, even for scalar input), in W/m²/µm. Integrating over the
        full spectrum recovers ``S_0 = 1361 W/m²`` to within ~1e-6.

    Notes
    -----
    This is the *spectral irradiance*, not the radiance. To get the
    equivalent Lambertian radiance (used by single-scatter path-radiance
    formulas), divide by ``π``::

        L_sun(λ) = E_sun(λ) / π   [W/m²/sr/µm]
    """
    if model != "blackbody_5778":
        raise CoreValidationError(
            f"toa_solar_spectral_irradiance: unknown model '{model}'. Supported: 'blackbody_5778'."
        )
    lam = np.atleast_1d(np.asarray(wavelength_um, dtype=np.float64))
    radiance = planck_spectral_radiance(lam, _T_SOLAR_EFFECTIVE_K)
    k_scale = _compute_k_scale(model)
    return np.asarray(
        np.pi * radiance * _GEOMETRIC_DILUTION * k_scale,
        dtype=np.float64,
    )


def toa_solar_equivalent_radiance(
    wavelength_um: np.ndarray | float,
    model: SolarModel = "blackbody_5778",
) -> np.ndarray:
    """Equivalent Lambertian solar radiance ``E_sun(λ) / π`` [W/m²/sr/µm].

    Convenience wrapper for single-scatter path-radiance calculations
    that expect a radiance rather than an irradiance.
    """
    return np.asarray(
        toa_solar_spectral_irradiance(wavelength_um, model) / np.pi,
        dtype=np.float64,
    )
