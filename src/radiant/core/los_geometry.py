"""Line-of-sight geometry for the Source → Atmosphere boundary (Option C).

`LineOfSightGeometry` is a frozen data contract published by SourceStage and
consumed by AtmosphereStage (see ADR-0002).  It carries the target altitude,
the top-of-atmosphere altitude, and the three zenith/azimuth angles that the
assembly equation needs to compute two-leg attenuation (τ_sun on the down-leg,
τ_up on the up-leg) and single-scatter path radiance.

This file is deliberately isolated from `core/geometry.py` (the spherical
viewing-geometry helper functions) per Rule 19 — LOS
geometry for atmospheric path assembly is a distinct computation from
observer-kinematic rotation and flat-Earth slant range.

Notes
-----
- All angles are stored in radians.  All altitudes are stored in meters.
- Slant range and airmass are computed on a spherical Earth with a single
  secant-type correction; see docstrings for the exact formulas.
- Earth radius is imported from `radiant.core.constants.R_EARTH_M` (Rule 13).

Direction generality (ADR-0011)
-------------------------------
Since Phase 1 of the Geometry Flexibility plan the contract carries **both**
endpoints: `h_sensor` joins `h_tgt`, and `theta_o` spans the closed domain
[0, π] so up-looking (`theta_o > π/2`) and level scenes are expressible.
`h_sensor` is optional only for back-compatibility with pre-ADR-0011
payloads (`None` = "sensor endpoint not carried"); `GeometryStage` always
populates it.  When it is present the altitude/hemisphere invariant and the
full two-topology horizon guard are enforced here; when it is absent only
the conservative angular band on `theta_o` can be applied, which is why
level and near-level geometry MUST supply the sensor endpoint.

Boundary converter
------------------
`theta_o_from_eta` is a module-level converter from the sensor-side off-nadir
look angle ``eta`` (which depends on ``h_sensor``) to the target-side observer
zenith ``theta_o`` (which does not).  **It is deliberately unwired** — CU-005
resolution (owner-directed, 2026-07-10): users supply the target-side zenith
directly via the canonical ``geometry.path_zenith_rad`` (CU-009); an
``eta``-input surface (``geometry.sensor_off_boresight_rad`` routed through this
converter, with a precedence rule against ``path_zenith_rad``) is deferred
behind the SensorDescriptor ADR rather than adding a second, redundant way
to specify the same look geometry today.  The converter stays tested
(``core/tests/test_los_geometry.py``) and reserved for that follow-on — it
is **not dead code**.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import (
    GUARD_HARD_RAD,
    GUARD_WARN_RAD,
    check_horizon_guard,
    horizon_band_action,
    slant_range_from_theta_o_m,
)


@dataclass(frozen=True, kw_only=True)
class LineOfSightGeometry:
    """Line-of-sight geometry for the atmosphere assembly equation.

    Parameters
    ----------
    h_tgt:
        Target altitude above mean sea level [m].  Must be ≥ 0.
        ``at_aperture`` descriptors set this to 0 by convention; the
        assembly arm ignores it.  ``h_tgt ≥ h_atm_top`` is legal (Gap
        95): the target sits above the atmospheric column (exo-altitude
        target — satellite, post-burnout booster) and the target→sensor
        leg is vacuum; ``AtmosphereStage`` serves that case exactly
        (τ_up = 1, L_path_up = 0, full ground→sensor column kept for
        the background) as the down-looking arm of
        ``radiant.atmosphere.topology.evaluate_path_topology``.  (The
        ``evaluate_with_exo_target`` wrapper this used to name was
        deleted in Geometry-Flexibility Phase 2 — ADR-0011 guardrail
        G4; the case is now a segment composition, not a carve-out.)
    h_sensor:
        Sensor altitude above mean sea level [m], or ``None`` for a
        pre-ADR-0011 payload that does not carry the sensor endpoint.
        ``GeometryStage`` always populates it.  When present it must be
        ≥ 0 and consistent with ``theta_o`` under the altitude/hemisphere
        invariant (``h_sensor > h_tgt ⟺ theta_o < π/2``), and the full
        two-topology horizon guard is applied.
    h_atm_top:
        Top of the atmospheric integration column [m] (v1 fixed default =
        Kármán line ≈ 100 km).
    theta_o:
        Observer zenith angle at the target [rad].  ``0`` = sensor at
        zenith-of-nadir (straight above the target), ``π/2`` = sensor on the
        target's horizon plane, ``π`` = sensor straight below (vertical
        up-looking).  Domain is the **closed** interval ``[0, π]``
        (ADR-0011); the near-horizontal band around ``π/2`` is rejected by
        the horizon guard rather than by the domain check.
    theta_s:
        Solar zenith angle at the target [rad], or ``None`` for pure-thermal
        scenarios where the sun is not used.  Must lie in ``[0, π]`` if set.
    delta_phi:
        Relative azimuth ``φ_s − φ_o`` [rad], or ``None``.  Must lie in
        ``[−π, π]`` if set.

    Derived properties
    ------------------
    slant_range_atm:
        Distance along the LOS from ``h_tgt`` to ``h_atm_top`` [m] on a
        spherical Earth.  Down-looking topology only — see the property
        docstring for the up-looking Phase 2 guard.
    path_airmass_up:
        Dimensionless airmass factor for the sensor-up leg.  Reduces to
        ``sec(theta_o)`` in the plane-parallel limit and diverges
        smoothly as ``theta_o → π/2``.
    los_direction:
        ``"down"`` | ``"up"`` | ``"level"`` — derived, never a user switch.
    is_uplooking:
        ``True`` iff ``los_direction == "up"``.
    """

    h_tgt: float
    h_sensor: float | None = None
    h_atm_top: float = 1.0e5
    theta_o: float
    theta_s: float | None = None
    delta_phi: float | None = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # h_atm_top must be physically plausible (positive)
        if self.h_atm_top <= 0.0:
            raise ParameterBoundsError(
                what=f"LineOfSightGeometry.h_atm_top = {self.h_atm_top} m is non-positive",
                why="Top of atmosphere must be a positive altitude above MSL.",
                action="Set h_atm_top to a positive value (v1 default: 1.0e5 m ≈ Kármán line).",
                context={"h_atm_top": self.h_atm_top},
            )

        if self.h_tgt < 0.0:
            raise ParameterBoundsError(
                what=f"LineOfSightGeometry.h_tgt = {self.h_tgt} m is negative",
                why="Target altitude must be non-negative (above MSL).",
                action=(
                    "Set h_tgt ≥ 0 m. Values at or above h_atm_top are legal — "
                    "the target→sensor leg is then treated as vacuum (Gap 95)."
                ),
                context={"h_tgt": self.h_tgt, "h_atm_top": self.h_atm_top},
            )

        if not (0.0 <= self.theta_o <= math.pi):
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.theta_o = {self.theta_o} rad "
                    f"({math.degrees(self.theta_o):.3f}°) is outside [0, π]"
                ),
                why=(
                    "Observer zenith at the target runs from 0 (sensor straight "
                    "above) through π/2 (sensor on the target's horizon plane) to "
                    "π (sensor straight below — vertical up-looking).  Nothing "
                    "outside [0, π] is a zenith angle.  The domain is closed at π "
                    "since ADR-0011; near-horizontal paths are handled by the "
                    "horizon guard, not by the domain check."
                ),
                action="Wrap theta_o into [0, π] radians (0–180°).",
                context={"theta_o": self.theta_o},
            )

        if self.h_sensor is not None and self.h_sensor < 0.0:
            raise ParameterBoundsError(
                what=f"LineOfSightGeometry.h_sensor = {self.h_sensor} m is negative",
                why="Sensor altitude must be non-negative (at or above MSL).",
                action="Set h_sensor ≥ 0 m, or leave it None for a legacy payload.",
                context={"h_sensor": self.h_sensor},
            )

        self._validate_path_geometry()

        if self.theta_s is not None and not (0.0 <= self.theta_s <= math.pi):
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.theta_s = {self.theta_s} rad "
                    f"({math.degrees(self.theta_s):.3f}°) is outside [0, π]"
                ),
                why="Solar zenith at target must lie in [0, π] when specified.",
                action="Set theta_s in [0, π] rad, or leave as None for pure-thermal scenarios.",
                context={"theta_s": self.theta_s},
            )

        if self.delta_phi is not None and not (-math.pi <= self.delta_phi <= math.pi):
            raise ParameterBoundsError(
                what=(f"LineOfSightGeometry.delta_phi = {self.delta_phi} rad is outside [−π, π]"),
                why="Relative azimuth φ_s − φ_o must be expressed in [−π, π].",
                action="Wrap delta_phi into [−π, π] before constructing the geometry.",
                context={"delta_phi": self.delta_phi},
            )

    def _validate_path_geometry(self) -> None:
        """Hemisphere invariant + horizon guard (ADR-0011, plan §8.3).

        With the sensor endpoint present the full two-topology guard runs
        (angular bands for endpoint-minimum paths, tangent-height depression
        for interior-tangent ones).  Without it — a pre-ADR-0011 payload —
        only ``theta_o`` is known, so the conservative endpoint-minimum
        angular band is applied; that is exactly the legacy down-looking
        topology, and it is why a level or near-level scene must carry
        ``h_sensor``.
        """
        if self.h_sensor is not None:
            check_horizon_guard(
                self.theta_o,
                self.h_sensor,
                self.h_tgt,
                where="LineOfSightGeometry: horizon guard",
            )
            return

        action, band_rad = horizon_band_action(self.theta_o)
        if action == "raise":
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.theta_o = {self.theta_o} rad "
                    f"({math.degrees(self.theta_o):.4f}°) is "
                    f"{math.degrees(band_rad):.4f}° from the geometric horizontal, "
                    f"inside the ±{math.degrees(GUARD_HARD_RAD):g}° hard horizon guard"
                ),
                why=(
                    "Within a half-degree of the horizontal, atmospheric refraction "
                    "dominates the path geometry and v1.x has no refraction model, so "
                    "any number returned here would be quietly wrong (ADR-0011 "
                    "decision 6).  The airmass column also loses meaning there."
                ),
                action=(
                    f"Move theta_o more than {math.degrees(GUARD_WARN_RAD):g}° from "
                    "π/2 rad (90°), or "
                    "supply h_sensor so the guard can use the tangent-point topology "
                    "(a short level path with a shallow tangent is admissible; a "
                    "grazing slant is not)."
                ),
                context={"theta_o": self.theta_o, "band_rad": band_rad},
            )
        if action == "warn":
            warnings.warn(
                f"LineOfSightGeometry.theta_o = {math.degrees(self.theta_o):.4f}° is "
                f"{math.degrees(band_rad):.4f}° from the geometric horizontal. "
                "Computing anyway, but "
                "atmospheric refraction is NOT modelled in v1.x and is the dominant "
                f"geometric error in this band (hard guard at "
                f"±{math.degrees(GUARD_HARD_RAD):g}°; "
                "thresholds provisional pending Phase 2 MODTRAN calibration).",
                UserWarning,
                stacklevel=4,
            )

    # ------------------------------------------------------------------
    # Derived direction (ADR-0011 decision 1 — derived, never a switch)
    # ------------------------------------------------------------------

    @property
    def los_direction(self) -> str:
        """Signed LOS direction: ``"down"`` | ``"up"`` | ``"level"``.

        Derived from the altitude pair when ``h_sensor`` is carried, and
        from ``theta_o`` otherwise — the two agree by the hemisphere
        invariant, except for equal altitudes, which cannot occur in a
        legacy (``h_sensor is None``) payload.
        """
        if self.h_sensor is not None:
            if self.h_sensor > self.h_tgt:
                return "down"
            if self.h_sensor < self.h_tgt:
                return "up"
            return "level"
        if self.theta_o < math.pi / 2.0:
            return "down"
        if self.theta_o > math.pi / 2.0:
            return "up"
        return "level"

    @property
    def is_uplooking(self) -> bool:
        """``True`` iff the sensor sits below the target (``theta_o > π/2``)."""
        return self.los_direction == "up"

    # ------------------------------------------------------------------
    # Derived geometric properties
    # ------------------------------------------------------------------

    def _require_downlooking_column(self, what: str) -> None:
        """Reject up-looking use of the target→h_atm_top column (Phase 2).

        ``slant_range_atm`` and ``path_airmass_up`` are down-looking-topology
        quantities: they measure the column *above* the target, on the way
        out to the sensor.  For ``theta_o > π/2`` the sensor is below the
        target and that column is not the path — the up-looking atmospheric
        arm is Phase 2 path-segment work (Gaps 108/109), so this raises
        rather than returning a plausible-looking wrong number (Rule 17).

        The exo-altitude carve-out (``h_tgt >= h_atm_top``) is checked by the
        callers *before* this guard: there is no column either way, so the
        vacuum limits (0.0 m, airmass 1.0) stay exact — that is what the
        up-looking LEO→GEO quick win rides on.
        """
        if self.theta_o > math.pi / 2.0:
            raise ParameterBoundsError(
                what=(
                    f"LineOfSightGeometry.{what}: theta_o = {self.theta_o} rad "
                    f"({math.degrees(self.theta_o):.3f}°) is up-looking, but "
                    f"{what} measures the atmospheric column from h_tgt = "
                    f"{self.h_tgt} m up to h_atm_top = {self.h_atm_top} m"
                ),
                why=(
                    "For an up-looking path the sensor is below the target, so the "
                    "column above the target is not the target→sensor leg.  The "
                    "direction-aware path-segment products (up-path radiance, "
                    "horizontal arm, sky background) arrive in Phase 2 of the "
                    "Geometry Flexibility plan (Gaps 108/109); returning the "
                    "down-looking column here would be silently wrong."
                ),
                action=(
                    "Use a down-looking geometry (theta_o < π/2), or an exo-altitude "
                    "target (h_tgt >= h_atm_top) where the leg is vacuum, until the "
                    "Phase 2 up-looking column lands."
                ),
                context={
                    "theta_o": self.theta_o,
                    "h_tgt": self.h_tgt,
                    "h_atm_top": self.h_atm_top,
                    "los_direction": self.los_direction,
                },
            )

    @property
    def slant_range_atm(self) -> float:
        """Slant range from h_tgt up to h_atm_top along theta_o [m].

        Uses ray-sphere intersection from the target point on a spherical
        Earth of radius R_E.  The LOS originates at radius (R_E + h_tgt)
        with zenith angle theta_o (measured from the local vertical) and
        intersects the sphere of radius (R_E + h_atm_top):

            slant = -r_t cos(θ_o) + √((r_t cos(θ_o))² + (r_top² − r_t²))

        where r_t = R_E + h_tgt and r_top = R_E + h_atm_top.

        At θ_o = 0 this reduces to ``h_atm_top − h_tgt`` exactly.
        For an exo-altitude target (``h_tgt ≥ h_atm_top``, Gap 95) there
        is no column above the target: returns 0.0 m.
        """
        if self.h_tgt >= self.h_atm_top:
            return 0.0
        self._require_downlooking_column("slant_range_atm")
        r_t = R_EARTH_M + self.h_tgt
        r_top = R_EARTH_M + self.h_atm_top
        cos_theta = math.cos(self.theta_o)
        # (r_t cos θ)² + (r_top² − r_t²) — always ≥ 0 for r_top ≥ r_t.
        disc = (r_t * cos_theta) ** 2 + (r_top * r_top - r_t * r_t)
        return float(-r_t * cos_theta + math.sqrt(disc))

    @property
    def path_airmass_up(self) -> float:
        """Dimensionless airmass along the sensor up-leg.

        Defined as ``slant_range_atm / (h_atm_top − h_tgt)`` (the ratio of
        the slant path to the vertical path through the same column).  In
        the plane-parallel limit, this equals sec(theta_o) exactly.
        Spherical-Earth curvature makes the airmass diverge slightly more
        slowly than sec(θ_o) as θ_o → π/2, matching the standard "Kasten"
        shape without explicit refraction.

        For an exo-altitude target (``h_tgt ≥ h_atm_top``, Gap 95) the
        target→sensor leg traverses no column at all; the ratio is the
        vacuum limit 1.0 (0 m of slant path over 0 m of column).
        """
        dz = self.h_atm_top - self.h_tgt
        if dz <= 0.0:
            return 1.0
        self._require_downlooking_column("path_airmass_up")
        return float(self.slant_range_atm / dz)

    # ------------------------------------------------------------------
    # Earth-intercept check (Stage 7 — no_atmosphere=space precondition)
    # ------------------------------------------------------------------

    def intercepts_earth(self, h_sensor: float) -> bool:
        """Return True if the sensor→target LOS passes through the Earth.

        Spherical-Earth ray-sphere intersection from the sensor position.
        Used by the ``no_atmosphere`` sub-case ``space`` to validate that
        the sensor's LOS to the target clears the Earth limb — matrix §7:
        v1 has no earthlimb model, so any LOS that dips below the surface
        must be rejected.

        The sensor is placed at radius ``R_E + h_sensor`` and directed at
        the target through zenith angle ``theta_o`` (measured at the
        target on a spherical Earth).  Concretely: construct the LOS as
        the line from ``sensor_pos`` to ``target_pos`` and check whether
        the minimum distance from the Earth centre along the *segment*
        (not the infinite line) is below ``R_E``.

        Parameters
        ----------
        h_sensor:
            Sensor altitude above MSL [m].  Must be non-negative.  Passed
            explicitly rather than read from the ``h_sensor`` field so the
            pre-ADR-0011 call sites keep working; when the field is also
            set the caller is responsible for passing the same value.

        Returns
        -------
        bool
            ``True`` iff the LOS segment between sensor and target passes
            below the Earth's surface (``R_E``).  ``False`` if the path
            stays above the surface for its entire length, or exactly
            tangential within floating-point tolerance.

        Raises
        ------
        ParameterBoundsError
            If ``h_sensor`` is negative, if it contradicts ``theta_o``
            under the altitude/hemisphere invariant, or if no viewing
            triangle exists for the (altitudes, ``theta_o``) combination.

        Notes
        -----
        Geometry on a spherical Earth:
          * Target is at radius ``r_t = R_E + h_tgt``.
          * Sensor is at radius ``r_s = R_E + h_sensor``.
          * The target-centred observer zenith is ``theta_o``.
          * The slant range comes from
            :func:`radiant.core.viewing_triangle.slant_range_from_theta_o_m`,
            which applies the law of cosines to the triangle (Earth centre,
            target, sensor)::

                r_s² = r_t² + d² − 2 r_t d cos(π − theta_o)
                     = r_t² + d² + 2 r_t d cos(theta_o)

            and selects the root by altitude ordering (ADR-0011): the ``+``
            root for a sensor at or above the target — bit-identical to the
            expression this method used before Phase 1 — and the **near**
            (``−``) root for an up-looking path, where the ``+`` root is the
            far, through-the-Earth intersection.  Taking ``+`` unconditionally
            is what made a vertical LEO→GEO LOS (``theta_o = π``) falsely
            report an Earth intercept.
          * An altitude/zenith combination that admits no triangle at all
            (the ray never descends to the sensor shell) is a bad input, not
            an intercept: the solver raises an actionable error naming the
            ray's perigee altitude.  The pre-Phase-1 "return True" degenerate
            branches are gone.
          * The closest approach of the LOS segment to the Earth centre
            is:
                - if the foot of the perpendicular from the centre lies
                  *on* the segment: ``r_min = r_t sin(theta_o)``
                  (equivalently ``r_s sin(theta_s_at_sensor)``).
                - if the foot lies *off* the segment (behind target or
                  beyond sensor): the minimum is at one of the endpoints,
                  which are both ≥ R_E by construction.
          * We return ``r_min < R_E`` for on-segment feet; for off-segment
            feet we return ``False`` (endpoints are above the surface).

        At ``theta_o = 0`` (nadir-looking from above), ``r_min = 0`` but
        the foot is not on the segment for a space sensor above the
        atmosphere — the segment stays radial and never dips below R_E.
        The on-segment check handles this correctly.
        """
        if h_sensor < 0.0:
            raise ParameterBoundsError(
                what=f"LineOfSightGeometry.intercepts_earth: h_sensor = {h_sensor} m is negative",
                why="Sensor altitude must be non-negative (at or above MSL).",
                action="Set h_sensor ≥ 0.",
                context={"h_sensor": h_sensor},
            )

        r_t = R_EARTH_M + self.h_tgt
        cos_to = math.cos(self.theta_o)
        sin_to = math.sin(self.theta_o)

        # Slant range target→sensor, branch-selected by altitude ordering.
        # The hemisphere invariant and the "no such triangle" case are
        # validated inside the solver (actionable errors, Rule 15/17).
        d = slant_range_from_theta_o_m(self.theta_o, h_sensor, self.h_tgt)
        if d <= 0.0:
            # Coincident endpoints (level path of zero length): there is no
            # segment to dip below anything.
            return False

        # Closest approach of the infinite line through (target, sensor)
        # to Earth centre = r_t · sin(theta_o) (perpendicular from centre
        # to the LOS through the target point with zenith theta_o).
        r_min_line = r_t * sin_to

        # Foot-of-perpendicular parameter t along the segment
        # target → sensor (t = 0 at target, t = d at sensor).
        #
        # Set up a target-local 2-D frame: target at origin, local up
        # along +y, Earth centre at (0, −r_t) (directly below the target
        # along local-up).  The LOS direction from target toward sensor
        # has zenith theta_o measured from local-up, and lies in the xy
        # plane, so the direction unit vector is (sin(theta_o),
        # cos(theta_o)).  Line points:
        #     P(t) = (t · sin(theta_o),  r_t + t · cos(theta_o))
        # Squared distance from origin to P(t):
        #     |P(t)|² = t² · sin² + (r_t + t · cos)²
        #             = t² + 2 r_t cos(theta_o) · t + r_t²
        # Minimum (d/dt = 0) at
        #     t_foot = −r_t · cos(theta_o)
        # The foot lies on the LOS segment [0, d] iff
        #     0 ≤ −r_t · cos(theta_o) ≤ d
        # Nadir (theta_o = 0): t_foot = −r_t < 0 ⇒ foot OFF the segment
        # (behind the target, toward Earth centre).  The closest point on
        # the segment is therefore an endpoint; both endpoints have radii
        # ≥ R_EARTH_M by construction, so no intercept.  Correct.
        t_foot = -r_t * cos_to
        if 0.0 <= t_foot <= d:
            # Foot on segment — closest approach is r_min_line.
            return bool(r_min_line < R_EARTH_M)
        # Foot off segment — closest approach is at an endpoint.  Both
        # endpoints sit at radii r_t ≥ R_EARTH_M and r_s ≥ R_EARTH_M by
        # construction, so the segment does not dip below the surface.
        return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict.

        ``h_sensor`` is emitted **only when it is carried** (not ``None``):
        a legacy payload therefore serializes to exactly the pre-ADR-0011
        byte sequence, which keeps the descriptor-snapshot baselines
        unchanged for every existing down-looking scene (plan §3 principle
        3 — new behaviour is reachable only through newly legal inputs).
        Round-tripping is unaffected: :meth:`from_dict` maps both "key
        absent" and an explicit ``None`` back to ``h_sensor=None``, which is
        the same state ("sensor endpoint not carried").
        """
        payload: dict[str, Any] = {
            "h_tgt": self.h_tgt,
            "h_atm_top": self.h_atm_top,
            "theta_o": self.theta_o,
            "theta_s": self.theta_s,
            "delta_phi": self.delta_phi,
        }
        if self.h_sensor is not None:
            payload["h_sensor"] = self.h_sensor
        return payload

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LineOfSightGeometry:
        """Rebuild from a ``to_dict`` payload.

        Back-compatible with pre-ADR-0011 payloads: a missing ``h_sensor``
        key and an explicit ``None`` both round-trip to ``None`` (sensor
        endpoint not carried), distinct from any numeric altitude.
        """
        return cls(
            h_tgt=float(d["h_tgt"]),
            theta_o=float(d["theta_o"]),
            h_sensor=None if d.get("h_sensor") is None else float(d["h_sensor"]),
            h_atm_top=float(d.get("h_atm_top", 1.0e5)),
            theta_s=None if d.get("theta_s") is None else float(d["theta_s"]),
            delta_phi=None if d.get("delta_phi") is None else float(d["delta_phi"]),
        )


