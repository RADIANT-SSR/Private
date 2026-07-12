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
"""

from __future__ import annotations

import math
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
    slant_range_from_theta_o_m,
    theta_o_from_ground_range_m,
)
from radiant.geometry.errors import GeometrySpecificationError

# Agreement tolerance between redundant mode entries (ADR-0006 rule 2).
_REL_TOL = 0.01
_ABS_FLOOR_RAD = 1e-6


@dataclass(frozen=True, kw_only=True)
class ViewingResolution:
    """Canonical viewing geometry after mode resolution."""

    mode: str  # which entry resolved theta_o
    theta_o_rad: float
    eta_rad: float
    slant_range_m: float
    ground_range_m: float
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


def resolve_viewing(params: ParameterSet) -> ViewingResolution:
    """Resolve the viewing-geometry family (modes V1–V4) to canonical θ_o.

    ``geometry.sensor_altitude_m`` is the anchor (required parameter);
    every angle entry is converted to an implied target-side zenith and
    checked for agreement per ADR-0006 rule 2.
    """
    h_sensor: float = params.get("geometry.sensor_altitude_m")
    h_target: float = params.get("geometry.target_altitude_m")

    candidates: list[tuple[str, float]] = []
    if _provided(params, "geometry.path_zenith_rad"):
        candidates.append(
            ("geometry.path_zenith_rad", float(params.get("geometry.path_zenith_rad")))
        )
    if _provided(params, "geometry.sensor_off_nadir_rad"):
        eta_in = float(params.get("geometry.sensor_off_nadir_rad"))
        candidates.append(
            (
                "geometry.sensor_off_nadir_rad",
                theta_o_from_eta(eta_in, h_sensor, h_target),
            )
        )
    if _provided(params, "geometry.ground_range_m"):
        candidates.append(
            (
                "geometry.ground_range_m",
                theta_o_from_ground_range_m(
                    float(params.get("geometry.ground_range_m")), h_sensor, h_target
                ),
            )
        )
    if _provided(params, "geometry.elevation_angle_rad"):
        candidates.append(
            (
                "geometry.elevation_angle_rad",
                math.pi / 2.0 - float(params.get("geometry.elevation_angle_rad")),
            )
        )

    if not candidates:
        theta_o = float(params.get("geometry.path_zenith_rad"))  # schema default: nadir
        mode = "path_zenith (default)"
    elif len(candidates) == 1:
        mode, theta_o = candidates[0]
    else:
        first = candidates[0][1]
        if not all(_agree(first, v) for _, v in candidates[1:]):
            _raise_disagreement("viewing", candidates, "rad")
        mode = " + ".join(name for name, _ in candidates) + " (consistent)"
        theta_o = first

    eta = eta_from_theta_o(theta_o, h_sensor, h_target) if theta_o > 0.0 else 0.0
    slant = slant_range_from_theta_o_m(theta_o, h_sensor, h_target)
    ground = ground_range_from_theta_o_m(theta_o, h_sensor, h_target) if theta_o > 0.0 else 0.0
    return ViewingResolution(
        mode=mode,
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
