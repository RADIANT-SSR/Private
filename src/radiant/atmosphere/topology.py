"""Path-topology dispatch — the one entry point ``AtmosphereStage`` calls.

One computation, one module (Rule 19): decide which **path topology** a
line of sight describes and compose the atmospheric products for it.  Three
arms, keyed on the derived ``los.los_direction`` (ADR-0011 decision 1 — the
direction is derived from the altitude pair, never a user switch):

===========  ===========================================================
Direction    Product
===========  ===========================================================
``down``     The backend's own ``evaluate``, **unchanged and not
             rerouted** — every existing scene, byte-identical.  The
             exo-altitude target (``h_tgt ≥ h_atm_top``) is a segment
             composition over that same call; see below.
``up``       Segment composition — :mod:`radiant.atmosphere.uplooking_quantities`.
``level``    Same, with a constant-altitude arm as the observer leg.
===========  ===========================================================

Guardrail G4 — the exo carve-out is retired into the composition
----------------------------------------------------------------
Gap 95's ``evaluate_with_exo_target`` used to be a *wrapper*: a function that
called the backend at a substituted geometry and then overrode fields of the
result.  ADR-0011 guardrail G4 requires such carve-outs to become natural
cases of the segment product and the wrapper to be deleted in the same PR
(Rule 27).  It is expressed here as the composition it always was.

An exo-altitude target sits above the modelled column, so the path splits at
``h_atm_top`` into two segments:

* ``V`` — target → sensor.  Both endpoints are at or above ``h_atm_top``, so
  ``τ_V ≡ 1`` and ``L_V ≡ 0`` **exactly**, for every backend and with no
  model consulted.  (This is the same vacuum limit
  :func:`radiant.atmosphere.segment_simple.evaluate_column_segment` returns
  for a segment above the column top — stated as an identity here so the
  branch stays model-agnostic, which a simple-model evaluator could not be.)
* ``G`` — ground → target, the background continuation.  A down-looking LOS
  continues past the target through the whole column to the surface, so this
  segment is the backend's full column, obtained from a **surface-target**
  evaluation (``h_tgt = 0``, same angles) — the one geometry every backend
  supports, including a single-column tape7 import.

The ADR-0011 composition rules over the partition ``G ∪ V`` (lower segment
``G``, upper segment ``V``) then give the published fields directly::

    tau_full_up  = τ_G · τ_V              = τ_G            (τ_V ≡ 1)
    L_path_full  = L_G · τ_V + L_V        = L_G            (τ_V ≡ 1, L_V ≡ 0)
    tau_up       =        τ_V             = 1
    L_path_up    =        L_V             = 0
    tau_sun      = 1  (the TOA → target solar leg is vacuum too)

so the composition is *written* as a composition and *evaluated* by the
identities, with no arithmetic — which is why the fold is provably
bit-identical to the wrapper it replaces (`scripts/` differential proof;
see the task report).

Up-looking exo (both endpoints above the column) is the other natural case of
the same partition: there is no ``G`` at all, because the continuation
terminates on deep space rather than the ground, so every field collapses to
its vacuum identity.  That is the Phase-1 LEO→GEO quick win, unchanged.

Known conflation (documented, pre-existing, unchanged by the fold):
``AtmosphericQuantities`` carries a single ``E_sky`` pair that illuminates both
the target and the ground background.  For a down-looking exo target the "sky"
it sees is upwelling Earthshine rather than the ground-level downwelling used
here — right order of magnitude, wrong spectrum.  Zeroing it instead would
silently strip the ground background's reflected-sky term, which is worse.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.uplooking_quantities import (
    UplookingProducts,
    evaluate_uplooking_topology,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance

logger = logging.getLogger(__name__)

__all__ = ["TopologyProducts", "evaluate_path_topology"]


@dataclasses.dataclass(frozen=True)
class TopologyProducts:
    """What the topology dispatch hands back to ``AtmosphereStage``.

    Parameters
    ----------
    quantities:
        The eight-field :class:`AtmosphericQuantities` bundle the §6.1
        assembly consumes — the same contract for every topology (guardrail
        G1: no flat-bundle accretion).
    sky_source_radiance:
        Sky radiance along the LOS continuation at the target plane
        [W/m²/sr/µm], or ``None`` when the topology has no sky termination
        (every down-looking scene).  Consumed only by the ``SkyBackground``
        assembly arm.
    provenance:
        How this topology resolved, as a plain dict — the observer-leg
        description, the segment provenance, the GF-9 illumination note and
        the sky-continuation note, plus the geometry the dispatch keyed off.
        ``None`` for the topologies that carry no narrative (the down-looking
        arms and the vacuum path).  Published under
        ``stage_outputs["atmosphere"]["topology_provenance"]`` so an analyst
        can see from ``result.inspect()`` *why* τ_sun took its value —
        sunlit vs shadowed (Rule 16).  Before CU-240's sibling CU-266 this
        survived only in an INFO log record, which no result object carries.
    """

    quantities: AtmosphericQuantities
    sky_source_radiance: np.ndarray | None = None
    provenance: dict[str, Any] | None = None


def evaluate_path_topology(
    model: object,
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry | None,
    params: ParameterSet,
) -> TopologyProducts:
    """Evaluate *model* for whichever path topology *los* describes.

    ``los=None`` (the at-aperture pass-through arm carries no LOS) is a
    transparent pass-through to ``model.evaluate``; the backend's own
    handling of that case is unchanged.
    """
    if los is None:
        return TopologyProducts(
            quantities=model.evaluate(wavelength_um, los, params)  # type: ignore[attr-defined]
        )

    direction = los.los_direction

    if direction == "down":
        if los.h_tgt < los.h_atm_top:
            # Endo-atmospheric down-looking — the historical path, untouched.
            return TopologyProducts(
                quantities=model.evaluate(  # type: ignore[attr-defined]
                    wavelength_um, los, params
                )
            )
        return TopologyProducts(quantities=_down_looking_exo(model, wavelength_um, los, params))

    # Up-looking or level.
    if los.h_sensor is not None and los.h_sensor >= los.h_atm_top:
        # Both endpoints above the column: no G segment, no medium anywhere on
        # the path or its continuation.  Backend-independent by construction.
        #
        # CU-261: publish an explicit zero sky rather than ``None``. Assembly
        # refuses a ``None`` sky because a silently-zero background would
        # understate the photon term and inflate SNR (Rule 17) — but that guard
        # is about an *unknown* sky. Here the sky is known: there is no medium
        # anywhere along the LOS continuation, so its radiance is exactly zero.
        # Handing that zero over is a computed result, not a default, and it lets
        # a legitimate vacuum scene whose termination rule selects SkyBackground
        # run instead of raising.
        return TopologyProducts(
            quantities=_vacuum_quantities(wavelength_um, los),
            sky_source_radiance=np.zeros_like(
                np.asarray(wavelength_um, dtype=np.float64), dtype=np.float64
            ),
        )

    products: UplookingProducts = evaluate_uplooking_topology(model, wavelength_um, los, params)
    return TopologyProducts(
        quantities=products.quantities,
        sky_source_radiance=products.sky_source_radiance,
        provenance=products.provenance,
    )


# ---------------------------------------------------------------------------
# Down-looking segment compositions
# ---------------------------------------------------------------------------


def _down_looking_exo(
    model: object,
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry,
    params: ParameterSet,
) -> AtmosphericQuantities:
    """``G ∪ V`` composition for a down-looking exo-altitude target (Gap 95).

    See the module docstring for the partition and the identities that
    collapse it.  ``V`` contributes no arithmetic (``τ_V ≡ 1``, ``L_V ≡ 0``),
    so the composed fields are exactly ``G``'s — which is what makes this
    bit-identical to the pre-fold wrapper.
    """
    logger.info(
        "AtmosphereStage: h_tgt = %.0f m ≥ h_atm_top = %.0f m — exo-altitude "
        "target (Gap 95). Path composes as [ground→target column G] ∪ [vacuum "
        "target→sensor segment V]: tau_up = 1, L_path_up = 0, tau_sun = 1; the "
        "full ground→sensor column is G, retained for the background branch.",
        los.h_tgt,
        los.h_atm_top,
    )
    # Segment G: the backend's own full column, evaluated at the surface-target
    # geometry that every backend supports.
    surface_los = dataclasses.replace(los, h_tgt=0.0)
    g: AtmosphericQuantities = model.evaluate(  # type: ignore[attr-defined]
        wavelength_um,
        surface_los,
        params,
    )
    # Segment V: vacuum identities, model-independent.
    ones = np.ones_like(g.wavelength_um, dtype=np.float64)
    zeros = np.zeros_like(g.wavelength_um, dtype=np.float64)
    return AtmosphericQuantities(
        wavelength_um=g.wavelength_um,
        tau_sun=ones,  # TOA → target solar leg is vacuum
        tau_up=ones.copy(),  # τ_V
        tau_full_up=g.tau_full_up,  # τ_G · τ_V  with τ_V ≡ 1
        E_TOA=g.E_TOA,
        E_sky_scattered=g.E_sky_scattered,
        E_sky_thermal=g.E_sky_thermal,
        L_path_up=zeros,  # L_V
        L_path_full=g.L_path_full,  # L_G · τ_V + L_V  with τ_V ≡ 1, L_V ≡ 0
    )


def _vacuum_quantities(
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry,
) -> AtmosphericQuantities:
    """Exact vacuum bundle for a path with **both** endpoints above the column.

    Reached only for an up-looking or level LOS whose lower endpoint sits at
    or above ``h_atm_top``.  Nothing in the modelled column lies between the
    endpoints, *or* behind the target along the continuation — the path
    terminates on deep space, not on the ground — so the full-column terms are
    the vacuum identities too, not the ground→sensor column the down-looking
    branch retains.  This is the space-to-space up-looking case (LEO→GEO,
    Geometry-Flexibility Phase 1 quick win).

    Backend-independent by construction: with no medium anywhere on the path,
    every backend's answer is this one.  ``E_TOA`` is the same core solar
    irradiance :class:`~radiant.atmosphere.exo.ExoAtmosphere` supplies, so a
    reflective target above the atmosphere still has its direct-solar term.
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
