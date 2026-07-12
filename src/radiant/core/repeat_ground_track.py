"""Repeat-ground-track & revisit kinematics for circular LEO orbits.

Pure kinematics (no radiometry, no sensor knowledge): the J2 secular nodal
regression, the sun-synchronous inclination, the equatorial ground-track
spacing, and a first-order swath-revisit estimate. Found needed by scenario
3.1, where orbits/day and the access corridor were coverage proxies (Gap
51); this adds the orbit-plane and ground-track layer above the
single-orbit kinematics in :mod:`radiant.core.orbit`.

Model:

    n      = mean motion = √(μ / a³)                         [rad/s]
    Ω̇      = −1.5 · n · J2 · (R_E/a)² · cos i                [rad/s]
             (secular nodal regression; retrograde i > 90° ⇒ Ω̇ > 0)
    sun-sync: Ω̇ = 360° / 365.2422 d = 0.9856 °/day  (plane tracks the Sun)
    ΔL     = 360° · T_orbit / T_solar_day                    (westward node shift)
    spacing_eq = 2π R_E · T_orbit / T_solar_day               [m at equator]

The ground-track spacing uses the solar day (86400 s), the natural frame
for a sun-synchronous orbit; Earth's sidereal rotation and the small
node-shift from Ω̇ within a day are neglected (< ~1 %). The revisit estimate
is first-order (nadir swath vs inter-track spacing at latitude) — exact
revisit requires the integer repeat-cycle, which is out of scope here.

This lives in ``core`` because it is orbital geometry, the same category as
:mod:`radiant.core.orbit`.
"""

from __future__ import annotations

import math

from radiant.core.constants import R_EARTH_M, J2_earth, mu_earth_m3_s2
from radiant.core.exceptions import RadiantError
from radiant.core.orbit import orbital_period_s

__all__ = [
    "RepeatGroundTrackError",
    "equatorial_ground_track_spacing_m",
    "nodal_regression_rate_deg_per_day",
    "revisit_interval_days",
    "sun_synchronous_inclination_deg",
]

# Nodal regression a sun-synchronous orbit must hold: 360° per tropical year.
_SUN_SYNC_RATE_DEG_PER_DAY = 360.0 / 365.2422
_SOLAR_DAY_S = 86400.0


class RepeatGroundTrackError(RadiantError):
    """Raised for out-of-range repeat-ground-track inputs."""


def _mean_motion_rad_s(altitude_m: float) -> float:
    if altitude_m <= 0.0:
        raise RepeatGroundTrackError(f"altitude_m must be positive, got {altitude_m}.")
    a = R_EARTH_M + altitude_m
    return math.sqrt(mu_earth_m3_s2 / a**3)


def nodal_regression_rate_deg_per_day(altitude_m: float, inclination_deg: float) -> float:
    """Secular nodal regression Ω̇ [deg/day] from J2.

    ``Ω̇ = −1.5 · n · J2 · (R_E/a)² · cos i``. Negative (westward) for
    prograde orbits (i < 90°); positive for retrograde/sun-sync (i > 90°).
    """
    if not 0.0 <= inclination_deg <= 180.0:
        raise RepeatGroundTrackError(f"inclination_deg must be in [0, 180], got {inclination_deg}.")
    n = _mean_motion_rad_s(altitude_m)
    a = R_EARTH_M + altitude_m
    omega_dot_rad_s = (
        -1.5 * n * J2_earth * (R_EARTH_M / a) ** 2 * math.cos(math.radians(inclination_deg))
    )
    return math.degrees(omega_dot_rad_s) * _SOLAR_DAY_S


def sun_synchronous_inclination_deg(altitude_m: float) -> float:
    """Inclination [deg] giving a sun-synchronous orbit at *altitude_m*.

    Solves ``Ω̇(i) = 0.9856 °/day`` for i. Returns a value in (90°, 180°)
    (retrograde). Raises if no sun-sync inclination exists at this altitude
    (``|cos i| > 1`` — too high for the J2 torque to keep pace).
    """
    n = _mean_motion_rad_s(altitude_m)
    a = R_EARTH_M + altitude_m
    # Ω̇_deg_day = K · cos i, with K the prograde (negative) coefficient.
    k_deg_day = math.degrees(-1.5 * n * J2_earth * (R_EARTH_M / a) ** 2) * _SOLAR_DAY_S
    cos_i = _SUN_SYNC_RATE_DEG_PER_DAY / k_deg_day
    if not -1.0 <= cos_i <= 1.0:
        raise RepeatGroundTrackError(
            f"No sun-synchronous inclination exists at altitude {altitude_m:.0f} m "
            f"(required cos i = {cos_i:.3f} is out of range)."
        )
    return math.degrees(math.acos(cos_i))


def equatorial_ground_track_spacing_m(altitude_m: float) -> float:
    """Longitude spacing between successive ascending nodes at the equator [m].

    ``2π R_E · T_orbit / T_solar_day`` — the Earth turns under the orbit by
    one orbital period's worth of a solar day each revolution.
    """
    t_orbit = orbital_period_s(altitude_m)
    return 2.0 * math.pi * R_EARTH_M * t_orbit / _SOLAR_DAY_S


def revisit_interval_days(
    altitude_m: float,
    swath_width_m: float,
    latitude_deg: float = 0.0,
) -> float:
    """First-order nadir revisit interval [days] for a cross-track swath.

    The adjacent-track spacing shrinks by ``cos(latitude)`` toward the
    poles; the number of days for the daily tracks to fill that spacing
    with the given swath is ``spacing(lat) / (swath · orbits_per_day)``.
    This is a coverage estimate, not the exact repeat-cycle revisit — it
    assumes tracks interleave uniformly and ignores swath overlap at the
    poles. Returns days (may be < 1 for a wide swath).
    """
    if swath_width_m <= 0.0:
        raise RepeatGroundTrackError(f"swath_width_m must be positive, got {swath_width_m}.")
    if not -90.0 <= latitude_deg <= 90.0:
        raise RepeatGroundTrackError(f"latitude_deg must be in [-90, 90], got {latitude_deg}.")
    spacing_eq = equatorial_ground_track_spacing_m(altitude_m)
    spacing_lat = spacing_eq * math.cos(math.radians(latitude_deg))
    orbits_per_day = _SOLAR_DAY_S / orbital_period_s(altitude_m)
    return spacing_lat / (swath_width_m * orbits_per_day)