# ---------------------------------------------------------------------------
# Boundary converters (reserved for Stage 7 / SensorDescriptor follow-on)
# ---------------------------------------------------------------------------
#
# `theta_o_from_eta` is the one-shot Rule-2 unit/coordinate converter from the
# sensor-referenced off-nadir angle η (which depends on h_sensor) to the
# target-referenced observer zenith θ_o (which LineOfSightGeometry carries).
# It is not invoked by any stage today.  Stage 7 of the Option C plan (and
# the SensorDescriptor follow-on ADR that will carry `h_sensor`) is the first
# consumer.  Keeping it in this module keeps the boundary conversion adjacent
# to the geometry it converts into, and avoids a cross-stage dependency on a
# future SensorDescriptor module.


def theta_o_from_eta(eta: float, h_sensor: float, h_tgt: float) -> float:
    """Convert off-nadir look angle η at the sensor to observer zenith θ_o at the target.

    Uses the spherical-Earth corrected sine rule (law of sines applied to the
    triangle formed by Earth centre, sensor, and target):

        sin(θ_o) = (R_E + h_sensor) / (R_E + h_tgt) · sin(η)

    This is the Rule-2 boundary conversion: the user provides ``η`` (sensor
    pointing), and the atmospheric assembly needs ``θ_o`` (LOS zenith as
    measured at the target, which is what ``LineOfSightGeometry.theta_o``
    carries).  The two are identical in the plane-parallel limit but differ
    by up to ~8° at LEO off-nadir geometries.

    Parameters
    ----------
    eta:
        Sensor off-nadir angle [rad].  Must satisfy the law of sines
        validity condition ``sin(η) · (R_E + h_sensor) ≤ (R_E + h_tgt)``
        (the LOS must actually intersect the target shell).
    h_sensor:
        Sensor altitude above MSL [m].  Must be non-negative.
    h_tgt:
        Target altitude above MSL [m].  Must be non-negative.

    Returns
    -------
    float
        Observer zenith at target [rad] in ``[0, π/2]``.

    Raises
    ------
    ParameterBoundsError
        If ``eta`` or the altitudes are invalid, or if the sine-rule ratio
        exceeds 1 (physically impossible LOS — the sensor-shell ray would
        not intersect the target shell at this azimuth).
    """
    if h_sensor < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_eta: h_sensor = {h_sensor} m is negative",
            why="Sensor altitude must be non-negative.",
            action="Set h_sensor ≥ 0.",
            context={"h_sensor": h_sensor},
        )
    if h_tgt < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_eta: h_tgt = {h_tgt} m is negative",
            why="Target altitude must be non-negative.",
            action="Set h_tgt ≥ 0.",
            context={"h_tgt": h_tgt},
        )
    if not (-math.pi / 2.0 <= eta <= math.pi / 2.0):
        raise ParameterBoundsError(
            what=(
                f"theta_o_from_eta: eta = {eta} rad "
                f"({math.degrees(eta):.3f}°) is outside [−π/2, π/2]"
            ),
            why="Sensor off-nadir angle must lie in [−π/2, π/2].",
            action="Reduce |eta| below π/2.",
            context={"eta": eta},
        )

    ratio = (R_EARTH_M + h_sensor) / (R_EARTH_M + h_tgt) * math.sin(eta)
    if abs(ratio) > 1.0:
        # Guard against floating-point overshoot right at the horizon tangent.
        if abs(ratio) - 1.0 < 1e-12:
            ratio = math.copysign(1.0, ratio)
        else:
            raise ParameterBoundsError(
                what=(f"theta_o_from_eta: sin(θ_o) ratio = {ratio:.6f} exceeds 1"),
                why=(
                    "Sine-rule inversion has no solution — the sensor LOS at "
                    "this η does not intersect the target altitude shell "
                    "(grazes past it)."
                ),
                action=("Reduce eta, raise h_tgt, or acknowledge the LOS misses the target shell."),
                context={
                    "eta": eta,
                    "h_sensor": h_sensor,
                    "h_tgt": h_tgt,
                    "sin_ratio": ratio,
                },
            )
    return float(math.asin(ratio))
