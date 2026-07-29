"""Spherical viewing triangle — target-side-zenith (θ_o) solutions.

One geometric model, solved several ways.  The triangle is (Earth centre,
target, sensor) on a spherical Earth:

    r_t = R_E + h_target      (target radius)
    r_s = R_E + h_sensor      (sensor radius)
    θ_o = observer zenith measured AT THE TARGET from local up
    η   = interior angle at the sensor between sensor→centre (nadir) and
          sensor→target
    φ   = central angle at the Earth centre
    d   = slant range target ↔ sensor

Interior-angle relations (law of sines / cosines on the triangle) — these
hold for **any** altitude ordering:

    sin(η) = (r_t / r_s) · sin(θ_o)                       [law of sines]
    φ      = θ_o − η                                       [angle sum]
    d      = −r_t cos(θ_o) ± √(r_t² cos²(θ_o) + r_s² − r_t²)
                                                           [law of cosines]
    ground range (surface arc) = R_E · φ

Direction generality (ADR-0011, plan `Geometry_Flexibility_Plan.md` Phase 1)
---------------------------------------------------------------------------
The 2026-07-11 "v1 has no uplooking geometry" ruling is **superseded** by
ADR-0011: the same triangle is now read from either vertex.

* **Down-looking** (``h_sensor > h_target``, θ_o < π/2): the ``+`` root is
  the only positive one — the historical path, whose expressions are kept
  byte-identical (zero drift for every existing golden baseline).
* **Up-looking** (``h_sensor < h_target``, θ_o > π/2): both law-of-cosines
  roots are positive (the SSA ambiguity).  Entering θ_o at the *upper*
  endpoint is therefore ambiguous, and this module resolves it to the
  **near** (``−``) root — the direct path whose tangent point lies outside
  the segment.  η is then the *obtuse* branch of the arcsine (the sensor
  looks above its own horizontal).  For near-level up-looking pairs, where
  the horizontal separation exceeds the tangent length √(r_t² − r_s²), the
  physical path is the *far* root; that geometry must be entered through
  :func:`solve_from_lower_zenith`, which is unambiguous by construction
  (ADR-0011 decision 3 — angle entry keyed to the path's lower endpoint).
* **Level** (``h_sensor == h_target``): the near root degenerates to zero
  (the target itself), so the chord is the ``+`` root; the central-angle
  form is exposed directly by the ``level_*`` helpers.

θ_o domain is the **closed** interval [0, π].  π is attained exactly by the
vertical up-looking case (ground sensor with the target at its zenith, LEO
sensor directly under a GEO target).  ADR-0011 writes "[0, π)"; that is a
notation slip — owner-confirmed 2026-07-26 (plan §8.3) — the closed interval is
what the geometry requires and what is implemented here.

Altitude/hemisphere invariant (derived, enforced):

    h_sensor >  h_target  ⟺  θ_o < π/2
    h_sensor <= h_target  ⟺  θ_o > π/2

(equal altitudes give θ_o = π/2 + φ/2; θ_o = π/2 exactly means coincident
endpoints).  A combination that violates it is not a viewing geometry at
all and raises an actionable error naming both altitudes.

Horizon guard (plan §8.3 addendum) is implemented by
:func:`classify_horizon_topology` / :func:`check_horizon_guard`; see those
docstrings for the two-tier rule and its provisional thresholds.

This module is the θ_o-referenced counterpart of the η-referenced helpers
in :mod:`radiant.core.geometry` (``slant_range_spherical_m``,
``incidence_angle_rad``) and the inverse family of
:func:`radiant.core.los_geometry.theta_o_from_eta`.  The canonical
``geometry.path_zenith_rad`` parameter carries θ_o (CU-005/CU-009
convention), so chain-level derivations use THESE functions; the
η-referenced pair remains for callers that genuinely hold a sensor
pointing angle.  (CU-096 tracks the historical θ_o/η conflation in
platform/performance.)

Uses :data:`radiant.core.constants.R_EARTH_M` (6371.0 km mean radius) —
the single canonical Earth radius shared by :mod:`radiant.core.los_geometry`,
:mod:`radiant.core.geometry`, and the orbital kinematics — so every leg of
the triangle and the atmospheric path live on the same Earth.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

# ---------------------------------------------------------------------------
# Horizon-guard thresholds (plan §8.3 addendum, owner 2026-07-26)
#
# PROVISIONAL: calibrated in Phase 2 against a MODTRAN refraction on/off deck
# pair (batch 2, alongside the SST ladder).  They are named constants, never
# inline literals, precisely so that recalibration is a one-line change.
# ---------------------------------------------------------------------------

# Rule 2 — angles are stored in radians internally; the degree values the plan
# and ADR quote (0.5° / 2.0°) appear exactly once each, in the ``math.radians``
# call that defines the canonical constant, and thereafter only in message text
# (CU-222).

#: Endpoint-minimum topology — hard guard half-width about the horizontal [rad]
#: (0.5°).
GUARD_HARD_RAD = math.radians(0.5)
#: Endpoint-minimum topology — outer edge of the compute-with-warning shoulder
#: [rad] (2.0°).
GUARD_WARN_RAD = math.radians(2.0)
#: Interior-tangent topology — tangent-height depression below which the path is clean [m].
GUARD_DH_CLEAN_M = 100.0
#: Interior-tangent topology — tangent-height depression above which the path is rejected [m].
GUARD_DH_RAISE_M = 2000.0

#: Effective-Earth-radius factor used to *size* (never to model) the refraction the
#: shoulder warning excludes — the standard k = 4/3 approximation, in which a ray
#: bends as if the Earth had radius k·R and the tangent depression of a given
#: geometry shrinks by 1/k.  v1.x models no refraction (ADR-0011 decision 6); this
#: constant exists only so the warning can state the order of magnitude of what it
#: is leaving out, which was the ratified intent of the warn shoulder (CU-269).
GUARD_REFRACTION_K = 4.0 / 3.0

#: Angular slack on the band comparisons [rad].  A threshold quoted as "0.5°"
#: must mean the same band whether the caller's angle was built as
#: ``math.radians(89.5)`` or as ``math.pi/2 - math.radians(0.5)`` — those two
#: differ by ~1e-16 rad in IEEE-754, which without this slack flips the verdict
#: at exactly the ratified boundary (found while landing CU-222).  1e-12 rad is
#: 6e-11 degrees: far below any physical meaning, and the same trigonometric
#: tolerance the rest of the package uses.
_GUARD_BAND_EPS_RAD = 1e-12

_TOPOLOGY_ENDPOINT_MIN = "endpoint_minimum"
_TOPOLOGY_INTERIOR = "interior_tangent"

#: Float slack for the law-of-sines ratio right at tangency.
_RATIO_EPS = 1e-12


@dataclass(frozen=True, kw_only=True)
class HorizonGuardResult:
    """Classification of a sensor↔target segment against the horizon guard.

    Attributes
    ----------
    topology:
        ``"endpoint_minimum"`` — the foot of the perpendicular from the
        Earth centre lies *outside* the segment, so the closest approach to
        the surface is the segment's lower endpoint (every up/down slant).
        ``"interior_tangent"`` — the foot lies *on* the segment, so the ray
        dips to a tangent point between the endpoints (level and near-level
        paths, and any limb-crossing continuation).
    action:
        ``"clean"`` | ``"warn"`` | ``"raise"``.
    zenith_low_rad:
        Zenith angle of the path evaluated at its **lower** endpoint [rad].
    h_low_m:
        Altitude of the lower endpoint [m].
    slant_range_m:
        Segment length [m].
    dh_m:
        Tangent-height depression below the lower endpoint [m] — set for
        ``interior_tangent`` topology, ``None`` otherwise.
    band_rad:
        ``|zenith_low − π/2|`` [rad] — set for ``endpoint_minimum``
        topology, ``None`` otherwise.  Radians is the canonical angular unit
        (Rule 2); degrees appear only in :attr:`detail` and in the guard's
        warning / error text.
    detail:
        Human-readable, quantified one-liner used by
        :func:`check_horizon_guard` in its warning / error text.
    """

    topology: str
    action: str
    zenith_low_rad: float
    h_low_m: float
    slant_range_m: float
    dh_m: float | None = None
    band_rad: float | None = None
    detail: str = ""


@dataclass(frozen=True, kw_only=True)
class LowerEndpointSolution:
    """Triangle solved from the path's **lower** endpoint (ADR-0011 §3).

    Unambiguous by construction: a ray leaving the lower endpoint at zenith
    ``zeta_low_rad`` crosses the higher shell exactly once, whether it
    ascends monotonically (``zeta_low ≤ π/2``) or descends to a perigee
    first (``zeta_low > π/2``).

    Attributes
    ----------
    zeta_low_rad:
        Input zenith of the ray at the lower endpoint [rad].
    zeta_up_rad:
        Zenith of the same (ascending) ray where it crosses the upper
        shell [rad] — always acute: ``asin((r_low / r_up)·sin(ζ_low))``.
    theta_o_rad:
        ``π − zeta_up_rad``: the observer zenith of the **reverse** ray at
        the upper endpoint.  When the upper endpoint is the target (an
        up-looking scene) this is the canonical ``geometry.path_zenith_rad``.
        When the *lower* endpoint is the target (a down-looking scene) the
        canonical θ_o is ``zeta_low_rad`` itself.
    slant_range_m:
        Distance between the endpoints [m].
    central_angle_rad:
        ``zeta_low_rad − zeta_up_rad``.
    eta_int_rad:
        Interior angle of the triangle at the **upper** endpoint [rad]
        (equal to ``zeta_up_rad``).  For a down-looking scene, where the
        sensor is the upper endpoint, this is the sensor off-nadir angle η.
    h_low_m, h_up_m:
        Endpoint altitudes [m].
    """

    zeta_low_rad: float
    zeta_up_rad: float
    theta_o_rad: float
    slant_range_m: float
    central_angle_rad: float
    eta_int_rad: float
    h_low_m: float
    h_up_m: float


def _validate_altitudes(h_sensor_m: float, h_target_m: float, where: str) -> tuple[float, float]:
    """Common altitude validation; returns (r_t, r_s).

    Since ADR-0011 there is **no** altitude-ordering gate here — only the
    physical requirement that both endpoints sit at or above MSL.  Ordering
    is checked against θ_o by :func:`_validate_hemisphere`.
    """
    if h_target_m < 0.0:
        raise ParameterBoundsError(
            what=f"{where}: h_target_m = {h_target_m} m is negative",
            why="Target altitude must be at or above MSL.",
            action="Set h_target_m >= 0.",
            context={"h_target_m": h_target_m},
        )
    if h_sensor_m < 0.0:
        raise ParameterBoundsError(
            what=f"{where}: h_sensor_m = {h_sensor_m} m is negative",
            why="Sensor altitude must be at or above MSL.",
            action="Set h_sensor_m >= 0.",
            context={"h_sensor_m": h_sensor_m},
        )
    return R_EARTH_M + h_target_m, R_EARTH_M + h_sensor_m


def _validate_theta_o(theta_o_rad: float, where: str) -> None:
    """Validate θ_o against the CLOSED domain [0, π].

    Closed at π: the vertical up-looking geometry (ground sensor with the
    target at its zenith, LEO sensor directly beneath a GEO target) is
    θ_o = π *exactly*, and it is a perfectly ordinary scene.  ADR-0011
    writes the domain as "[0, π)" — a notation slip, owner-confirmed
    2026-07-26 (plan §8.3); the closed interval is implemented here.
    """
    if not (0.0 <= theta_o_rad <= math.pi):
        raise ParameterBoundsError(
            what=(
                f"{where}: theta_o_rad = {theta_o_rad} rad "
                f"({math.degrees(theta_o_rad):.3f}°) is outside [0, π]"
            ),
            why=(
                "Observer zenith at the target is measured from the target's "
                "local up: 0 = sensor at zenith-of-nadir (straight above), "
                "π/2 = sensor on the horizon plane, π = sensor straight below "
                "(vertical up-looking).  Nothing outside [0, π] is a zenith angle."
            ),
            action="Wrap theta_o_rad into [0, π] rad (0–180°).",
            context={"theta_o_rad": theta_o_rad},
        )


def _validate_hemisphere(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float, where: str
) -> None:
    """Enforce the altitude/hemisphere invariant (ADR-0011).

    ``h_sensor > h_target ⟺ θ_o < π/2`` and ``h_sensor <= h_target ⟺
    θ_o > π/2``.  Equal altitudes give ``θ_o = π/2 + φ/2 > π/2`` for any
    non-zero separation; ``θ_o = π/2`` exactly is the coincident-endpoint
    degenerate case and is admitted only there.

    θ_o = π/2 with the sensor strictly above the target describes a ray
    launched exactly along the target's horizontal — the hard horizon guard
    case (ADR-0011 decision 6), rejected here for the same reason.
    """
    half_pi = math.pi / 2.0
    if h_sensor_m > h_target_m:
        ok = theta_o_rad < half_pi
        implied = "above"
    elif h_sensor_m < h_target_m:
        ok = theta_o_rad > half_pi
        implied = "not above"
    else:
        ok = theta_o_rad >= half_pi
        implied = "not above (level with)"
    if ok:
        return
    hemisphere = "below" if theta_o_rad > half_pi else "above"
    raise ParameterBoundsError(
        what=(
            f"{where}: h_sensor_m = {h_sensor_m} m is {implied} h_target_m = "
            f"{h_target_m} m, but theta_o_rad = {theta_o_rad} rad "
            f"({math.degrees(theta_o_rad):.3f}°) places the sensor in the "
            f"{hemisphere}-the-horizon hemisphere seen from the target"
        ),
        why=(
            "θ_o is the zenith of the target→sensor ray measured at the "
            "target, so it fixes which side of the target's horizon plane "
            "the sensor lies on: θ_o < π/2 ⇔ h_sensor > h_target, "
            "θ_o > π/2 ⇔ h_sensor <= h_target (equal altitudes give "
            "θ_o = π/2 + φ/2).  θ_o = π/2 with unequal altitudes is the "
            "horizontal-launch grazing case, rejected by the horizon guard "
            "(ADR-0011 decision 6, no refraction model)."
        ),
        action=(
            "Either correct the altitudes or replace theta_o_rad with the "
            f"supplementary-hemisphere value {math.pi - theta_o_rad:.6f} rad "
            f"({180.0 - math.degrees(theta_o_rad):.3f}°); for near-level "
            "geometry enter the angle at the lower endpoint via "
            "solve_from_lower_zenith()."
        ),
        context={
            "theta_o_rad": theta_o_rad,
            "h_sensor_m": h_sensor_m,
            "h_target_m": h_target_m,
        },
    )


def _sine_ratio(theta_o_rad: float, r_t: float, r_s: float, where: str) -> float:
    """``(r_t / r_s)·sin(θ_o)`` with a tangency-tolerant range check."""
    ratio = (r_t / r_s) * math.sin(theta_o_rad)
    if ratio > 1.0:
        if ratio - 1.0 <= _RATIO_EPS:
            return 1.0
        r_perigee = r_t * math.sin(theta_o_rad)
        raise ParameterBoundsError(
            what=(
                f"{where}: the target→sensor ray at theta_o_rad = {theta_o_rad} rad "
                f"({math.degrees(theta_o_rad):.3f}°) never descends to the sensor "
                f"shell — its perigee radius is {r_perigee:.1f} m "
                f"({r_perigee - R_EARTH_M:.1f} m altitude), above the sensor at "
                f"{r_s - R_EARTH_M:.1f} m"
            ),
            why=(
                "The law of sines has no solution when (r_t/r_s)·sin(θ_o) > 1: "
                "the straight ray leaving the target at this zenith bottoms out "
                "above the sensor's altitude, so no such viewing triangle exists."
            ),
            action=(
                "Increase theta_o_rad toward π (steeper down-toward-the-sensor "
                "ray), raise the sensor altitude, or enter the geometry from the "
                "lower endpoint with solve_from_lower_zenith()."
            ),
            context={
                "theta_o_rad": theta_o_rad,
                "r_perigee_m": r_perigee,
                "h_perigee_m": r_perigee - R_EARTH_M,
                "h_sensor_m": r_s - R_EARTH_M,
            },
        )
    return ratio


def eta_from_theta_o(theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0) -> float:
    """Interior angle η [rad] at the sensor, from target-side zenith θ_o.

    Law of sines on the viewing triangle::

        sin(η) = (R_E + h_target) / (R_E + h_sensor) · sin(θ_o)

    η is measured at the sensor between the sensor→Earth-centre direction
    (local nadir) and the sensor→target direction.  For a down-looking
    sensor it is the familiar off-nadir look angle and is acute; for an
    up-looking sensor (target above) the target lies above the sensor's own
    horizontal and η is the **obtuse** branch ``π − asin(...)``; at equal
    altitudes it is ``π − θ_o``.

    Exact inverse of :func:`radiant.core.los_geometry.theta_o_from_eta` on
    the down-looking branch, where ``r_t < r_s`` makes the ratio < 1 and
    η < θ_o strictly for θ_o > 0.
    """
    _validate_theta_o(theta_o_rad, "eta_from_theta_o")
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "eta_from_theta_o")
    _validate_hemisphere(theta_o_rad, h_sensor_m, h_target_m, "eta_from_theta_o")
    if r_s > r_t:
        # Down-looking — historical expression, kept byte-identical (zero drift).
        return float(math.asin((r_t / r_s) * math.sin(theta_o_rad)))
    if r_s == r_t:
        # Level: isoceles triangle, base angles equal ⇒ η = π − θ_o.
        return float(math.pi - theta_o_rad)
    # Up-looking near branch: the sensor sits on the descending leg of the
    # ray, so the target is above the sensor's horizontal ⇒ η is obtuse.
    ratio = _sine_ratio(theta_o_rad, r_t, r_s, "eta_from_theta_o")
    return float(math.pi - math.asin(ratio))


def slant_range_from_theta_o_m(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0
) -> float:
    """Slant range target → sensor [m] from target-side zenith θ_o.

    Law of cosines on the viewing triangle::

        d = −r_t cos(θ_o) ± √( r_t² cos²(θ_o) + r_s² − r_t² )

    Root selection (ADR-0011):

    * ``r_s > r_t`` (down-looking) — the ``+`` root is the only positive
      one.  At θ_o = 0 it reduces to ``h_sensor − h_target`` exactly.
    * ``r_s == r_t`` (level) — the ``−`` root degenerates to 0 (the target
      itself); the chord is the ``+`` root, ``2 r sin(φ/2)``.
    * ``r_s < r_t`` (up-looking) — both roots are positive; the **near**
      (``−``) root is selected, i.e. the direct path that reaches the
      sensor before the ray's perigee.  At θ_o = π it reduces to
      ``h_target − h_sensor`` exactly.  See the module docstring for the
      near-level caveat and :func:`solve_from_lower_zenith`.
    """
    _validate_theta_o(theta_o_rad, "slant_range_from_theta_o_m")
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "slant_range_from_theta_o_m")
    _validate_hemisphere(theta_o_rad, h_sensor_m, h_target_m, "slant_range_from_theta_o_m")
    cos_to = math.cos(theta_o_rad)
    disc = (r_t * cos_to) ** 2 + (r_s * r_s - r_t * r_t)
    if r_s >= r_t:
        # disc >= r_s² − r_t² >= 0 for r_s >= r_t — always a real root.
        return float(-r_t * cos_to + math.sqrt(disc))
    # Up-looking: the ratio check is the same condition as disc >= 0, but it
    # reports the perigee altitude, which is the actionable diagnostic.
    _sine_ratio(theta_o_rad, r_t, r_s, "slant_range_from_theta_o_m")
    return float(-r_t * cos_to - math.sqrt(max(disc, 0.0)))


def ground_range_from_theta_o_m(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0
) -> float:
    """Surface arc distance sensor-ground-point → target [m] from θ_o.

    Angle sum of the viewing triangle: the central angle is ``φ = θ_o − η``
    (interior angles π − θ_o at the target, η at the sensor, φ at the centre
    sum to π).  Ground range is the Earth-surface arc ``R_E · φ``.  Zero at
    both collinear limits (θ_o = 0, θ_o = π).  The identity is universal —
    it holds for the up-looking obtuse-η branch and the level branch too.
    """
    eta = eta_from_theta_o(theta_o_rad, h_sensor_m, h_target_m)
    return float(R_EARTH_M * (theta_o_rad - eta))


def theta_o_from_ground_range_m(
    ground_range_m: float, h_sensor_m: float, h_target_m: float = 0.0
) -> float:
    """Target-side zenith θ_o [rad] from surface arc distance.

    Inverse of :func:`ground_range_from_theta_o_m`.  From the central
    angle ``φ = ground_range / R_E``, the law of cosines gives the slant
    range, and the law of cosines again (about the target vertex) gives
    the interior angle at the target, whose supplement is θ_o::

        d²          = r_t² + r_s² − 2 r_t r_s cos(φ)
        cos(π − θ_o) = (r_t² + d² − r_s²) / (2 r_t d)

    Down-looking (``h_sensor > h_target``) raises when the requested arc
    puts the sensor at or below the target's horizon (θ_o would reach π/2)
    — the maximum expressible arc is ``R_E · (π/2 − asin(r_t / r_s))``.

    Level (``h_sensor == h_target``) uses the central-angle form directly:
    ``θ_o = π/2 + φ/2``.

    Up-looking (``h_sensor < h_target``) mirrors the down-looking
    construction with the endpoint roles swapped; it raises when the arc is
    long enough that the chord passes its own tangent point (``d`` exceeds
    the tangent length ``√(r_t² − r_s²)``), because the forward θ_o solver
    resolves that regime to the near root instead.  Enter such near-level
    geometry through :func:`solve_from_lower_zenith`.
    """
    if ground_range_m < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_ground_range_m: ground_range_m = {ground_range_m} m is negative",
            why="Ground range is a distance; it cannot be negative.",
            action="Set ground_range_m >= 0.",
            context={"ground_range_m": ground_range_m},
        )
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "theta_o_from_ground_range_m")

    if r_s == r_t:
        # Level path — the triangle is isoceles and the central-angle form
        # is exact and better conditioned than the law-of-cosines route.
        phi_level = level_central_angle_from_ground_arc_m(ground_range_m)
        return level_theta_o_from_central_angle_rad(phi_level)

    if r_s > r_t:
        if ground_range_m == 0.0:
            return 0.0

        phi_max = math.pi / 2.0 - math.asin(r_t / r_s)
        phi = ground_range_m / R_EARTH_M
        if phi >= phi_max:
            raise ParameterBoundsError(
                what=(
                    f"theta_o_from_ground_range_m: ground_range_m = {ground_range_m:.1f} m "
                    f"(central angle {math.degrees(phi):.3f}°) is at or beyond the "
                    f"target's horizon for h_sensor_m = {h_sensor_m:.1f} m"
                ),
                why=(
                    "Beyond the horizon arc the observer zenith at the target "
                    "reaches π/2 and the LOS no longer clears the surface."
                ),
                action=(
                    f"Reduce ground_range_m below {R_EARTH_M * phi_max:.1f} m "
                    f"(the horizon arc for this altitude pair), or increase h_sensor_m."
                ),
                context={
                    "ground_range_m": ground_range_m,
                    "max_ground_range_m": R_EARTH_M * phi_max,
                    "h_sensor_m": h_sensor_m,
                    "h_target_m": h_target_m,
                },
            )

        d_sq = r_t * r_t + r_s * r_s - 2.0 * r_t * r_s * math.cos(phi)
        d = math.sqrt(d_sq)
        cos_interior = (r_t * r_t + d_sq - r_s * r_s) / (2.0 * r_t * d)
        # Clamp for float round-off at the nadir extreme (cos → −1).
        cos_interior = max(-1.0, min(1.0, cos_interior))
        return float(math.pi - math.acos(cos_interior))

    # Up-looking (r_s < r_t): the sensor is the lower endpoint.
    if ground_range_m == 0.0:
        return math.pi
    phi = ground_range_m / R_EARTH_M
    if phi >= math.pi:
        raise ParameterBoundsError(
            what=(
                f"theta_o_from_ground_range_m: ground_range_m = {ground_range_m:.1f} m "
                f"(central angle {math.degrees(phi):.3f}°) exceeds half the Earth's "
                f"circumference"
            ),
            why="A central angle of π rad is the antipode; there is nothing beyond it.",
            action=f"Reduce ground_range_m below {R_EARTH_M * math.pi:.1f} m.",
            context={"ground_range_m": ground_range_m},
        )
    d_sq = r_t * r_t + r_s * r_s - 2.0 * r_t * r_s * math.cos(phi)
    d = math.sqrt(d_sq)
    tangent_length = math.sqrt(r_t * r_t - r_s * r_s)
    if d > tangent_length:
        raise ParameterBoundsError(
            what=(
                f"theta_o_from_ground_range_m: ground_range_m = {ground_range_m:.1f} m "
                f"implies a chord of {d:.1f} m between h_sensor_m = {h_sensor_m:.1f} m "
                f"and h_target_m = {h_target_m:.1f} m, longer than the tangent length "
                f"{tangent_length:.1f} m"
            ),
            why=(
                "Past the tangent length the up-looking path's closest approach to "
                "the Earth lies BETWEEN the endpoints, so the target-side zenith θ_o "
                "no longer identifies it uniquely — the forward solver resolves θ_o "
                "to the near root, which is a different, shorter path."
            ),
            action=(
                "Enter this near-level geometry from its lower endpoint with "
                "solve_from_lower_zenith(zeta_low_rad, h_low_m, h_high_m), which is "
                "unambiguous by construction (ADR-0011 decision 3)."
            ),
            context={
                "ground_range_m": ground_range_m,
                "chord_m": d,
                "tangent_length_m": tangent_length,
                "h_sensor_m": h_sensor_m,
                "h_target_m": h_target_m,
            },
        )
    cos_interior = (r_t * r_t + d_sq - r_s * r_s) / (2.0 * r_t * d)
    cos_interior = max(-1.0, min(1.0, cos_interior))
    return float(math.pi - math.acos(cos_interior))


def solve_from_lower_zenith(
    zeta_low_rad: float, h_low_m: float, h_high_m: float
) -> LowerEndpointSolution:
    """Solve the triangle from the path's LOWER endpoint (ADR-0011 §3).

    A ray leaving the lower endpoint at zenith ``ζ_low`` crosses the higher
    shell **exactly once**, which is what makes this door unambiguous where
    a θ_o (upper-endpoint) entry is not:

    * ``ζ_low ≤ π/2`` — the ray ascends monotonically.
    * ``ζ_low > π/2`` — the ray descends to a perigee and climbs back out
      (interior-tangent topology; the horizon guard applies), still meeting
      the upper shell once.

    Solution (law of sines / cosines, roles swapped relative to the
    down-looking family)::

        ζ_up = asin( (r_low / r_up) · sin(ζ_low) )      (acute, ascending)
        φ    = ζ_low − ζ_up
        d    = −r_low cos(ζ_low) + √( r_low² cos²(ζ_low) + r_up² − r_low² )

    ``r_up > r_low`` guarantees a single positive root.  The reverse ray at
    the upper endpoint has zenith ``π − ζ_up``, which is ``theta_o_rad`` on
    the returned record: when the upper endpoint is the **target**, that is
    the canonical ``geometry.path_zenith_rad`` of the up-looking scene.

    The horizon guard runs on the resulting segment (warn / raise per
    :func:`check_horizon_guard`).
    """
    where = "solve_from_lower_zenith"
    if not (0.0 <= zeta_low_rad <= math.pi):
        raise ParameterBoundsError(
            what=(
                f"{where}: zeta_low_rad = {zeta_low_rad} rad "
                f"({math.degrees(zeta_low_rad):.3f}°) is outside [0, π]"
            ),
            why="A zenith angle at the lower endpoint lies in [0, π] by definition.",
            action="Wrap zeta_low_rad into [0, π] rad (0–180°).",
            context={"zeta_low_rad": zeta_low_rad},
        )
    if h_low_m < 0.0:
        raise ParameterBoundsError(
            what=f"{where}: h_low_m = {h_low_m} m is negative",
            why="Endpoint altitudes must be at or above MSL.",
            action="Set h_low_m >= 0.",
            context={"h_low_m": h_low_m},
        )
    if h_high_m <= h_low_m:
        raise ParameterBoundsError(
            what=(f"{where}: h_high_m = {h_high_m} m is not above h_low_m = {h_low_m} m"),
            why=(
                "This solver is keyed to the path's lower endpoint, so the second "
                "altitude must be the higher one.  Equal altitudes are the level "
                "case and have their own central-angle form."
            ),
            action=(
                "Swap the arguments, or use level_central_angle_from_slant_m / "
                "level_theta_o_from_central_angle_rad for an equal-altitude path."
            ),
            context={"h_low_m": h_low_m, "h_high_m": h_high_m},
        )

    r_low = R_EARTH_M + h_low_m
    r_up = R_EARTH_M + h_high_m
    cos_low = math.cos(zeta_low_rad)
    disc = (r_low * cos_low) ** 2 + (r_up * r_up - r_low * r_low)
    # r_up > r_low ⇒ disc > 0 and the '+' root is the unique positive one.
    d = -r_low * cos_low + math.sqrt(disc)
    zeta_up = math.asin(min(1.0, (r_low / r_up) * math.sin(zeta_low_rad)))
    phi = zeta_low_rad - zeta_up

    _check_segment(
        zeta_low_rad=zeta_low_rad,
        r_low=r_low,
        slant_m=d,
        where=where,
        context={"h_low_m": h_low_m, "h_high_m": h_high_m, "zeta_low_rad": zeta_low_rad},
    )

    return LowerEndpointSolution(
        zeta_low_rad=float(zeta_low_rad),
        zeta_up_rad=float(zeta_up),
        theta_o_rad=float(math.pi - zeta_up),
        slant_range_m=float(d),
        central_angle_rad=float(phi),
        eta_int_rad=float(zeta_up),
        h_low_m=float(h_low_m),
        h_up_m=float(h_high_m),
    )


# ---------------------------------------------------------------------------
# Level (equal-altitude) paths — central-angle form
# ---------------------------------------------------------------------------


def level_central_angle_from_slant_m(slant_m: float, h_m: float) -> float:
    """Central angle φ [rad] of a level path of chord length ``slant_m``.

    Both endpoints sit at radius ``r = R_E + h``; the chord subtends
    ``φ = 2 asin(d / 2r)``.
    """
    if h_m < 0.0:
        raise ParameterBoundsError(
            what=f"level_central_angle_from_slant_m: h_m = {h_m} m is negative",
            why="Endpoint altitude must be at or above MSL.",
            action="Set h_m >= 0.",
            context={"h_m": h_m},
        )
    if slant_m < 0.0:
        raise ParameterBoundsError(
            what=f"level_central_angle_from_slant_m: slant_m = {slant_m} m is negative",
            why="A chord length is a distance; it cannot be negative.",
            action="Set slant_m >= 0.",
            context={"slant_m": slant_m},
        )
    r = R_EARTH_M + h_m
    ratio = slant_m / (2.0 * r)
    if ratio > 1.0:
        raise ParameterBoundsError(
            what=(
                f"level_central_angle_from_slant_m: slant_m = {slant_m} m exceeds the "
                f"diameter {2.0 * r} m of the level shell at h_m = {h_m} m"
            ),
            why="No chord of a circle can be longer than its diameter.",
            action=f"Reduce slant_m below {2.0 * r} m.",
            context={"slant_m": slant_m, "h_m": h_m},
        )
    return float(2.0 * math.asin(ratio))


def level_central_angle_from_ground_arc_m(arc_m: float) -> float:
    """Central angle φ [rad] subtended by a surface arc ``arc_m`` [m].

    The ground-range convention throughout RADIANT measures the arc on the
    Earth's surface (radius ``R_E``), so ``φ = arc / R_E`` independently of
    the endpoints' common altitude.
    """
    if arc_m < 0.0:
        raise ParameterBoundsError(
            what=f"level_central_angle_from_ground_arc_m: arc_m = {arc_m} m is negative",
            why="A surface arc is a distance; it cannot be negative.",
            action="Set arc_m >= 0.",
            context={"arc_m": arc_m},
        )
    return float(arc_m / R_EARTH_M)


def level_slant_range_from_central_angle_m(central_angle_rad: float, h_m: float) -> float:
    """Chord length [m] of a level path subtending ``central_angle_rad``.

    ``d = 2 r sin(φ/2)`` with ``r = R_E + h``.
    """
    _validate_central_angle(central_angle_rad, "level_slant_range_from_central_angle_m")
    if h_m < 0.0:
        raise ParameterBoundsError(
            what=f"level_slant_range_from_central_angle_m: h_m = {h_m} m is negative",
            why="Endpoint altitude must be at or above MSL.",
            action="Set h_m >= 0.",
            context={"h_m": h_m},
        )
    r = R_EARTH_M + h_m
    return float(2.0 * r * math.sin(central_angle_rad / 2.0))


def level_theta_o_from_central_angle_rad(central_angle_rad: float) -> float:
    """Observer zenith θ_o [rad] at either endpoint of a level path.

    The triangle is isoceles, so the two base angles are equal and
    ``θ_o = π/2 + φ/2`` at **both** endpoints: each looks slightly *down*
    at the other, because the chord sags below the constant-altitude arc.
    """
    _validate_central_angle(central_angle_rad, "level_theta_o_from_central_angle_rad")
    return float(math.pi / 2.0 + central_angle_rad / 2.0)


def _validate_central_angle(central_angle_rad: float, where: str) -> None:
    if not (0.0 <= central_angle_rad <= math.pi):
        raise ParameterBoundsError(
            what=(
                f"{where}: central_angle_rad = {central_angle_rad} rad "
                f"({math.degrees(central_angle_rad):.3f}°) is outside [0, π]"
            ),
            why="A central angle between two points on a sphere lies in [0, π].",
            action="Wrap central_angle_rad into [0, π] rad (0–180°).",
            context={"central_angle_rad": central_angle_rad},
        )


# ---------------------------------------------------------------------------
# Horizon guard (plan §8.3 addendum, refines ADR-0011 decision 6)
# ---------------------------------------------------------------------------


def horizon_band_action(zenith_low_rad: float) -> tuple[str, float]:
    """Angular-band verdict for an endpoint-minimum path.

    Returns ``(action, band_rad)`` where ``band_rad = |ζ_low − π/2|`` [rad]
    and action is ``"raise"`` inside :data:`GUARD_HARD_RAD`, ``"warn"``
    inside :data:`GUARD_WARN_RAD`, else ``"clean"``.

    The comparison is done in radians end to end (Rule 2, CU-222); callers
    that print the band convert with ``math.degrees`` at the format string.
    Both boundaries carry :data:`_GUARD_BAND_EPS_RAD` of slack so a band
    landing *exactly* on a ratified threshold falls on the permissive side
    regardless of how the caller's angle was constructed.
    """
    band_rad = abs(zenith_low_rad - math.pi / 2.0)
    if band_rad < GUARD_HARD_RAD - _GUARD_BAND_EPS_RAD:
        return "raise", band_rad
    if band_rad < GUARD_WARN_RAD - _GUARD_BAND_EPS_RAD:
        return "warn", band_rad
    return "clean", band_rad


def _classify_segment(zenith_low_rad: float, r_low: float, slant_m: float) -> HorizonGuardResult:
    """Classify a segment given its lower-endpoint zenith, radius, and length."""
    h_low_m = r_low - R_EARTH_M
    if slant_m <= 0.0:
        return HorizonGuardResult(
            topology=_TOPOLOGY_INTERIOR,
            action="clean",
            zenith_low_rad=zenith_low_rad,
            h_low_m=h_low_m,
            slant_range_m=slant_m,
            dh_m=0.0,
            detail="zero-length path — no atmosphere is traversed",
        )
    # Foot of the perpendicular from the Earth centre, measured from the
    # LOWER endpoint along the segment: t_foot = −r_low cos(ζ_low).
    t_foot = -r_low * math.cos(zenith_low_rad)
    if 0.0 < t_foot < slant_m:
        # Interior tangent.  dh = r_low(1 − sin ζ_low), written as a versine
        # to avoid catastrophic cancellation for near-horizontal paths.
        dh = 2.0 * r_low * math.sin(0.5 * (zenith_low_rad - math.pi / 2.0)) ** 2
        if dh < GUARD_DH_CLEAN_M:
            action = "clean"
        elif dh <= GUARD_DH_RAISE_M:
            action = "warn"
        else:
            action = "raise"
        detail = (
            f"interior tangent point {dh:.1f} m below the lower endpoint "
            f"({h_low_m:.1f} m MSL); tangent altitude {h_low_m - dh:.1f} m"
        )
        return HorizonGuardResult(
            topology=_TOPOLOGY_INTERIOR,
            action=action,
            zenith_low_rad=zenith_low_rad,
            h_low_m=h_low_m,
            slant_range_m=slant_m,
            dh_m=dh,
            detail=detail,
        )
    action, band_rad = horizon_band_action(zenith_low_rad)
    detail = (
        f"path leaves its lower endpoint ({h_low_m:.1f} m MSL) at zenith "
        f"{math.degrees(zenith_low_rad):.4f}°, i.e. {math.degrees(band_rad):.4f}° "
        f"from the geometric horizontal"
    )
    return HorizonGuardResult(
        topology=_TOPOLOGY_ENDPOINT_MIN,
        action=action,
        zenith_low_rad=zenith_low_rad,
        h_low_m=h_low_m,
        slant_range_m=slant_m,
        band_rad=band_rad,
        detail=detail,
    )


def classify_horizon_topology(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0
) -> HorizonGuardResult:
    """Classify the sensor↔target segment against the horizon guard.

    Two topologies, per the plan §8.3 addendum (owner, 2026-07-26):

    * **endpoint_minimum** — the perpendicular from the Earth centre falls
      outside the segment, so the closest approach to the surface is the
      lower endpoint.  Guarded by the **angular bands** at that endpoint:
      inside ±:data:`GUARD_HARD_RAD` of the horizontal → ``raise``; out to
      ±:data:`GUARD_WARN_RAD` → ``warn``; beyond → ``clean``.
    * **interior_tangent** — the perpendicular falls *on* the segment, so
      the ray dips to a tangent point between the endpoints (every level
      and near-level arm).  Guarded by the **tangent-height depression**
      ``Δh = r_low (1 − sin ζ_low) ≈ L² / 8R_E``: below
      :data:`GUARD_DH_CLEAN_M` → ``clean``; out to
      :data:`GUARD_DH_RAISE_M` → ``warn``; beyond → ``raise`` (limb-like
      transit, excluded for v1.x).

    A pure angular test over-rejects benign short horizontal paths (two
    8 km-separated towers sit at θ_o = 90.04° with Δh = 1.3 m) and a blanket
    equal-altitude exemption under-rejects long transits (500 km at 5 km
    altitude has Δh ≈ 4.9 km); the topology split is what makes the guard
    continuous between them.

    This is classification only — it never warns or raises.  Use
    :func:`check_horizon_guard` to apply the verdict.
    """
    _validate_theta_o(theta_o_rad, "classify_horizon_topology")
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "classify_horizon_topology")
    _validate_hemisphere(theta_o_rad, h_sensor_m, h_target_m, "classify_horizon_topology")
    d = slant_range_from_theta_o_m(theta_o_rad, h_sensor_m, h_target_m)
    if r_s >= r_t:
        # Target (or either endpoint, when level) is the lower endpoint and
        # θ_o is already its zenith.
        return _classify_segment(theta_o_rad, r_t, d)
    # Up-looking: the sensor is the lower endpoint; the zenith there is the
    # supplement of the interior angle η.
    eta = eta_from_theta_o(theta_o_rad, h_sensor_m, h_target_m)
    return _classify_segment(math.pi - eta, r_s, d)


def _check_segment(
    *,
    zeta_low_rad: float,
    r_low: float,
    slant_m: float,
    where: str,
    context: dict[str, float],
) -> HorizonGuardResult:
    """Apply the guard verdict for an already-resolved segment."""
    result = _classify_segment(zeta_low_rad, r_low, slant_m)
    payload: dict[str, Any] = dict(context)
    payload.update(
        {
            "topology": result.topology,
            "slant_range_m": result.slant_range_m,
            "guard_hard_rad": GUARD_HARD_RAD,
            "guard_warn_rad": GUARD_WARN_RAD,
            "guard_dh_clean_m": GUARD_DH_CLEAN_M,
            "guard_dh_raise_m": GUARD_DH_RAISE_M,
        }
    )
    if result.dh_m is not None:
        payload["tangent_depression_m"] = result.dh_m
        # CU-269: size the refraction this guard excludes, so every consumer does
        # not have to re-derive it. Under the standard effective-radius model the
        # tangent depression of a fixed geometry scales as 1/k, so a k = 4/3 ray
        # bottoms out dh/k below its endpoints instead of dh: the peak
        # sampling-altitude error is dh·(1 - 1/k), and the path-mean is 2/3 of that
        # (the depression profile is parabolic about the tangent point).
        dh_refracted = result.dh_m / GUARD_REFRACTION_K
        dh_peak_error = result.dh_m - dh_refracted
        payload["refraction_k"] = GUARD_REFRACTION_K
        payload["tangent_depression_refracted_m"] = dh_refracted
        payload["refraction_sampling_error_peak_m"] = dh_peak_error
        payload["refraction_sampling_error_mean_m"] = (2.0 / 3.0) * dh_peak_error
    if result.band_rad is not None:
        payload["band_rad"] = result.band_rad

    if result.action == "raise":
        if result.topology == _TOPOLOGY_INTERIOR:
            raise ParameterBoundsError(
                what=(
                    f"{where}: near-horizontal path rejected — {result.detail}, "
                    f"deeper than the {GUARD_DH_RAISE_M:.0f} m tangent-depression limit"
                ),
                why=(
                    "A path whose tangent point sinks that far below its endpoints is "
                    "a limb-like transit: it samples air far denser than either "
                    "endpoint and its bending is dominated by refraction, which v1.x "
                    "does not model (ADR-0011 decision 5 — limb paths declined, "
                    "guarded rather than approximated)."
                ),
                action=(
                    "Shorten the path, raise both endpoints, or tilt the geometry "
                    "away from the horizontal until the tangent depression is below "
                    f"{GUARD_DH_RAISE_M:.0f} m."
                ),
                context=payload,
            )
        raise ParameterBoundsError(
            what=(
                f"{where}: near-horizontal path rejected — {result.detail}, inside the "
                f"±{math.degrees(GUARD_HARD_RAD):g}° hard horizon guard"
            ),
            why=(
                "Within a half-degree of the geometric horizontal, atmospheric "
                "refraction dominates the path geometry and v1.x has no refraction "
                "model, so any number returned here would be quietly wrong "
                "(ADR-0011 decision 6)."
            ),
            action=(
                f"Move the path more than {math.degrees(GUARD_WARN_RAD):g}° off the "
                "horizontal at its "
                "lower endpoint, or change the altitudes so the geometry is no longer "
                "grazing."
            ),
            context=payload,
        )
    if result.action == "warn":
        # CU-269: a caveat the reader can act on has to carry its size. Where the
        # path has a tangent point, quote what k = 4/3 refraction would have done
        # to it; where it does not (an endpoint-minimum slant), say so rather than
        # quoting a number that does not apply.
        if result.dh_m is not None:
            dh_refracted = result.dh_m / GUARD_REFRACTION_K
            mean_error = (2.0 / 3.0) * (result.dh_m - dh_refracted)
            size = (
                f" Size of the omission: under the standard k = {GUARD_REFRACTION_K:.3g} "
                f"effective-radius model this path would bottom out at "
                f"{dh_refracted:.1f} m rather than {result.dh_m:.1f} m below its lower "
                f"endpoint, i.e. the air this path is sampled through sits on average "
                f"~{mean_error:.1f} m lower than the true refracted ray's — so the band "
                "transmittance is biased slightly low."
            )
        else:
            size = (
                " This segment has no interior tangent point (its closest approach is "
                "its lower endpoint), so the refraction omission is a path-length "
                "effect rather than a sampling-altitude one and is not sized here."
            )
        warnings.warn(
            f"{where}: near-horizontal path — {result.detail}. Computing anyway, but "
            "atmospheric refraction is NOT modelled in v1.x and is the dominant "
            "geometric error in this band (hard guard at "
            f"±{math.degrees(GUARD_HARD_RAD):g}° / {GUARD_DH_RAISE_M:.0f} m tangent depression; "
            f"thresholds provisional pending Phase 2 MODTRAN calibration).{size}",
            UserWarning,
            stacklevel=3,
        )
    return result


def check_horizon_guard(
    theta_o_rad: float,
    h_sensor_m: float,
    h_target_m: float = 0.0,
    *,
    where: str = "check_horizon_guard",
) -> HorizonGuardResult:
    """Classify and **apply** the horizon guard for a sensor↔target segment.

    Emits a quantified :class:`UserWarning` in the shoulder band and raises
    :class:`~radiant.core.parameters.ParameterBoundsError` inside the hard
    band (Rule 17 — no silent degradation where refraction is unmodelled).
    Returns the :class:`HorizonGuardResult` when the path is admissible.
    """
    result = classify_horizon_topology(theta_o_rad, h_sensor_m, h_target_m)
    return _check_segment(
        zeta_low_rad=result.zenith_low_rad,
        r_low=R_EARTH_M + result.h_low_m,
        slant_m=result.slant_range_m,
        where=where,
        context={
            "theta_o_rad": theta_o_rad,
            "h_sensor_m": h_sensor_m,
            "h_target_m": h_target_m,
        },
    )
