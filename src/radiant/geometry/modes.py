"""Input-mode detection and resolution to the canonical geometry.

The user may express the scene in any one of several modes per family
(viewing: V0–V4, V6; solar: S0–S3 — RADIANT_Geometry.md §input-modes,
ADR-0006).  This module detects which mode the user's inputs select and
resolves them to the canonical internal representation:

    viewing:  theta_o (target-side path zenith), eta, slant range,
              ground range, altitudes
    solar:    theta_s, delta_phi (or None/None at night)
    kinematics: ground-track speed (+ orbital period for circular orbits)

Rules (normative, ADR-0006):
  1. Mode detection is by provenance — a parameter left at DEFAULT
     provenance was not provided and never counts as user intent.
  2. Redundant user-set entries for the same canonical quantity must
     agree within 1 % (relative, with a 1e-6 rad absolute floor for
     angles) or resolution raises an actionable
     :class:`~radiant.geometry.errors.GeometrySpecificationError`.
  3. Every derived quantity is published to ``stage_outputs`` by
     :class:`~radiant.geometry.stage.GeometryStage` with its mode label,
     so ``result.inspect()`` shows how each number was produced.
  4. No user-set entry at all falls back to the documented defaults
     (nadir view, 0.5 rad solar zenith in day mode) — never a silent NaN.

Angle-entry semantics (ADR-0011 decision 3, plan Phase 1)
---------------------------------------------------------
Since the geometry core became direction-general, **every viewing angle a
user enters is referenced to the path's LOWER endpoint**:

* ``path_zenith_rad`` (V1) is the LOS zenith *at the lower endpoint*;
* ``sensor_off_nadir_rad`` (V2) is an off-**boresight** angle whose
  reference axis is resolved from the altitudes — nadir when the sensor is
  the upper endpoint, zenith when it is the lower one;
* ``elevation_angle_rad`` (V4) is the elevation above the horizontal *at
  the lower endpoint*, and may now be negative (the path leaves its lower
  endpoint on a descending shoulder);
* ``ground_range_m`` (V3) is direction-free — the surface arc fixes the
  central angle whichever endpoint is higher.

This is exactly back-compatible: in every pre-ADR-0011 scene the sensor is
strictly above the target, so the target *is* the lower endpoint and the
entered angle is the canonical target-side zenith θ_o, unchanged.  For an
up-looking scene the sensor is the lower endpoint and θ_o is **derived**
(``θ_o = π − ζ_up``); the mode label says so.

The canonical published quantity remains θ_o on the closed domain [0, π]
(π = target directly overhead), and the resolved values are the ones the
horizon guard in :class:`~radiant.core.los_geometry.LineOfSightGeometry`
then judges.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.orbit import ground_track_speed_m_s, orbital_period_s
from radiant.core.parameters import ParameterSet, Provenance
from radiant.core.solar_geometry import (
    local_solar_time_from_ltan,
    solar_zenith_angle_rad,
)
from radiant.core.viewing_triangle import (
    eta_from_theta_o,
    ground_range_from_theta_o_m,
    level_central_angle_from_slant_m,
    level_theta_o_from_central_angle_rad,
    slant_range_from_theta_o_m,
    solve_from_lower_zenith,
    theta_o_from_ground_range_m,
)
from radiant.geometry.errors import GeometrySpecificationError

# Agreement tolerance between redundant mode entries (ADR-0006 rule 2).
_REL_TOL = 0.01
_ABS_FLOOR_RAD = 1e-6


@dataclass(frozen=True, kw_only=True)
class ViewingResolution:
    """Canonical viewing geometry after mode resolution.

    ``theta_o_rad`` is the target-side observer zenith on the closed domain
    [0, π] — acute for a down-looking scene, obtuse for an up-looking one,
    ``π/2 + φ/2`` for a level (equal-altitude) path.  Up-looking is legal
    since ADR-0011 (the 2026-07-11 "v1 has no uplooking geometry" ruling is
    superseded).

    The triangle-derived fields (``eta_rad``, ``slant_range_m``,
    ``ground_range_m``) are ``None`` in exactly one case: **coincident
    endpoints** — equal altitudes with no separation information at all
    (no angle entry, no ground range, no target range), where the two
    endpoints are the same point and there is no path.  That is the
    φ → 0 limit of the level solution, not a carve-out: an equal-altitude
    scene that carries *any* separation (a lab bench with
    ``geometry.target_range_m``, a tower pair with ``ground_range_m``, an
    elevation entry) resolves to the full horizontal triangle (ADR-0011
    guardrail G4 — the collocated no-triangle carve-out is retired here).

    ``direction`` is derived from the altitude pair, never a user switch
    (ADR-0011 decision 1).
    """

    mode: str  # which entry resolved theta_o
    direction: str  # "down" | "up" | "level" — derived from the altitudes
    theta_o_rad: float
    eta_rad: float | None
    slant_range_m: float | None
    ground_range_m: float | None
    h_sensor_m: float
    h_target_m: float


@dataclass(frozen=True, kw_only=True)
class SolarResolution:
    """Canonical solar geometry after mode resolution."""

    mode: str
    theta_s_rad: float | None
    delta_phi_rad: float | None


@dataclass(frozen=True, kw_only=True)
class KinematicsResolution:
    """Canonical platform kinematics after mode resolution."""

    mode: str
    ground_speed_m_s: float
    orbital_period_s: float | None


def _provided(params: ParameterSet, name: str) -> bool:
    """True when *name* resolved from an explicit input (not its default)."""
    try:
        rv = params.get_resolved(name)
    except KeyError:
        return False
    return rv.provenance is not Provenance.DEFAULT


def _agree(a: float, b: float) -> bool:
    """Rule-2 agreement check: 1% relative with an absolute floor."""
    return abs(a - b) <= max(_ABS_FLOOR_RAD, _REL_TOL * max(abs(a), abs(b)))


def _raise_disagreement(family: str, entries: list[tuple[str, float]], unit: str) -> None:
    listing = "; ".join(
        f"{name} ⇒ {value:.6g} {unit}" + (f" ({math.degrees(value):.3f}°)" if unit == "rad" else "")
        for name, value in entries
    )
    raise GeometrySpecificationError(
        what=(
            f"Over-specified {family} geometry: {len(entries)} inputs imply "
            f"disagreeing values — {listing}"
        ),
        why=(
            "Multiple input modes were set for the same canonical quantity "
            "and they disagree by more than 1%. RADIANT cannot know which "
            "one describes the intended scene."
        ),
        action=(
            "Set exactly one of these parameters (the others derive from "
            "it), or make the redundant values consistent."
        ),
        context=dict(entries),
    )


def viewing_direction(h_sensor_m: float, h_target_m: float) -> str:
    """Derived LOS direction from the altitude pair (ADR-0011 decision 1).

    ``"down"`` when the sensor is strictly above the target (every
    pre-ADR-0011 scene), ``"up"`` when it is strictly below, ``"level"``
    when the altitudes are equal.  Never a user switch.
    """
    if h_sensor_m > h_target_m:
        return "down"
    if h_sensor_m < h_target_m:
        return "up"
    return "level"


#: Mode-label suffix naming the endpoint an entered angle was read at.
#: Empty for the down-looking case so every existing label — and the
#: manifest round-trip test that pins it — is unchanged (zero drift).
_DIRECTION_NOTE: dict[str, str] = {
    "down": "",
    "up": " (up-looking — angle at the sensor, the lower endpoint)",
    "level": " (level path — angle at either endpoint)",
}


def _theta_o_from_lower_zenith(
    zeta_low_rad: float, direction: str, h_sensor: float, h_target: float
) -> float:
    """Canonical θ_o from a zenith angle entered at the path's LOWER endpoint.

    ADR-0011 decision 3.  Down-looking and level paths have the target at
    (or level with) the lower endpoint, so the entered angle **is** θ_o and
    the historical expression is untouched.  Up-looking paths are solved
    from the sensor end, which is unambiguous by construction, and θ_o is
    derived as ``π − ζ_up``.
    """
    if direction == "up":
        return solve_from_lower_zenith(zeta_low_rad, h_sensor, h_target).theta_o_rad
    return zeta_low_rad


def resolve_viewing(params: ParameterSet) -> ViewingResolution:
    """Resolve the viewing-geometry family (modes V1–V4) to canonical θ_o.

    ``geometry.sensor_altitude_m`` is the anchor (required parameter);
    every angle entry is read at the path's lower endpoint (ADR-0011
    decision 3), converted to an implied target-side zenith θ_o, and
    checked for agreement per ADR-0006 rule 2 — the agreement check is
    unchanged in form, only its inputs are now direction-aware.
    """
    h_sensor: float = params.get("geometry.sensor_altitude_m")
    h_target: float = params.get("geometry.target_altitude_m")
    direction = viewing_direction(h_sensor, h_target)

    candidates: list[tuple[str, float]] = []
    if _provided(params, "geometry.path_zenith_rad"):
        candidates.append(
            (
                "geometry.path_zenith_rad",
                _theta_o_from_lower_zenith(
                    float(params.get("geometry.path_zenith_rad")), direction, h_sensor, h_target
                ),
            )
        )
    if _provided(params, "geometry.sensor_off_nadir_rad"):
        eta_in = float(params.get("geometry.sensor_off_nadir_rad"))
        # V2 is an off-BORESIGHT angle: the reference axis is the sensor's
        # nadir when the sensor is the upper endpoint (the historical
        # off-nadir look angle, converted by the sine rule exactly as
        # before), and the sensor's zenith when it is the lower endpoint —
        # in which case the entered angle already *is* ζ_low.
        candidates.append(
            (
                "geometry.sensor_off_nadir_rad",
                theta_o_from_eta(eta_in, h_sensor, h_target)
                if direction == "down"
                else _theta_o_from_lower_zenith(eta_in, direction, h_sensor, h_target),
            )
        )
    if _provided(params, "geometry.ground_range_m"):
        # V3 is direction-free: the surface arc fixes the central angle
        # Δ = arc / R_E whichever endpoint is higher, and the solver picks
        # the triangle branch from the altitude ordering.
        candidates.append(
            (
                "geometry.ground_range_m",
                theta_o_from_ground_range_m(
                    float(params.get("geometry.ground_range_m")), h_sensor, h_target
                ),
            )
        )
    if _provided(params, "geometry.elevation_angle_rad"):
        # V4: elevation above the horizontal AT THE LOWER ENDPOINT.  A
        # negative elevation is legal since ADR-0011 — the path leaves its
        # lower endpoint on a descending shoulder (ζ_low > π/2); whether
        # that is admissible is the horizon guard's call, not the schema's.
        candidates.append(
            (
                "geometry.elevation_angle_rad",
                _theta_o_from_lower_zenith(
                    math.pi / 2.0 - float(params.get("geometry.elevation_angle_rad")),
                    direction,
                    h_sensor,
                    h_target,
                ),
            )
        )

    # A level path with no angle entry at all still has a triangle whenever
    # the user gave a separation: the chord (V0 geometry.target_range_m)
    # fixes the central angle directly, φ = 2·asin(d / 2r).  This is what
    # subsumes the old collocated no-triangle carve-out (guardrail G4).
    chord_m = float(params.get("geometry.target_range_m"))
    level_no_angle = direction == "level" and not candidates
    level_from_chord = level_no_angle and chord_m > 0.0
    # Coincident endpoints: equal altitudes with no separation given at all.
    # The φ → 0 limit of the level solution — θ_o = π/2, zero slant, zero
    # arc — so there is no path to publish ranges for.  Downstream consumers
    # keep their None-handling (PerformanceStage skips the ground-projection
    # metrics for exactly this reason).
    coincident = level_no_angle and chord_m <= 0.0

    if coincident:
        theta_o = math.pi / 2.0
        mode = "path_zenith (default) (level path — coincident endpoints, zero separation)"
    elif level_from_chord:
        theta_o = level_theta_o_from_central_angle_rad(
            level_central_angle_from_slant_m(chord_m, h_sensor)
        )
        mode = "geometry.target_range_m (level path — chord ⇒ central angle)"
    elif not candidates:
        # Schema default 0.0, read at the lower endpoint: nadir view when
        # the sensor is above (unchanged), target-at-zenith when below.
        theta_o = _theta_o_from_lower_zenith(
            float(params.get("geometry.path_zenith_rad")), direction, h_sensor, h_target
        )
        mode = "path_zenith (default)" + _DIRECTION_NOTE[direction]
    elif len(candidates) == 1:
        mode, theta_o = candidates[0]
        mode += _DIRECTION_NOTE[direction]
    else:
        first = candidates[0][1]
        if not all(_agree(first, v) for _, v in candidates[1:]):
            _raise_disagreement("viewing", candidates, "rad")
        mode = " + ".join(name for name, _ in candidates) + " (consistent)"
        mode += _DIRECTION_NOTE[direction]
        theta_o = first

    eta: float | None
    slant: float | None
    ground: float | None
    if direction == "down":
        # Historical expressions, untouched — every existing golden baseline
        # flows through exactly these three lines (plan §3 principle 3).
        eta = eta_from_theta_o(theta_o, h_sensor, h_target) if theta_o > 0.0 else 0.0
        slant = slant_range_from_theta_o_m(theta_o, h_sensor, h_target)
        ground = ground_range_from_theta_o_m(theta_o, h_sensor, h_target) if theta_o > 0.0 else 0.0
    elif coincident:
        eta = None
        slant = None
        ground = None
    else:
        # Up-looking or a level path with separation: the same triangle read
        # from the other vertex.  θ_o = π (target at the sensor's zenith) is
        # the mirror of the down-looking θ_o = 0 nadir limit and is taken
        # exactly rather than through a 1e-16 sine.
        at_zenith = theta_o >= math.pi
        eta = math.pi if at_zenith else eta_from_theta_o(theta_o, h_sensor, h_target)
        slant = slant_range_from_theta_o_m(theta_o, h_sensor, h_target)
        ground = 0.0 if at_zenith else ground_range_from_theta_o_m(theta_o, h_sensor, h_target)

    return ViewingResolution(
        mode=mode,
        direction=direction,
        theta_o_rad=theta_o,
        eta_rad=eta,
        slant_range_m=slant,
        ground_range_m=ground,
        h_sensor_m=h_sensor,
        h_target_m=h_target,
    )


def _wrap_pi(angle_rad: float) -> float:
    """Wrap an angle into [−π, π] (LineOfSightGeometry azimuth contract)."""
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi


def resolve_solar(params: ParameterSet) -> SolarResolution:
    """Resolve the solar-geometry family (modes S0–S3) to canonical θ_s, Δφ."""
    illumination: str = params.get("geometry.solar_illumination")
    if illumination == "night":
        return SolarResolution(mode="night", theta_s_rad=None, delta_phi_rad=None)

    site_params = (
        "geometry.site_latitude_rad",
        "geometry.day_of_year",
        "geometry.local_solar_time_h",
        "geometry.ltan_h",
    )
    site_active = any(_provided(params, p) for p in site_params)

    candidates: list[tuple[str, float]] = []
    if _provided(params, "geometry.solar_zenith_rad"):
        candidates.append(
            ("geometry.solar_zenith_rad", float(params.get("geometry.solar_zenith_rad")))
        )
    if _provided(params, "geometry.solar_elevation_rad"):
        candidates.append(
            (
                "geometry.solar_elevation_rad",
                math.pi / 2.0 - float(params.get("geometry.solar_elevation_rad")),
            )
        )
    if site_active:
        if _provided(params, "geometry.ltan_h") and _provided(
            params, "geometry.local_solar_time_h"
        ):
            raise GeometrySpecificationError(
                what=(
                    "Both geometry.ltan_h and geometry.local_solar_time_h are set "
                    "— they are mutually exclusive entries for the same quantity"
                ),
                why=(
                    "LTAN is converted to local solar time internally; providing "
                    "both over-specifies the sun's hour angle."
                ),
                action="Set exactly one of ltan_h (sun-sync orbits) or local_solar_time_h.",
                context={
                    "ltan_h": params.get("geometry.ltan_h"),
                    "local_solar_time_h": params.get("geometry.local_solar_time_h"),
                },
            )
        if _provided(params, "geometry.ltan_h"):
            lst = local_solar_time_from_ltan(float(params.get("geometry.ltan_h")))
        else:
            lst = float(params.get("geometry.local_solar_time_h"))
        candidates.append(
            (
                "site+time (S3)",
                solar_zenith_angle_rad(
                    math.degrees(float(params.get("geometry.site_latitude_rad"))),
                    int(params.get("geometry.day_of_year")),
                    lst,
                ),
            )
        )

    if not candidates:
        theta_s = float(params.get("geometry.solar_zenith_rad"))  # schema default
        mode = "solar_zenith (default)"
    elif len(candidates) == 1:
        mode, theta_s = candidates[0]
    else:
        first = candidates[0][1]
        if not all(_agree(first, v) for _, v in candidates[1:]):
            _raise_disagreement("solar", candidates, "rad")
        mode = " + ".join(name for name, _ in candidates) + " (consistent)"
        theta_s = first

    delta_phi = _wrap_pi(float(params.get("geometry.solar_azimuth_rad")))
    return SolarResolution(mode=mode, theta_s_rad=theta_s, delta_phi_rad=delta_phi)


def resolve_kinematics(params: ParameterSet) -> KinematicsResolution:
    """Resolve platform kinematics (mode V6 circular orbit, or direct)."""
    circular: bool = bool(params.get("geometry.circular_orbit"))
    ground_speed_param: float = float(params.get("geometry.ground_speed_m_s"))

    if not circular:
        return KinematicsResolution(
            mode="direct", ground_speed_m_s=ground_speed_param, orbital_period_s=None
        )

    h_sensor: float = params.get("geometry.sensor_altitude_m")
    v_orbit = ground_track_speed_m_s(h_sensor)
    if (
        _provided(params, "geometry.ground_speed_m_s")
        and ground_speed_param > 0.0
        and not _agree(v_orbit, ground_speed_param)
    ):
        raise GeometrySpecificationError(
            what=(
                f"geometry.circular_orbit derives a ground-track speed of "
                f"{v_orbit:.1f} m/s from the {params.get('geometry.sensor_altitude_m'):.0f} m "
                f"altitude, but geometry.ground_speed_m_s is explicitly set to "
                f"{ground_speed_param:.1f} m/s"
            ),
            why=(
                "A circular orbit's ground-track speed is fully determined "
                "by its altitude; a disagreeing explicit speed "
                "over-specifies the kinematics."
            ),
            action=(
                "Remove the explicit geometry.ground_speed_m_s (it will be "
                "derived), or set circular_orbit=false for a non-orbital "
                "platform."
            ),
            context={
                "derived_m_s": v_orbit,
                "explicit_m_s": ground_speed_param,
            },
        )
    return KinematicsResolution(
        mode="circular_orbit",
        ground_speed_m_s=v_orbit,
        orbital_period_s=orbital_period_s(h_sensor),
    )


def check_range_consistency(
    params: ParameterSet,
    viewing: ViewingResolution,
) -> None:
    """CU-093: a user range and a user angle must describe ONE distance.

    ``geometry.target_range_m`` names the sensor→target slant range —
    the same physical quantity the viewing triangle derives from the
    resolved θ_o.  Decision matrix (ADR-0006 rule 2):

    * range user-set AND an angle entry user-set AND the triangle exists
      → the two slant ranges must agree within 1 % or this raises.
    * range user-set with angles left at defaults (mode V0) → the range
      wins for regime/detection purposes; if it disagrees with the
      default-nadir slant by more than 1 %, a ``UserWarning`` is issued
      (Rule 17 — the historical silent disagreement is never silent).
    * no user range → nothing to check.

    On a **level** path with no angle entry the range is not merely a
    consistency partner — it is the separation that builds the triangle
    (``resolve_viewing``'s chord door), so the two agree by construction
    and this check is a no-op there.
    """
    raw_range = float(params.get("geometry.target_range_m"))
    if raw_range <= 0.0 or viewing.slant_range_m is None:
        return
    if _agree(raw_range, viewing.slant_range_m):
        return

    angle_entries = (
        "geometry.path_zenith_rad",
        "geometry.sensor_off_nadir_rad",
        "geometry.ground_range_m",
        "geometry.elevation_angle_rad",
    )
    angle_user_set = any(_provided(params, name) for name in angle_entries)
    if angle_user_set:
        raise GeometrySpecificationError(
            what=(
                f"geometry.target_range_m = {raw_range:.6g} m disagrees with the "
                f"slant range implied by the viewing angles "
                f"({viewing.slant_range_m:.6g} m from {viewing.mode})"
            ),
            why=(
                "Both describe the sensor→target slant range; the chain "
                "cannot use two different distances for one line of sight "
                "(CU-093: regime/detection would use one, GSD/ground "
                "metrics the other)."
            ),
            action=("Set exactly one of them (the other derives), or make them agree within 1%."),
            context={
                "geometry.target_range_m": raw_range,
                "implied_slant_range_m": viewing.slant_range_m,
                "viewing_mode": viewing.mode,
            },
        )
    warnings.warn(
        (
            f"geometry.target_range_m = {raw_range:.6g} m differs from the "
            f"nadir-default slant range ({viewing.slant_range_m:.6g} m at "
            f"h_sensor = {viewing.h_sensor_m:.6g} m). The user range drives "
            f"regime classification and detection range; spatial/ground "
            f"metrics use the default-nadir geometry. Set a viewing angle "
            f"(e.g. geometry.path_zenith_rad or geometry.sensor_off_nadir_rad) "
            f"to make the scene self-consistent (CU-093)."
        ),
        UserWarning,
        stacklevel=2,
    )
