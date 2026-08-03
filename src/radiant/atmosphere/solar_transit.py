"""Direct-solar transmittance for a sunlit target below the terminator (GF-9).

One computation, one module (Rule 19): ``τ_sun(λ)`` for a target whose local
solar zenith exceeds π/2 — the sun is below the target's horizontal, but the
target is still above the Earth's shadow, so a direct beam does reach it.

Topology
--------
The beam does **not** descend a column from the top of the atmosphere; it
enters the atmosphere on the far side of the terminator, sinks to a tangent
point and climbs back out to the target.  Decomposed against that tangent
point the path is exactly two ascending arcs sharing one tangent radius
``r₀ = (R_E + h_tgt)·sin θ_s``
(:func:`radiant.atmosphere.solar_shadow.solar_tangent_radius_m`)::

    τ_sun = τ(tangent → h_atm_top)  ·  τ(tangent → h_tgt)
              \\_ incoming leg _/       \\_ outgoing leg _/

Both arcs are evaluated by
:func:`radiant.atmosphere.segment_grazing.grazing_segment_optical_depth`
(τ is reciprocal, ADR-0011 decision 3, so only the optical depth is needed and
the travel direction is irrelevant).  The two optical depths add before the
exponential, which keeps the product exact rather than a product of two
rounded exponentials.

Sub-tangent altitudes.  ``h_tan = r₀ − R_E`` may be anywhere from 0 (the
terminator itself) to just below ``h_tgt`` (a sun barely below the horizontal).
Both arcs therefore start at ``h_tan``: the outgoing arc runs ``h_tan →
h_tgt``, the incoming one ``h_tan → h_atm_top``.  When the sun is exactly on
the horizontal (``θ_s = π/2``) the tangent point *is* the target, the outgoing
arc has zero length, and the expression degenerates continuously to the single
grazing column ``h_tgt → h_atm_top``.

Provisional — no MODTRAN anchor in batch 1
------------------------------------------
The optical depths this module produces are the largest anywhere in RADIANT: a
tangent ray through the lower troposphere carries 30–70 air masses, so the
band-model fidelity questions that :mod:`radiant.atmosphere.level_arm`
documents for long horizontal paths appear here **magnified**.  Specifically:

* The simple model's transmittance is a pure exponential in the slant column.
  A correlated-k or band model saturates sub-exponentially, so at these
  columns the simple model under-predicts τ, badly, in any band with strong
  lines (MWIR water, CO₂).  The L-grid horizontal anchors already show
  model/MODTRAN falling to 0.01 at 100 km of 3-km-altitude 3–5 µm path; a
  tangent ray is optically longer still.
* Refraction is not modelled (ADR-0011 decision 5).  Near the terminator
  refraction bends the beam by ≈ 0.5°, which changes the tangent altitude by
  kilometres and therefore the column by a large factor.
* The exponential density profile is a poor description of the real
  stratosphere at the altitudes a shallow tangent ray samples.

Batch 1 of the owner-run MODTRAN matrix (ground-to-air ladder + horizontal
5×5 grid) contains **no** twilight deck, so nothing here is MODTRAN-anchored
yet.  Treat the value as an order-of-magnitude bound, not a radiometric
result; a twilight deck pair belongs in batch 2 alongside the refraction
on/off calibration.

Zero drift
----------
Reachable only for ``θ_s > π/2``, which the pre-Phase-2 schema bound
(``geometry.solar_zenith_rad ≤ 1.5707``) and
:class:`~radiant.atmosphere.protocol.AtmosphericGeometry` both rejected
outright.  No previously-expressible scene can reach this code.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.atmosphere.segment_grazing import grazing_segment_optical_depth
from radiant.atmosphere.segment_simple import DEFAULT_H_ATM_TOP_M
from radiant.atmosphere.segments import validate_wavelength_grid
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.solar_shadow import solar_tangent_radius_m, sunlit
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = ["twilight_solar_transmittance"]


def twilight_solar_transmittance(
    atmosphere: SimpleAtmosphere,
    wavelength_um: np.ndarray,
    h_tgt_m: float,
    theta_s_rad: float,
    *,
    h_atm_top_m: float = DEFAULT_H_ATM_TOP_M,
) -> np.ndarray:
    """Two-arm ``τ_sun(λ)`` for a sunlit target with ``θ_s > π/2``.

    Parameters
    ----------
    atmosphere:
        The configured :class:`~radiant.atmosphere.simple.SimpleAtmosphere`.
    wavelength_um:
        1-D strictly-ascending, strictly-positive chain wavelength grid [µm].
    h_tgt_m:
        Target altitude above MSL [m].
    theta_s_rad:
        Local solar zenith at the target [rad].  Must be ``> π/2`` — the
        above-horizon case is served by the backend's own ``tau_sun`` and is
        deliberately *not* rerouted here (zero drift).
    h_atm_top_m:
        Top of the modelled atmospheric column [m].

    Returns
    -------
    np.ndarray
        Direct-solar transmittance along the tangent transit, ∈ (0, 1].

    Raises
    ------
    ParameterBoundsError
        If ``theta_s_rad ≤ π/2`` (wrong topology — the caller should use the
        backend's own column), if the target is at or above ``h_atm_top_m``
        (no modelled air to traverse — the caller should use the vacuum
        identity ``τ_sun ≡ 1``), or if the target is in the Earth's shadow
        (no direct beam exists at all).
    """
    lam = validate_wavelength_grid(wavelength_um, "twilight_solar_transmittance")
    if not math.isfinite(theta_s_rad) or theta_s_rad <= math.pi / 2.0:
        raise ParameterBoundsError(
            what=(
                f"twilight_solar_transmittance: theta_s_rad = {theta_s_rad} rad is not "
                "greater than π/2"
            ),
            why=(
                "The two-arm tangent decomposition describes a beam that enters on the "
                "far side of the terminator.  For a sun above the local horizontal the "
                "solar path is an ordinary descending column, which the backend already "
                "computes; rerouting it here would perturb every existing daylight "
                "result (zero-drift requirement)."
            ),
            action=(
                "Call this only for theta_s_rad > π/2; use the backend's own tau_sun otherwise."
            ),
            context={"theta_s_rad": theta_s_rad},
        )
    if h_tgt_m >= h_atm_top_m:
        raise ParameterBoundsError(
            what=(
                f"twilight_solar_transmittance: h_tgt_m = {h_tgt_m} m is at or above "
                f"h_atm_top_m = {h_atm_top_m} m"
            ),
            why=(
                "A target above the modelled column sees the sun through vacuum in "
                "every direction that is not blocked by the Earth; the transit integral "
                "has nothing to integrate."
            ),
            action=(
                "Use the exo vacuum identity tau_sun ≡ 1 for an above-column target "
                "(after checking solar_shadow.sunlit for Earth occultation)."
            ),
            context={"h_tgt_m": h_tgt_m, "h_atm_top_m": h_atm_top_m},
        )
    if not sunlit(h_tgt_m, theta_s_rad):
        raise ParameterBoundsError(
            what=(
                f"twilight_solar_transmittance: the target at h = {h_tgt_m} m with "
                f"theta_s = {math.degrees(theta_s_rad):.4f}° is inside the Earth's shadow"
            ),
            why=(
                "A shadowed target has no direct beam, so there is no transmittance to "
                "compute; returning some small number would imply an illumination that "
                "does not exist (Rule 17)."
            ),
            action=(
                "Test solar_shadow.sunlit() first and drop the direct-solar term "
                "entirely when it is False."
            ),
            context={"h_tgt_m": h_tgt_m, "theta_s_rad": theta_s_rad},
        )

    r_0 = solar_tangent_radius_m(h_tgt_m, theta_s_rad)
    h_tan = r_0 - R_EARTH_M

    # Outgoing arc: tangent point → target.  Zero length when the sun sits
    # exactly on the horizontal (r_0 == R_E + h_tgt).
    od_out, _, _ = grazing_segment_optical_depth(atmosphere, lam, r_0, h_tan, h_tgt_m)
    # Incoming arc: tangent point → top of the modelled column.
    od_in, _, _ = grazing_segment_optical_depth(atmosphere, lam, r_0, h_tan, h_atm_top_m)

    return np.asarray(np.exp(-(od_out + od_in)), dtype=np.float64)
