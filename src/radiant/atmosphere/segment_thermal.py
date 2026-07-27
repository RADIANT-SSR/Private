"""Thermal (graybody) emission of one path segment.

One computation, one module (Rule 19): the emergent thermal radiance of a
path segment whose transmittance is already known.

Physics
-------
For a homogeneous, locally-thermodynamic-equilibrium slab of transmittance
``τ`` at temperature ``T_eff``, Kirchhoff's law fixes the emissivity from the
transmittance — it is never an independent input (Rule 5)::

    ε(λ) = 1 − τ(λ)
    L(λ) = ε(λ) · B(λ, T_eff) = (1 − τ(λ)) · B(λ, T_eff)

The two limits are exact: ``τ → 1`` (vacuum) gives ``L = 0`` exactly, and
``τ → 0`` (opaque) gives ``L = B(λ, T_eff)``, the blackbody ceiling.

Choice of ``T_eff``
-------------------
The caller supplies ``T_eff``.  Both segment evaluators in this package take
it from the CU-155 helper
``SimpleAtmosphere._downwelling_effective_temperature_K(h)`` evaluated at the
segment's **lower** endpoint (for a level arm, at the arm altitude, which is
its own lower endpoint).  That helper returns the fixed-lapse ICAO profile
temperature a calibrated emission-height offset ``z_em`` above ``h``, floored
at the tropopause: the emission escaping a segment of an exponential
atmosphere is dominated by the *densest* air it contains, which is at the
lower endpoint.  Using the same helper for the level arm keeps the arm the
continuous ``h_high → h_low`` limit of the column segment.

Direction
---------
This module returns one number per wavelength.  Both directional fields of a
:class:`~radiant.atmosphere.segments.SegmentQuantities` use it with the same
``T_eff``: for the exponential atmosphere the emission is lower-endpoint
dominated in *both* directions, and the residual directional asymmetry is the
escape attenuation, which is bounded by the same ``τ``.  Measured against the
real MODTRAN K-ladder (0 → 1/3/5/10/20 km vertical columns, midlat_summer),
the formal-solution ratio ``L_toward_upper / L_toward_lower`` is 1.00, 0.98,
0.96, 0.93, 0.91 in 8–12 µm and 0.99, 0.95, 0.91, 0.84, 0.77 in 3–5 µm — i.e.
the one-temperature graybody over-states the upward product by at most ~9 %
(LWIR) / ~23 % (MWIR) at a 20 km column, and by under 2 % for the few-km
segments that dominate ground-to-air and air-to-air work.  A
direction-dependent emission height is a follow-on (CU filed), not a silent
approximation.
"""

from __future__ import annotations

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.parameters import ParameterBoundsError

__all__ = ["segment_thermal_emission"]


def segment_thermal_emission(
    wavelength_um: np.ndarray,
    tau: np.ndarray,
    t_eff_K: float,
) -> np.ndarray:
    """Emergent graybody thermal radiance of a segment [W/m²/sr/µm].

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm], strictly positive.
    tau:
        Segment transmittance [dimensionless], ∈ [0, 1], same shape as
        ``wavelength_um``.
    t_eff_K:
        Effective emission temperature of the segment [K], ``> 0``.

    Returns
    -------
    np.ndarray
        ``(1 − τ) · B(λ, T_eff)`` [W/m²/sr/µm], non-negative, exactly zero
        wherever ``τ == 1``.

    Raises
    ------
    ParameterBoundsError
        On shape mismatch, ``τ`` outside [0, 1], or non-positive /
        non-finite temperature.  No NaN or inf is ever returned (Rule 17).
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    t = np.asarray(tau, dtype=np.float64)
    if t.shape != lam.shape:
        raise ParameterBoundsError(
            what=(
                f"segment_thermal_emission: tau shape {t.shape} does not match "
                f"wavelength_um shape {lam.shape}"
            ),
            why="Transmittance and wavelength are the same spectral vector.",
            action="Evaluate τ on the chain wavelength grid before calling.",
            context={"tau_shape": t.shape, "lam_shape": lam.shape},
        )
    if not np.all(np.isfinite(t)) or float(t.min()) < 0.0 or float(t.max()) > 1.0:
        raise ParameterBoundsError(
            what=(
                f"segment_thermal_emission: tau must be finite and in [0, 1] "
                f"(min={float(np.nanmin(t)):g}, max={float(np.nanmax(t)):g})"
            ),
            why=(
                "Emissivity is derived from transmittance (Kirchhoff, Rule 5); "
                "a τ outside [0, 1] yields an emissivity outside [0, 1]."
            ),
            action="Fix the optical-depth computation that produced τ.",
            context={"min": float(np.nanmin(t)), "max": float(np.nanmax(t))},
        )
    if not np.isfinite(t_eff_K) or t_eff_K <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"segment_thermal_emission: t_eff_K = {t_eff_K} K is not a "
                "positive finite temperature"
            ),
            why="The Planck function is undefined for non-positive temperature.",
            action="Supply the segment's effective emission temperature in K (> 0).",
            context={"t_eff_K": t_eff_K},
        )

    emissivity = 1.0 - t
    radiance: np.ndarray = emissivity * planck_spectral_radiance(lam, float(t_eff_K))
    # ε ≥ 0 and B ≥ 0, so the product is non-negative by construction; the
    # maximum() only removes signed-zero / round-off dust at ε == 0.
    return np.asarray(np.maximum(radiance, 0.0), dtype=np.float64)
