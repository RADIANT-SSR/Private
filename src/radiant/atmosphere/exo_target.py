"""Exo-altitude target handling — vacuum target leg over an atmospheric background.

Gap 95: a target at or above the top of the atmospheric column
(``los.h_tgt ≥ los.h_atm_top`` — a satellite, a post-burnout booster, a
100+ km hypersonic) has an exactly-known target→sensor leg:

    τ_up(λ)      ≡ 1              (no absorber above the column top)
    L_path_up(λ) ≡ 0 W/m²/sr/µm   (no emitting/scattering medium)
    τ_sun(λ)     ≡ 1              (the TOA→target sun leg is vacuum too)

while the *background* branch still needs the full ground→sensor column
(τ_full_up, L_path_full) — the scene behind the target is viewed through
the whole atmosphere and sets the background noise.

:func:`evaluate_with_exo_target` implements this once, model-agnostically:
it evaluates the wrapped backend at the **surface-target geometry**
(``h_tgt = 0``, same zenith/solar angles) — which every backend supports —
then overrides the target-leg quantities with the vacuum identities. The
full-column, E_TOA, and sky-irradiance terms are kept from the surface
evaluation. This is an identity substitution, not an approximation, so no
``UserWarning`` is emitted (Rule 17 concerns degradations); an INFO log
records the branch.

Known conflation (documented, pre-existing): ``AtmosphericQuantities``
carries a single E_sky pair that illuminates both the target and the
ground background. For an exo target the "sky" it sees is upwelling
Earthshine rather than the ground-level downwelling used here — right
order of magnitude, wrong spectrum. Zeroing instead would silently strip
the ground background's reflected-sky term, which is worse; the
target-side diffuse term is negligible against plume/self emission in the
scenarios this branch serves.

Direction (ADR-0011, Geometry-Flexibility Phase 1)
-------------------------------------------------
The surface re-evaluation above is a **down-looking** construction: it is
the column behind the target, kept because a down-looking LOS continues
past an exo target to the ground.  An up-looking or level LOS does not —
it continues into space.  Such a path is served only when its lower
endpoint is itself at or above ``h_atm_top`` (both endpoints outside the
column ⇒ the whole path, and its continuation, are vacuum: the LEO→GEO
quick win); an up-looking path whose lower endpoint is still inside the
column needs the Phase 2 direction-aware atmosphere and is refused
(Gaps 108/109) rather than served by the wrong column.

One computation, one module (Rule 19).
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere._uplooking_guard import reject_pending_uplooking_path
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance

logger = logging.getLogger(__name__)


def evaluate_with_exo_target(
    model: object,
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry | None,
    params: ParameterSet,
) -> AtmosphericQuantities:
    """Evaluate *model*, serving ``h_tgt ≥ h_atm_top`` with a vacuum target leg.

    For an endo-atmospheric target (``h_tgt < h_atm_top``) this is a
    transparent pass-through to ``model.evaluate``. For an exo-altitude
    target the backend is evaluated at the surface-target geometry and the
    target-leg quantities are replaced by the vacuum identities (module
    docstring). Works for every backend that satisfies the Atmosphere
    protocol — including single-column file imports that cannot otherwise
    serve an elevated target.
    """
    if los is None or los.h_tgt < los.h_atm_top:
        # None: at-aperture pass-through arms carry no LOS; the backend's own
        # handling (or refusal) of that case is unchanged.
        return model.evaluate(wavelength_um, los, params)  # type: ignore[attr-defined]

    # Direction matters for what lies BEHIND an exo-altitude target.
    # Down-looking (the historical case) the LOS continues past the target
    # through the whole column to the ground, which is why the surface
    # evaluation below is kept for the background branch.  Up-looking or
    # level, it continues into space — and an up-looking path whose lower
    # endpoint is still inside the column needs the Phase 2 direction-aware
    # atmosphere, so it is refused rather than served by the wrong column
    # (AtmosphereStage refuses it earlier; this covers direct calls).
    reject_pending_uplooking_path(los, where="evaluate_with_exo_target")
    if los.h_sensor is not None and los.h_sensor <= los.h_tgt:
        return _vacuum_quantities(wavelength_um, los)

    logger.info(
        "AtmosphereStage: h_tgt = %.0f m ≥ h_atm_top = %.0f m — exo-altitude "
        "target (Gap 95). Target→sensor leg is vacuum (tau_up = 1, "
        "L_path_up = 0, tau_sun = 1); ground→sensor full column retained "
        "for the background branch.",
        los.h_tgt,
        los.h_atm_top,
    )
    surface_los = dataclasses.replace(los, h_tgt=0.0)
    q0: AtmosphericQuantities = model.evaluate(  # type: ignore[attr-defined]
        wavelength_um,
        surface_los,
        params,
    )
    ones = np.ones_like(q0.wavelength_um, dtype=np.float64)
    zeros = np.zeros_like(q0.wavelength_um, dtype=np.float64)
    return AtmosphericQuantities(
        wavelength_um=q0.wavelength_um,
        tau_sun=ones,
        tau_up=ones.copy(),
        tau_full_up=q0.tau_full_up,
        E_TOA=q0.E_TOA,
        E_sky_scattered=q0.E_sky_scattered,
        E_sky_thermal=q0.E_sky_thermal,
        L_path_up=zeros,
        L_path_full=q0.L_path_full,
    )


def _vacuum_quantities(
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry,
) -> AtmosphericQuantities:
    """Exact vacuum bundle for a path with **both** endpoints above the column.

    Reached only for an up-looking or level LOS whose lower endpoint sits at
    or above ``h_atm_top`` (everything else was refused by
    :func:`radiant.atmosphere._uplooking_guard.reject_pending_uplooking_path`
    or takes the down-looking branch).  Nothing in the modelled column lies
    between the endpoints, *or* behind the target along the continuation of
    the LOS — the path terminates on deep space, not on the ground — so the
    full-column terms are the vacuum identities too, not the ground→sensor
    column the down-looking branch retains.  This is the space-to-space
    up-looking case (LEO→GEO, Geometry-Flexibility Phase 1 quick win).

    Backend-independent by construction: with no medium anywhere on the
    path, every backend's answer is this one.  ``E_TOA`` is the same core
    solar irradiance :class:`~radiant.atmosphere.exo.ExoAtmosphere` supplies,
    so a reflective target above the atmosphere still has its direct-solar
    term.
    """
    logger.info(
        "AtmosphereStage: up-looking/level path with both endpoints above "
        "h_atm_top = %.0f m (h_sensor = %.0f m, h_tgt = %.0f m, theta_o = "
        "%.4f rad) — vacuum path: tau ≡ 1, L_path ≡ 0, E_sky ≡ 0 for both "
        "the target and the background branch.",
        los.h_atm_top,
        los.h_sensor if los.h_sensor is not None else float("nan"),
        los.h_tgt,
        los.theta_o,
    )
    lam = np.asarray(wavelength_um, dtype=np.float64)
    ones = np.ones_like(lam)
    zeros = np.zeros_like(lam)
    return AtmosphericQuantities(
        wavelength_um=lam,
        tau_sun=ones,
        tau_up=ones.copy(),
        tau_full_up=ones.copy(),
        E_TOA=np.asarray(toa_solar_spectral_irradiance(lam), dtype=np.float64),
        E_sky_scattered=zeros,
        E_sky_thermal=zeros.copy(),
        L_path_up=zeros.copy(),
        L_path_full=zeros.copy(),
    )


__all__ = ["evaluate_with_exo_target"]
