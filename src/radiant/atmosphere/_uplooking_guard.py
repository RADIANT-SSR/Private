"""Phase-2-pending rejection of up-looking / level atmospheric paths.

ADR-0011 makes up-looking (``theta_o > π/2``) and level geometry *legal to
express*: :class:`~radiant.core.los_geometry.LineOfSightGeometry` accepts
both endpoints and the closed ``[0, π]`` zenith domain.  The **atmosphere**,
however, is still direction-blind: every backend integrates the column
*above* the target out to the sensor, which is the target→sensor leg only
when the sensor is the upper endpoint.  The direction-aware path-segment
products (up-path radiance, the horizontal arm, sky backgrounds) arrive in
Phase 2 of ``docs/plans/Geometry_Flexibility_Plan.md`` (Gaps 108/109).

This module rejects the geometries that would otherwise be served by the
wrong column, **at stage entry**, so the user sees one actionable error
naming the pending capability instead of a downstream
``ZENITH_CEILING``/``looking-up configuration`` message raised from inside
whichever backend happened to be configured (Rule 15, Rule 17).

Admissible without Phase 2, and therefore *not* rejected here:

* every down-looking path (``h_sensor > h_tgt``) — all of today's scenes;
* an up-looking or level path whose **lower** endpoint is already at or
  above ``h_atm_top`` — both endpoints are outside the modelled column, so
  the leg is vacuum by construction (``τ ≡ 1``, ``L_path ≡ 0``).  This is
  the LEO→GEO quick win of Phase 1, served by
  :func:`radiant.atmosphere.exo_target.evaluate_with_exo_target`.

One computation, one module (Rule 19): classifying a LOS as
"needs Phase 2" is the only thing this module does.
"""

from __future__ import annotations

import math

from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError

__all__ = ["reject_pending_uplooking_path"]


def reject_pending_uplooking_path(los: LineOfSightGeometry | None, *, where: str) -> None:
    """Raise if *los* needs the Phase-2 direction-aware atmosphere.

    No-op for ``None`` (the at-aperture pass-through arm carries no LOS) and
    for a pre-ADR-0011 payload that does not carry ``h_sensor`` — such a
    payload cannot express an up-looking scene in the first place (its
    direction is read off ``theta_o`` alone and the backends' existing
    ``h_sensor < h_tgt`` guards still apply).

    Raises
    ------
    ParameterBoundsError
        When the sensor sits at or below the target (up-looking or level)
        **and** the path's lower endpoint is inside the modelled
        atmospheric column.
    """
    if los is None or los.h_sensor is None:
        return
    if los.h_sensor > los.h_tgt:
        return  # down-looking — the supported topology
    if los.h_sensor >= los.h_atm_top:
        return  # both endpoints above the column — vacuum leg, exactly served

    direction = los.los_direction
    raise ParameterBoundsError(
        what=(
            f"{where}: up-looking/level atmospheric path — sensor at "
            f"h_sensor = {los.h_sensor} m is {'level with' if direction == 'level' else 'below'} "
            f"the target at h_tgt = {los.h_tgt} m (theta_o = {los.theta_o} rad, "
            f"{math.degrees(los.theta_o):.3f}°), and the lower endpoint lies "
            f"inside the modelled column (h_atm_top = {los.h_atm_top} m)"
        ),
        why=(
            "The geometry itself is accepted (ADR-0011 — up-looking and level "
            "scenes are legal since Geometry-Flexibility Phase 1), but the "
            "direction-aware atmosphere arrives in Phase 2 (Gaps 108/109). "
            "Every backend today integrates the column ABOVE the target out "
            "to the sensor; for an up-looking or level path that column is "
            "not the target→sensor leg, so any number produced here would be "
            "silently wrong (Rule 17)."
        ),
        action=(
            "Today only vacuum (exo) up-looking paths run: raise the target "
            f"above h_atm_top = {los.h_atm_top} m with the sensor also at or "
            "above it (the space-to-space case), or use a down-looking "
            "geometry (sensor above the target) until Phase 2 lands."
        ),
        context={
            "h_sensor": los.h_sensor,
            "h_tgt": los.h_tgt,
            "h_atm_top": los.h_atm_top,
            "theta_o": los.theta_o,
            "los_direction": direction,
            "where": where,
        },
    )
