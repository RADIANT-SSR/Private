"""Planck spectral radiance and its temperature derivative.

Physics
-------
Planck's law for the spectral radiance of a blackbody, expressed as a
spectral density per unit wavelength:

    B(λ, T) = (2 h c² / λ⁵) · 1 / (exp(h c / (λ k_B T)) − 1)

With λ in meters this yields W/m²/sr/m. RADIANT's canonical spectral
density is W/m²/sr/µm, so the result is multiplied by ``1e-6`` — this
is the Jacobian ``dλ_m/dλ_µm`` of the change of spectral variable, not
a user-facing unit conversion. It is the single place in this module
that carries a 1e-6 factor and is accompanied by a dimensional audit
in the module docstring below.

Dimensional audit
-----------------
    hc/(λ·k_B·T)              → [J·m] / ([m]·[J/K]·[K]) = dimensionless   ✓
    2 h c² / λ⁵  (λ in m)     → [J·s]·[m²/s²]/[m⁵]     = W/m²/sr/m
                                (per-sr implicit for Lambertian emission)
    × 1e-6 m/µm               → W/m²/sr/µm                                 ✓

Numerical stability
-------------------
The denominator uses :func:`numpy.expm1` to avoid catastrophic loss of
precision when ``x = hc/(λ k_B T) → 0`` (Rayleigh–Jeans limit). In that
regime ``exp(x) − 1 ≈ x`` and a naive subtraction loses most of the
significant digits; ``expm1(x)`` preserves them.

For very large ``x`` (Wien limit, short wavelength or cold source),
``expm1(x)`` grows without bound but never actually overflows to
``+inf`` until ``x ≳ 709`` in float64 (which corresponds to e.g.
λ ≈ 2.0 µm at T = 10 K). Beyond that we return exactly zero — the
Wien tail is numerically indistinguishable from zero and no physics is
lost.

At ``T = 0`` the function returns exactly zero (zero radiance at all
wavelengths). Negative temperatures or non-positive wavelengths raise
``ValueError``.

References
----------
- NIST ITS-90 Radiance Temperature: the "second radiation constant"
  ``c₂ = hc/k_B = 14387.76877 µm·K`` (CODATA 2018).
- Siegel & Howell, *Thermal Radiation Heat Transfer*, 6th ed., §1.6.
- Wien displacement constant ``b = 2897.771955 µm·K``.
"""

from __future__ import annotations

import numpy as np

from radiant.core.constants import hc_over_kB, two_hc2
from radiant.core.exceptions import CoreValidationError

# ---------------------------------------------------------------------------
# Overflow threshold for exp(x) in float64.
# exp(709.782) ≈ 1.797e308, just under float64 max. We cut a little below
# that to keep expm1 well-behaved.
# ---------------------------------------------------------------------------
_X_OVERFLOW: float = 700.0


