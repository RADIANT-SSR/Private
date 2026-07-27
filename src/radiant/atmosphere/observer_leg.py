"""Decompose an up-looking / level LOS into its observer-leg path segment.

One computation, one module (Rule 19): turn a
:class:`~radiant.core.los_geometry.LineOfSightGeometry` whose sensor sits at
or below the target into the single ADR-0011 path segment that spans
target → sensor, together with the two bookkeeping facts the radiometry needs
about it — which of the segment's two directional radiance fields points at
the sensor, and what the sun's relative azimuth is *in the segment's own
frame*.

Nothing radiometric happens here.  The segment is evaluated by
:mod:`radiant.atmosphere.segment_simple` (column) or
:mod:`radiant.atmosphere.level_arm` (constant altitude); this module only
decides which one and with what arguments.

The two topologies
------------------
**Up-looking** (``h_sensor < h_tgt``) — a slant column whose **lower**
endpoint is the sensor (ADR-0011 decision 3).  Its lower-endpoint zenith is

.. math::  \\zeta_{low} = \\pi - \\eta

with ``η`` the interior angle at the sensor from
:func:`radiant.core.viewing_triangle.eta_from_theta_o` — measured there from
the local *nadir*, and obtuse on the up-looking branch, so ``π − η`` is the
ordinary zenith of the sensor→target look direction.  A vertical up-looking
path (``θ_o = π``) gives ``η = π`` and ``ζ_low = 0``: straight up, as it
must.

**Level** (``h_sensor == h_tgt``) — a constant-altitude arm whose length is
the *true chord* between the endpoints,
:func:`radiant.core.viewing_triangle.slant_range_from_theta_o_m`.  The column
machinery cannot express this path at all (its vertical extent is zero, and
its local zenith is π/2 everywhere, past the air-mass ceiling), which is why
:class:`~radiant.atmosphere.segments.LevelArmSpec` is a separate type.  The
chord dips below its endpoints by ``Δh ≈ L²/8R_E``; the Phase-1 horizon guard
in :class:`LineOfSightGeometry` has already bounded that sag to ≤ 2 km, and
:mod:`radiant.atmosphere.level_arm` documents the density error the resulting
constant-density assumption carries (3.4 % of water column at the clean-band
edge, ≈ 1.9× at the raise threshold).

Azimuth bookkeeping
-------------------
``LineOfSightGeometry.delta_phi`` is ``φ_s − φ_o`` with ``φ_o`` the azimuth of
the **target → sensor** direction, measured at the target.  A segment's
scattering angle is keyed to its **lower → upper** direction, so the two
frames agree or differ by π depending on the topology:

* level — lower → upper is (by this module's convention) target → sensor, the
  same sense as ``φ_o``, so ``Δφ_seg = delta_phi`` and the sensor sees the
  ``toward_upper`` field;
* up-looking — lower → upper is sensor → target, the *opposite* horizontal
  sense, so ``Δφ_seg = delta_phi − π`` (only its cosine is consumed, and
  ``cos(Δφ − π) = −cos Δφ``) and the sensor sees the ``toward_lower`` field.

Sanity check that pins the sign: a ground sensor looking straight up
(``θ_o = π``, ``ζ_low = 0``) at a target overhead, with the sun at zenith
(``θ_s = 0``).  Photons travel straight down; the light reaching the sensor
also travels straight down, so this is pure forward scatter, ``cos Θ = +1``.
The formula gives ``cos Θ_toward_upper = −cos θ_s = −1`` and hence
``cos Θ_toward_lower = +1``.  ✓

Zero drift
----------
Raises for a down-looking LOS: the down-looking topology keeps its existing
un-rerouted path, and routing it through here would be a behaviour change
this module exists to avoid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.atmosphere.segments import (
    ColumnSegmentSpec,
    LevelArmSpec,
    PathSegmentSpec,
    SegmentDirection,
)
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import eta_from_theta_o, slant_range_from_theta_o_m

__all__ = ["ObserverLeg", "observer_leg_from_los"]


@dataclass(frozen=True)
class ObserverLeg:
    """The target ↔ sensor path segment plus its directional bookkeeping.

    Parameters
    ----------
    spec:
        The :class:`~radiant.atmosphere.segments.ColumnSegmentSpec` (up) or
        :class:`~radiant.atmosphere.segments.LevelArmSpec` (level).
    toward_sensor:
        Which of the segment's two directional radiance products is the one
        that reaches the sensor — ``"toward_lower"`` for up-looking (the
        sensor is the lower endpoint), ``"toward_upper"`` for level.
    delta_phi_seg_rad:
        Sun-to-path relative azimuth expressed in the **segment's** frame
        [rad], ready to hand to the evaluator.  ``None`` on the input LOS
        maps to ``0.0`` — it is only consumed when a solar geometry exists.
    zeta_low_rad:
        Segment zenith at its lower endpoint [rad].  ``π/2`` by construction
        for a level arm.
    slant_range_m:
        True target↔sensor distance [m].
    detail:
        Human-readable one-liner for provenance and error text.
    """

    spec: PathSegmentSpec
    toward_sensor: SegmentDirection
    delta_phi_seg_rad: float
    zeta_low_rad: float
    slant_range_m: float
    detail: str


def observer_leg_from_los(los: LineOfSightGeometry) -> ObserverLeg:
    """Build the observer-leg segment for an up-looking or level *los*.

    Raises
    ------
    ParameterBoundsError
        If ``los.h_sensor`` is absent (a pre-ADR-0011 payload cannot express
        an up-looking scene — guardrail G2 forbids a params side-load), or if
        the LOS is down-looking (wrong module — the down-looking topology is
        served, unchanged, by the backend's own column).
    """
    if los.h_sensor is None:
        raise ParameterBoundsError(
            what=(
                "observer_leg_from_los: the LineOfSightGeometry does not carry the "
                f"sensor endpoint (h_sensor is None; h_tgt = {los.h_tgt} m, "
                f"theta_o = {los.theta_o} rad)"
            ),
            why=(
                "The observer leg is the segment between the two endpoints; without "
                "the sensor endpoint there is no segment.  Reading "
                "geometry.sensor_altitude_m from the ParameterSet instead is what "
                "guardrail G2 (plan §3.5) deletes — two live sources for one "
                "quantity."
            ),
            action=(
                "Run the chain through GeometryStage, or pass h_sensor explicitly on "
                "a hand-built LineOfSightGeometry."
            ),
            context={"h_tgt": los.h_tgt, "theta_o": los.theta_o},
        )

    h_sensor = float(los.h_sensor)
    h_tgt = float(los.h_tgt)
    delta_phi = 0.0 if los.delta_phi is None else float(los.delta_phi)

    if h_sensor > h_tgt:
        raise ParameterBoundsError(
            what=(
                f"observer_leg_from_los: the path is down-looking (h_sensor = "
                f"{h_sensor} m > h_tgt = {h_tgt} m)"
            ),
            why=(
                "Down-looking scenes keep their existing, un-rerouted backend column "
                "so that every golden baseline stays byte-identical (plan §3 "
                "principle 3).  The segment decomposition is additive and reachable "
                "only from the newly-legal up-looking / level topologies."
            ),
            action=(
                "Dispatch on los.los_direction and send 'down' to the backend's own evaluate path."
            ),
            context={"h_sensor": h_sensor, "h_tgt": h_tgt, "theta_o": los.theta_o},
        )

    slant_m = slant_range_from_theta_o_m(los.theta_o, h_sensor, h_tgt)

    if h_sensor == h_tgt:
        return ObserverLeg(
            spec=LevelArmSpec(altitude_m=h_sensor, length_m=slant_m),
            toward_sensor="toward_upper",
            delta_phi_seg_rad=delta_phi,
            zeta_low_rad=math.pi / 2.0,
            slant_range_m=slant_m,
            detail=(
                f"level constant-altitude arm at {h_sensor:.1f} m MSL, "
                f"{slant_m:.1f} m long (tangent depression "
                f"{slant_m**2 / (8.0 * R_EARTH_M):.1f} m)"
            ),
        )

    eta = eta_from_theta_o(los.theta_o, h_sensor, h_tgt)
    zeta_low = math.pi - eta
    return ObserverLeg(
        spec=ColumnSegmentSpec(h_low_m=h_sensor, h_high_m=h_tgt, zeta_low_rad=zeta_low),
        toward_sensor="toward_lower",
        # cos(Δφ − π) = −cos(Δφ): the segment's lower→upper direction
        # (sensor → target) is the horizontal reverse of φ_o.
        delta_phi_seg_rad=delta_phi - math.pi,
        zeta_low_rad=zeta_low,
        slant_range_m=slant_m,
        detail=(
            f"up-looking column {h_sensor:.1f} → {h_tgt:.1f} m MSL, sensor-side "
            f"zenith {math.degrees(zeta_low):.4f}°, slant range {slant_m:.1f} m"
        ),
    )
