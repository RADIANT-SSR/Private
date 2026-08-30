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

Choice of ``T_eff`` (CU-321, 2026-08-02)
---------------------------------------
The caller supplies ``T_eff``, and since CU-321 it is a **spectrally
resolved, height-resolved** temperature from
:func:`radiant.atmosphere.emission_temperature.segment_emission_temperature_K`
— the temperature that makes this one-slab form reproduce the layered formal
solution of the segment's own (non-isothermal) air, evaluated once per escape
direction.  ``T_eff`` may therefore be a scalar or an array of the same shape
as the wavelength grid; both are accepted here.

Until CU-321 the callers passed one scalar per segment — the CU-155 helper
``SimpleAtmosphere._downwelling_effective_temperature_K`` at the segment's
lower endpoint — which assumed the whole column emits at near-surface
temperature.  That is exact for a level arm and harmless for a few-km column,
but it over-stated the down-looking 3–5 µm path thermal by 2.0–2.4× on the
tall MODTRAN columns (O3/O4/O5) because the MWIR emission of a 10–100 km
column escapes from cold air aloft.  The CU-155 helper survives only for the
hemispheric ``E_sky_thermal`` flux, whose emission-height offset is calibrated
through that one closed form (its companion diffusivity exponent has been the
geometric ``sec 48.2°`` since CU-324, 2026-08-29).

Direction
---------
This module still returns one number per wavelength and knows nothing about
direction: the direction lives in ``T_eff``.  The two directional fields of a
:class:`~radiant.atmosphere.segments.SegmentQuantities` now call it twice,
with ``escape="upper"`` and ``escape="lower"`` respectively, so the
directional asymmetry of a tall column is carried rather than approximated
away.  For an isothermal (level) segment the two temperatures are identical
by construction, so a level arm keeps exactly one graybody temperature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.parameters import ParameterBoundsError

if TYPE_CHECKING:  # pragma: no cover - typing only; importing it would cycle
    from collections.abc import Mapping

    from radiant.atmosphere.simple import SimpleAtmosphere

__all__ = ["directional_segment_thermal", "segment_thermal_emission"]

#: Species keys every caller supplies slant optical depths under.
SPECIES_KEYS: tuple[str, ...] = ("mol", "aer", "h2o", "gas")


def segment_thermal_emission(
    wavelength_um: np.ndarray,
    tau: np.ndarray,
    t_eff_K: float | np.ndarray,
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
        Effective emission temperature of the segment [K], ``> 0``.  Either a
        scalar (one temperature for the whole spectrum) or an array of the
        same shape as ``wavelength_um`` — the height-resolved ``T_eff(λ)``
        of CU-321.

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
    t_eff = np.asarray(t_eff_K, dtype=np.float64)
    if t_eff.ndim not in (0, 1) or (t_eff.ndim == 1 and t_eff.shape != lam.shape):
        raise ParameterBoundsError(
            what=(
                f"segment_thermal_emission: t_eff_K shape {t_eff.shape} is neither a scalar "
                f"nor one temperature per wavelength (grid shape {lam.shape})"
            ),
            why=(
                "A height-resolved emission temperature is spectrally resolved on the same "
                "grid as the transmittance it multiplies (CU-321)."
            ),
            action="Pass a scalar T_eff, or evaluate T_eff(λ) on the chain wavelength grid.",
            context={"t_eff_shape": t_eff.shape, "lam_shape": lam.shape},
        )
    if not np.all(np.isfinite(t_eff)) or float(t_eff.min()) <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"segment_thermal_emission: t_eff_K = {t_eff_K} K is not a "
                "positive finite temperature"
            ),
            why="The Planck function is undefined for non-positive temperature.",
            action="Supply the segment's effective emission temperature in K (> 0).",
            context={
                "t_eff_K_min": float(np.nanmin(t_eff)),
                "t_eff_K_max": float(np.nanmax(t_eff)),
            },
        )

    emissivity = 1.0 - t
    radiance: np.ndarray = emissivity * planck_spectral_radiance(lam, t_eff)
    # ε ≥ 0 and B ≥ 0, so the product is non-negative by construction; the
    # maximum() only removes signed-zero / round-off dust at ε == 0.
    return np.asarray(np.maximum(radiance, 0.0), dtype=np.float64)


def directional_segment_thermal(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    tau: np.ndarray,
    *,
    h_low_m: float,
    h_high_m: float,
    species_od: Mapping[str, np.ndarray],
    provenance: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """``(L_toward_upper, L_toward_lower)`` for one segment [W/m²/sr/µm].

    The single place the CU-321 height-resolved emission temperature is turned
    into the two directional thermal products, so every evaluator — column,
    grazing arc, level arm, level whole path, and the down-looking
    ``SimpleAtmosphere.evaluate`` term — uses the identical model.

    Parameters
    ----------
    atmosphere:
        Supplies ``_segment_emission_temperature_K`` and hence the
        temperature profile and the species scale heights.
    wavelength_um, tau:
        The segment's wavelength grid [µm] and its transmittance, as handed to
        :func:`segment_thermal_emission`.
    h_low_m, h_high_m:
        Segment endpoint altitudes [m].  ``h_low_m == h_high_m`` is the level
        (isothermal) case: both directions then carry the identical radiance.
    species_od:
        Slant optical depth per species over the whole segment, keyed by
        :data:`SPECIES_KEYS`.  Their sum is the segment's optical depth; this
        routine only asks *where in altitude* it sits.
    provenance:
        Optional dict to record the two directional ``T_eff`` ranges into.

    Raises
    ------
    ParameterBoundsError
        If a species key is missing (the four-species split is the contract).
    """
    missing = [key for key in SPECIES_KEYS if key not in species_od]
    if missing:
        raise ParameterBoundsError(
            what=f"directional_segment_thermal: species_od is missing {missing}",
            why=(
                "The emission weighting places each species' opacity on its own "
                "profile; a missing species would be silently unplaced (Rule 17)."
            ),
            action=f"Supply a slant optical depth for each of {list(SPECIES_KEYS)}.",
            context={"missing": missing, "supplied": sorted(species_od)},
        )

    lam = np.asarray(wavelength_um, dtype=np.float64)
    products: list[np.ndarray] = []
    for escape, label in (("upper", "toward_upper"), ("lower", "toward_lower")):
        t_eff = atmosphere._segment_emission_temperature_K(
            lam,
            h_low_m=h_low_m,
            h_high_m=h_high_m,
            od_slant_mol=np.asarray(species_od["mol"], dtype=np.float64),
            od_slant_aer=np.asarray(species_od["aer"], dtype=np.float64),
            od_slant_h2o=np.asarray(species_od["h2o"], dtype=np.float64),
            od_slant_gas=np.asarray(species_od["gas"], dtype=np.float64),
            escape=escape,
        )
        if provenance is not None:
            provenance[f"t_eff_{label}_K_min"] = float(np.min(t_eff))
            provenance[f"t_eff_{label}_K_max"] = float(np.max(t_eff))
        products.append(segment_thermal_emission(lam, tau, t_eff))
    return products[0], products[1]