def planck_spectral_radiance(
    wavelength_um: np.ndarray | float,
    temperature_K: float,
) -> np.ndarray:
    """Planck spectral radiance ``B(λ, T)`` in W/m²/sr/µm.

    Parameters
    ----------
    wavelength_um:
        Wavelength(s) in µm. Scalar or 1-D array. All values must be
        strictly positive.
    temperature_K:
        Absolute temperature in kelvin. Must be ``≥ 0``. ``T = 0``
        returns exactly zero radiance.

    Returns
    -------
    numpy.ndarray
        Spectral radiance in W/m²/sr/µm, same shape as
        ``wavelength_um`` (1-D, even for scalar input).

    Raises
    ------
    ValueError
        If ``temperature_K < 0`` or any wavelength is ``≤ 0``.

    Notes
    -----
    Uses :func:`numpy.expm1` for numerical stability in the
    Rayleigh–Jeans regime. The Wien tail is truncated to zero for
    ``hc/(λ k_B T) > 700`` to prevent overflow — this is safely in the
    region where the true value is below float64 underflow anyway.
    """
    if temperature_K < 0.0:
        raise CoreValidationError(
            f"planck_spectral_radiance: temperature_K = {temperature_K} K is invalid. "
            "Planck's law requires non-negative absolute temperature. "
            "Set temperature_K ≥ 0 (use 0 for a zero-radiance source)."
        )

    lam_um = np.atleast_1d(np.asarray(wavelength_um, dtype=np.float64))
    if np.any(lam_um <= 0.0):
        bad = float(lam_um[lam_um <= 0.0][0])
        raise CoreValidationError(
            f"planck_spectral_radiance: wavelength_um contains a non-positive "
            f"value ({bad} µm). All wavelengths must be strictly positive."
        )

    # T = 0 K → zero radiance everywhere (limit of Planck as T → 0⁺).
    if temperature_K == 0.0:
        return np.zeros_like(lam_um)

    # Convert µm → m for the canonical formula.
    lam_m = lam_um * 1.0e-6

    # Dimensionless argument x = hc / (λ k_B T) = c₂ / (λ_µm · T)
    # (Using c₂ = hc/k_B in µm·K is equivalent and avoids a rounding step.)
    x = hc_over_kB / (lam_m * temperature_K)

    # Allocate output; fill Wien-tail points with zero.
    result = np.zeros_like(lam_um)
    safe = x < _X_OVERFLOW
    if not np.any(safe):
        return result

    x_safe = x[safe]
    lam_m_safe = lam_m[safe]

    # B in W/m²/sr/m  =  (2 h c² / λ_m⁵) / expm1(x)
    B_per_m = two_hc2 / (lam_m_safe**5 * np.expm1(x_safe))

    # Jacobian dλ_m / dλ_µm = 1e-6 → W/m²/sr/µm
    result[safe] = B_per_m * 1.0e-6
    return result


def planck_spectral_radiance_dT(
    wavelength_um: np.ndarray | float,
    temperature_K: float,
) -> np.ndarray:
    """Temperature derivative ``∂B/∂T`` in W/m²/sr/µm/K.

    Used by downstream NEΔT computations. Derivation:

        B      = A / (e^x − 1)           with  A = 2hc²/λ⁵,  x = hc/(λ k_B T)
        dx/dT  = −x / T
        dB/dT  = A · e^x / (e^x − 1)² · (x / T)
               = B · (x / T) · e^x / (e^x − 1)

    Parameters
    ----------
    wavelength_um:
        Wavelength(s) in µm. Strictly positive.
    temperature_K:
        Absolute temperature in kelvin. Must be strictly positive
        (the derivative is not defined at ``T = 0``).

    Returns
    -------
    numpy.ndarray
        ``∂B/∂T`` in W/m²/sr/µm/K, same shape as ``wavelength_um``.

    Raises
    ------
    ValueError
        If ``temperature_K ≤ 0`` or any wavelength is ``≤ 0``.
    """
    if temperature_K <= 0.0:
        raise CoreValidationError(
            f"planck_spectral_radiance_dT: temperature_K = {temperature_K} K is invalid. "
            "The derivative ∂B/∂T is not defined at T = 0. "
            "Set temperature_K > 0."
        )

    lam_um = np.atleast_1d(np.asarray(wavelength_um, dtype=np.float64))
    if np.any(lam_um <= 0.0):
        bad = float(lam_um[lam_um <= 0.0][0])
        raise CoreValidationError(
            f"planck_spectral_radiance_dT: wavelength_um contains a non-positive "
            f"value ({bad} µm). All wavelengths must be strictly positive."
        )

    lam_m = lam_um * 1.0e-6
    x = hc_over_kB / (lam_m * temperature_K)

    result = np.zeros_like(lam_um)
    safe = x < _X_OVERFLOW
    if not np.any(safe):
        return result

    x_safe = x[safe]
    lam_m_safe = lam_m[safe]

    em1 = np.expm1(x_safe)  # e^x − 1, stable near x = 0
    ex = em1 + 1.0  # e^x, exact given em1

    # B in W/m²/sr/m
    B_per_m = two_hc2 / (lam_m_safe**5 * em1)

    # dB/dT in W/m²/sr/m/K
    dBdT_per_m = B_per_m * (x_safe / temperature_K) * (ex / em1)

    # Jacobian to W/m²/sr/µm/K
    result[safe] = dBdT_per_m * 1.0e-6
    return result
