"""Spherical viewing triangle — target-side-zenith (θ_o) solutions.

One geometric model, solved four ways.  The triangle is (Earth centre,
target, sensor) on a spherical Earth:

    r_t = R_E + h_target      (target radius)
    r_s = R_E + h_sensor      (sensor radius)
    θ_o = observer zenith measured AT THE TARGET from local up
    η   = off-nadir look angle measured AT THE SENSOR from local down
    φ   = central angle at the Earth centre
    d   = slant range target ↔ sensor

Interior-angle relations (law of sines / cosines on the triangle):

    sin(η) = (r_t / r_s) · sin(θ_o)                       [law of sines]
    φ      = θ_o − η                                       [angle sum]
    d      = −r_t cos(θ_o) + √(r_t² cos²(θ_o) + r_s² − r_t²)
                                                           [law of cosines]
    ground range (surface arc) = R_E · φ

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

Downlooking only (``h_sensor > h_target``), matching the
``LineOfSightGeometry.theta_o ∈ [0, π/2)`` convention; uplooking geometry
is rejected loudly (matrix decision, owner-ratified 2026-07-11).
"""

from __future__ import annotations

import math

from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError


def _validate_altitudes(h_sensor_m: float, h_target_m: float, where: str) -> tuple[float, float]:
    """Common altitude validation; returns (r_t, r_s)."""
    if h_target_m < 0.0:
        raise ParameterBoundsError(
            what=f"{where}: h_target_m = {h_target_m} m is negative",
            why="Target altitude must be at or above MSL.",
            action="Set h_target_m >= 0.",
            context={"h_target_m": h_target_m},
        )
    if h_sensor_m <= h_target_m:
        raise ParameterBoundsError(
            what=(f"{where}: h_sensor_m = {h_sensor_m} m is not above h_target_m = {h_target_m} m"),
            why=(
                "The spherical viewing triangle is defined for a downlooking "
                "sensor (h_sensor > h_target); v1 has no uplooking geometry."
            ),
            action="Set h_sensor_m strictly greater than h_target_m.",
            context={"h_sensor_m": h_sensor_m, "h_target_m": h_target_m},
        )
    return R_EARTH_M + h_target_m, R_EARTH_M + h_sensor_m


def _validate_theta_o(theta_o_rad: float, where: str) -> None:
    if not (0.0 <= theta_o_rad < math.pi / 2.0):
        raise ParameterBoundsError(
            what=(
                f"{where}: theta_o_rad = {theta_o_rad} rad "
                f"({math.degrees(theta_o_rad):.3f}°) is outside [0, π/2)"
            ),
            why=(
                "Observer zenith at the target must lie between nadir (0) and "
                "the horizontal (π/2, exclusive) — the LineOfSightGeometry "
                "convention."
            ),
            action="Reduce theta_o_rad below π/2 rad (90°).",
            context={"theta_o_rad": theta_o_rad},
        )


def eta_from_theta_o(theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0) -> float:
    """Sensor off-nadir angle η [rad] from target-side zenith θ_o.

    Law of sines on the viewing triangle::

        sin(η) = (R_E + h_target) / (R_E + h_sensor) · sin(θ_o)

    Exact inverse of :func:`radiant.core.los_geometry.theta_o_from_eta`.
    Since ``r_t < r_s`` (validated), the ratio is < 1 and a solution
    always exists; η < θ_o strictly for θ_o > 0.
    """
    _validate_theta_o(theta_o_rad, "eta_from_theta_o")
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "eta_from_theta_o")
    return float(math.asin((r_t / r_s) * math.sin(theta_o_rad)))


def slant_range_from_theta_o_m(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0
) -> float:
    """Slant range target → sensor [m] from target-side zenith θ_o.

    Law of cosines on the viewing triangle (positive root)::

        d = −r_t cos(θ_o) + √( r_t² cos²(θ_o) + r_s² − r_t² )

    At nadir (θ_o = 0) this reduces to ``h_sensor − h_target`` exactly.
    Same construction as ``LineOfSightGeometry.intercepts_earth``'s
    internal slant range.
    """
    _validate_theta_o(theta_o_rad, "slant_range_from_theta_o_m")
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "slant_range_from_theta_o_m")
    cos_to = math.cos(theta_o_rad)
    disc = (r_t * cos_to) ** 2 + (r_s * r_s - r_t * r_t)
    # disc >= r_s² − r_t² > 0 for r_s > r_t — always a real positive root.
    return float(-r_t * cos_to + math.sqrt(disc))


def ground_range_from_theta_o_m(
    theta_o_rad: float, h_sensor_m: float, h_target_m: float = 0.0
) -> float:
    """Surface arc distance nadir-point → target [m] from θ_o.

    Angle sum of the viewing triangle: the central angle is
    ``φ = θ_o − η`` (interior angles π − θ_o at the target, η at the
    sensor, φ at the centre sum to π).  Ground range is the Earth-surface
    arc ``R_E · φ``.  Zero at nadir.
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

    Raises when the requested arc puts the sensor at or below the
    target's horizon (θ_o would reach π/2) — the maximum expressible
    arc is ``R_E · (π/2 − asin(r_t / r_s))``.
    """
    if ground_range_m < 0.0:
        raise ParameterBoundsError(
            what=f"theta_o_from_ground_range_m: ground_range_m = {ground_range_m} m is negative",
            why="Ground range is a distance; it cannot be negative.",
            action="Set ground_range_m >= 0.",
            context={"ground_range_m": ground_range_m},
        )
    r_t, r_s = _validate_altitudes(h_sensor_m, h_target_m, "theta_o_from_ground_range_m")
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
