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

One computation, one module (Rule 19).
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet

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


__all__ = ["evaluate_with_exo_target"]
