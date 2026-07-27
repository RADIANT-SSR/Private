"""Where the line of sight ends *behind* the target — the Rule-B selector.

One computation, one module (Rule 19): follow the LOS **past** the target and
classify what it runs into.  That classification is the input to Rule B of
``docs/architecture/RADIANT_Use_Case_Matrix.md`` §3.2.5, which selects the
background descriptor:

===============================  ================================
Continuation terminates on       Background (Rule B)
===============================  ================================
Earth's surface                  ``B3`` — ``GroundBackground``
Space, through an atmospheric     ``B2`` — ``SkyBackground``
  column
A limb-crossing column            ``B4`` — declined for v1.x (raise)
===============================  ================================

Geometry
--------
At the target the direction *toward the sensor* has zenith ``θ_o``.  The
continuation — the ray leaving the target directly **away** from the sensor,
which is the same straight line extended — therefore leaves the target at
zenith ``π − θ_o``.  That single substitution is the whole computation; the
rest is the standard ray/sphere perigee test on a spherical Earth
(``R_E = constants.R_EARTH_M``, the one canonical Earth model, CU-097).

For a ray leaving radius ``r_t`` at zenith ``ζ_c``:

* ``ζ_c < π/2`` — the ray ascends monotonically.  It never returns, so it
  terminates on **space**; its perigee is the start point itself.
* ``ζ_c ≥ π/2`` — the ray descends to a perigee of radius
  ``r_p = r_t sin(ζ_c)`` and then ascends again.  It terminates on
  **earth** when ``r_p ≤ R_E`` and on the **limb** otherwise (it grazes
  through the atmosphere and exits the far side without touching down).

Direction consequence (ADR-0011).  A down-looking LOS (``θ_o < π/2``) has a
descending continuation — every one of today's scenes lands in the
``earth``/``limb`` branch.  An up-looking (``θ_o > π/2``) or level
(``θ_o = π/2 + φ/2``) LOS has an **ascending** continuation, so it always
terminates on space; that is why ``SkyBackground`` is the up/level default
and why the limb branch is unreachable from those topologies.

Zero drift
----------
This module computes; it never selects.  Nothing in the pre-existing
down-looking descriptor-selection path consults it (the down-looking default
is unchanged), so no existing scene can change behaviour because this file
exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, TypeAlias

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError

__all__ = ["LosTermination", "Terminus", "classify_los_termination"]

Terminus: TypeAlias = Literal["earth", "space", "limb"]


@dataclass(frozen=True)
class LosTermination:
    """Classification of the LOS continuation beyond the target.

    Parameters
    ----------
    terminus:
        ``"earth"``, ``"space"`` or ``"limb"`` — see the module docstring.
    continuation_zeta_rad:
        Zenith angle **at the target** of the continuation ray [rad],
        ``= π − θ_o``.  This is the lower-endpoint zenith of the sky column
        for an ascending continuation, i.e. exactly the key an
        ADR-0011 path segment wants.
    tangent_radius_m:
        Perigee radius of the **infinite line** through the continuation,
        measured from the Earth centre [m]: ``r_t · sin(ζ_c) = r_t · sin(θ_o)``
        (the two are equal because ``ζ_c = π − θ_o``).  One unambiguous
        definition for both branches.  For a *descending* continuation the
        perigee lies ahead of the target and is actually traversed; for an
        *ascending* one it lies **behind** the target, on the sensor side,
        and is not traversed — but it is still the correct parameterisation
        of the arc, and it is exactly the ``r₀`` that
        :func:`radiant.atmosphere.grazing_column.grazing_slant_column_km`
        consumes.
    tangent_altitude_m:
        ``tangent_radius_m − R_E`` [m].  Negative when the line would pass
        below the surface — i.e. the ray hits the Earth first.
    tangent_depression_m:
        How far the perigee sits below the target, ``h_tgt −
        tangent_altitude_m`` [m], ``≥ 0`` always.  This is the quantity the
        plan §8.3 interior-tangent guard thresholds are expressed in; it is
        only *meaningful* for a descending continuation, where the perigee is
        traversed.
    detail:
        Human-readable one-liner for error and warning text.
    """

    terminus: Terminus
    continuation_zeta_rad: float
    tangent_radius_m: float
    tangent_altitude_m: float
    tangent_depression_m: float
    detail: str

    @property
    def ascends(self) -> bool:
        """``True`` iff the continuation leaves the target going upward."""
        return self.continuation_zeta_rad < math.pi / 2.0


def classify_los_termination(los: LineOfSightGeometry) -> LosTermination:
    """Classify where *los* ends after passing the target.

    Pure classification — never warns, never selects a descriptor, and never
    consults anything but ``los.h_tgt`` and ``los.theta_o``.  Callers apply
    the verdict (``source._inferrer`` for the Rule-B default,
    ``atmosphere`` for the sky-column geometry).

    Raises
    ------
    ParameterBoundsError
        If ``h_tgt`` is negative or ``theta_o`` is outside ``[0, π]`` —
        both already enforced by :class:`LineOfSightGeometry`, so this is a
        defensive re-check for hand-built payloads (Rule 16).
    """
    h_tgt = float(los.h_tgt)
    theta_o = float(los.theta_o)
    if not math.isfinite(h_tgt) or h_tgt < 0.0:
        raise ParameterBoundsError(
            what=f"classify_los_termination: h_tgt = {h_tgt} m is not a finite altitude ≥ 0",
            why="The continuation ray starts at the target; its radius must be physical.",
            action="Set h_tgt ≥ 0 m on the LineOfSightGeometry.",
            context={"h_tgt": h_tgt},
        )
    if not math.isfinite(theta_o) or not (0.0 <= theta_o <= math.pi):
        raise ParameterBoundsError(
            what=f"classify_los_termination: theta_o = {theta_o} rad is outside [0, π]",
            why="Observer zenith at the target is a zenith angle (ADR-0011 closed domain).",
            action="Wrap theta_o into [0, π] rad.",
            context={"theta_o": theta_o},
        )

    r_t = R_EARTH_M + h_tgt
    zeta_c = math.pi - theta_o

    # Perigee of the infinite line, r_p = r_t sin(ζ_c) = r_t sin(θ_o).  sin is
    # well conditioned at π/2 (zero derivative), so no versine form is needed.
    r_p = r_t * math.sin(zeta_c)
    h_p = r_p - R_EARTH_M
    depression = h_tgt - h_p

    if zeta_c < math.pi / 2.0:
        # Ascending continuation: the perigee is behind the target, so the
        # traversed arc rises monotonically and terminates on space whatever
        # the perigee radius is.
        return LosTermination(
            terminus="space",
            continuation_zeta_rad=zeta_c,
            tangent_radius_m=r_p,
            tangent_altitude_m=h_p,
            tangent_depression_m=depression,
            detail=(
                f"continuation leaves the target ({h_tgt:.1f} m MSL) at zenith "
                f"{math.degrees(zeta_c):.4f}° and ascends monotonically to space "
                f"(line perigee {h_p:.1f} m MSL lies behind the target, untraversed)"
            ),
        )

    if r_p <= R_EARTH_M:
        return LosTermination(
            terminus="earth",
            continuation_zeta_rad=zeta_c,
            tangent_radius_m=r_p,
            tangent_altitude_m=h_p,
            tangent_depression_m=depression,
            detail=(
                f"continuation leaves the target ({h_tgt:.1f} m MSL) at zenith "
                f"{math.degrees(zeta_c):.4f}° and descends to the surface "
                f"(perigee {h_p:.1f} m MSL, i.e. below 0)"
            ),
        )

    return LosTermination(
        terminus="limb",
        continuation_zeta_rad=zeta_c,
        tangent_radius_m=r_p,
        tangent_altitude_m=h_p,
        tangent_depression_m=depression,
        detail=(
            f"continuation leaves the target ({h_tgt:.1f} m MSL) at zenith "
            f"{math.degrees(zeta_c):.4f}°, dips to a tangent altitude of "
            f"{h_p:.1f} m MSL ({depression:.1f} m below the target) and exits "
            "without an Earth intercept — a limb-crossing column"
        ),
    )
