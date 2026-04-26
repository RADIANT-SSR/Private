"""Band-integrated Planck inversion: recover ``T_equiv`` from ``L_band``.

Given a band ``[λ_lo, λ_hi]`` in µm and an in-band integrated radiance
``L_band`` in W/m²/sr (already integrated ``∫B(λ,T) dλ`` over the band),
find the temperature ``T_equiv`` such that
``∫_{λ_lo}^{λ_hi} B(λ, T_equiv) dλ == L_band``.

This is the forward-compatible inversion harness required by the S12
spec.  Step 2.2 uses it only for *round-trip parity tests* — the user
entry point at S12 currently supplies ``T_R`` directly (see
:mod:`source.converters.radiance_temperature`) so the inversion is not
yet wired through :mod:`source._inferrer`.

Rule 19 — this module owns exactly the band-radiance → temperature
inversion; the forward direction lives in :mod:`radiant.core.blackbody`.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from scipy.optimize import brentq

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.parameters import ParameterBoundsError

# Bracketing limits for the root find.  Below 1 K the band-integrated
# radiance is effectively machine zero for any reasonable band; above
# 10 000 K the converter would already have been rejected at schema
# bounds.  The bracket is wide enough to cover every physical RADIANT
# target without wasting iterations.
_T_BRACKET_LO_K: Final[float] = 1.0
_T_BRACKET_HI_K: Final[float] = 10_000.0

# Default quadrature density.  201 points across a band gives <1e-6
# relative error vs. a 10 000-point reference in the LWIR/MWIR; the
# caller can raise this if the band is wide or in the Wien regime.
_DEFAULT_N_QUAD: Final[int] = 201


def integrate_planck_over_band(
    temperature_K: float,
    band_um: tuple[float, float],
    *,
    n_quad: int = _DEFAULT_N_QUAD,
) -> float:
    """Return ``∫_{λ_lo}^{λ_hi} B(λ, T) dλ`` in W/m²/sr.

    Parameters
    ----------
    temperature_K:
        Absolute temperature [K].  Must be strictly positive.
    band_um:
        ``(λ_lo, λ_hi)`` in µm with ``λ_lo < λ_hi`` and both positive.
    n_quad:
        Number of trapezoid samples across the band.  Default 201.

    Returns
    -------
    float
        Integrated in-band radiance in W/m²/sr.
    """
    lo, hi = float(band_um[0]), float(band_um[1])
    lam = np.linspace(lo, hi, int(n_quad), dtype=np.float64)
    B = planck_spectral_radiance(lam, float(temperature_K))
    # trapz in W/m²/sr/µm · µm → W/m²/sr.
    return float(np.trapezoid(B, lam))


def invert_band_radiance_to_temperature(
    L_band_W_per_m2_per_sr: float,
    band_um: tuple[float, float],
    *,
    n_quad: int = _DEFAULT_N_QUAD,
    T_bracket_K: tuple[float, float] = (_T_BRACKET_LO_K, _T_BRACKET_HI_K),
    rtol: float = 1.0e-10,
) -> float:
    """Return ``T_equiv`` such that ``∫B(λ, T_equiv) dλ == L_band``.

    Parameters
    ----------
    L_band_W_per_m2_per_sr:
        In-band integrated radiance [W/m²/sr].  Must be ``> 0``.
    band_um:
        ``(λ_lo, λ_hi)`` with ``0 < λ_lo < λ_hi``.
    n_quad:
        Quadrature points per Planck integral.  Default 201.
    T_bracket_K:
        Temperature bracket for the root solver.  Default (1, 10 000) K.
    rtol:
        Relative tolerance for the root solver.  Default 1e-10.

    Returns
    -------
    float
        Temperature in K.

    Raises
    ------
    ParameterBoundsError
        If inputs are out of range or the target radiance lies outside
        the monotone-increasing image of the Planck band integral over
        ``T_bracket_K`` (e.g., radiance too high for 10 000 K).
    """
    _validate_band(band_um)
    if not np.isfinite(L_band_W_per_m2_per_sr):
        raise ParameterBoundsError(
            what=(f"invert_band_radiance: L_band = {L_band_W_per_m2_per_sr} is not finite"),
            why="Band-integrated radiance must be a real non-negative number.",
            action="Check the upstream integrator for NaN / inf inputs.",
            context={"L_band": L_band_W_per_m2_per_sr},
        )
    if L_band_W_per_m2_per_sr <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"invert_band_radiance: L_band = {L_band_W_per_m2_per_sr} W/m²/sr is non-positive"
            ),
            why="Planck's law maps T > 0 to L > 0; inversion undefined at L ≤ 0.",
            action=(
                "Supply a strictly positive in-band radiance, or emit a "
                "T1Thermal(T_t=0) directly if the target is dark."
            ),
            context={"L_band": L_band_W_per_m2_per_sr},
        )

    T_lo, T_hi = float(T_bracket_K[0]), float(T_bracket_K[1])
    L_lo = integrate_planck_over_band(T_lo, band_um, n_quad=n_quad)
    L_hi = integrate_planck_over_band(T_hi, band_um, n_quad=n_quad)

    if L_band_W_per_m2_per_sr < L_lo or L_band_W_per_m2_per_sr > L_hi:
        raise ParameterBoundsError(
            what=(
                f"invert_band_radiance: L_band = "
                f"{L_band_W_per_m2_per_sr:g} W/m²/sr lies outside the "
                f"[L({T_lo:g} K), L({T_hi:g} K)] = "
                f"[{L_lo:g}, {L_hi:g}] W/m²/sr bracket"
            ),
            why=(
                "The Planck band integral is strictly monotone in T; a "
                "target radiance outside the bracket has no root in "
                "T_bracket_K."
            ),
            action=("Widen T_bracket_K or verify the L_band units / band definition."),
            context={
                "L_band": L_band_W_per_m2_per_sr,
                "L_lo": L_lo,
                "L_hi": L_hi,
                "T_bracket_K": (T_lo, T_hi),
            },
        )

    def residual(T_K: float) -> float:
        return integrate_planck_over_band(T_K, band_um, n_quad=n_quad) - L_band_W_per_m2_per_sr

    return float(brentq(residual, T_lo, T_hi, rtol=rtol))


def _validate_band(band_um: tuple[float, float]) -> None:
    lo, hi = float(band_um[0]), float(band_um[1])
    if lo <= 0.0 or hi <= 0.0:
        raise ParameterBoundsError(
            what=(f"invert_band_radiance: band = ({lo}, {hi}) µm has non-positive edges"),
            why="Wavelengths must be strictly positive for Planck's law.",
            action="Supply band edges in µm with 0 < λ_lo < λ_hi.",
            context={"band_um": (lo, hi)},
        )
    if lo >= hi:
        raise ParameterBoundsError(
            what=(f"invert_band_radiance: band = ({lo}, {hi}) µm is inverted or degenerate"),
            why="Integration requires λ_lo < λ_hi (strict).",
            action="Swap band edges so λ_lo is the smaller wavelength.",
            context={"band_um": (lo, hi)},
        )


__all__ = [
    "integrate_planck_over_band",
    "invert_band_radiance_to_temperature",
]
