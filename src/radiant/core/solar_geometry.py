"""Solar-geometry calculator — solar zenith angle from date, latitude, time.

Pure kinematics (no radiometry, no sensor knowledge): converts a
target latitude, day of year, and local solar time into the solar
zenith angle for illumination geometry. Found needed by scenario 1.2,
where a sun-synchronous orbit's LTAN (Local Time of the Ascending Node)
must become the `geometry.solar_zenith_rad` the chain consumes.

Model (standard solar-position identities):

    δ  = solar declination (Spencer's Fourier series, ±0.01° of the
         true declination — better than Cooper's single-term formula)
    h  = hour angle = 15°/hr · (LST − 12)
    cos θ_z = sin φ sin δ + cos φ cos δ cos h

For a sun-synchronous orbit the local solar time is ~constant along the
daylit track, so the LTAN is a good estimate of the local solar time at
the target — :func:`local_solar_time_from_ltan` makes that identification
explicit (and documents the approximation).

This lives in ``core`` because it is geometry, not physics — the same
category as :func:`radiant.core.geometry.slant_range_spherical_m`.
"""

from __future__ import annotations

import math

from radiant.core.exceptions import RadiantError

__all__ = [
    "SolarGeometryError",
    "local_solar_time_from_ltan",
    "solar_declination_deg",
    "solar_zenith_angle_rad",
]


class SolarGeometryError(RadiantError):
    """Raised for out-of-range solar-geometry inputs."""


def solar_declination_deg(day_of_year: int) -> float:
    """Solar declination [deg] for *day_of_year* (1–366).

    Spencer's Fourier-series approximation (accurate to ~0.01°):

        δ = (180/π)·(0.006918 − 0.399912 cos B + 0.070257 sin B
             − 0.006758 cos 2B + 0.000907 sin 2B
             − 0.002697 cos 3B + 0.001480 sin 3B),   B = 2π(N−1)/365
    """
    if not 1 <= day_of_year <= 366:
        raise SolarGeometryError(f"day_of_year must be in [1, 366], got {day_of_year}.")
    b = 2.0 * math.pi * (day_of_year - 1) / 365.0
    delta_rad = (
        0.006918
        - 0.399912 * math.cos(b)
        + 0.070257 * math.sin(b)
        - 0.006758 * math.cos(2 * b)
        + 0.000907 * math.sin(2 * b)
        - 0.002697 * math.cos(3 * b)
        + 0.001480 * math.sin(3 * b)
    )
    return math.degrees(delta_rad)


def local_solar_time_from_ltan(ltan_hours: float) -> float:
    """Local solar time [hr] at the target from a sun-sync orbit LTAN.

    A sun-synchronous orbit holds its local solar time ~constant along
    the daylit ground track, so the LTAN (the local solar time at the
    ascending-node equator crossing) is a good estimate of the local
    solar time at any target on that pass. This is an identity with a
    documented approximation, not a coordinate transform — target
    longitude and the small nodal-regression drift within a pass are
    neglected (both < a few minutes for LEO sun-sync).
    """
    if not 0.0 <= ltan_hours <= 24.0:
        raise SolarGeometryError(f"ltan_hours must be in [0, 24], got {ltan_hours}.")
    return ltan_hours


def solar_zenith_angle_rad(
    latitude_deg: float,
    day_of_year: int,
    local_solar_time_hr: float,
) -> float:
    """Solar zenith angle [rad] at a target.

    Parameters
    ----------
    latitude_deg:
        Target geodetic latitude [deg], −90 to +90 (north positive).
    day_of_year:
        Day of year, 1–366.
    local_solar_time_hr:
        Local solar time [hr], 0–24 (12.0 = solar noon). For a
        sun-synchronous orbit use :func:`local_solar_time_from_ltan`.

    Returns
    -------
    float
        Solar zenith angle [rad], 0 (overhead) to π/2 (horizon) and
        beyond (night). ``cos θ_z = sin φ sin δ + cos φ cos δ cos h``.
    """
    if not -90.0 <= latitude_deg <= 90.0:
        raise SolarGeometryError(f"latitude_deg must be in [-90, 90], got {latitude_deg}.")
    if not 0.0 <= local_solar_time_hr <= 24.0:
        raise SolarGeometryError(
            f"local_solar_time_hr must be in [0, 24], got {local_solar_time_hr}."
        )
    phi = math.radians(latitude_deg)
    delta = math.radians(solar_declination_deg(day_of_year))
    hour_angle = math.radians(15.0 * (local_solar_time_hr - 12.0))
    cos_z = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(hour_angle)
    # Clamp for float round-off at the overhead/horizon extremes.
    cos_z = max(-1.0, min(1.0, cos_z))
    return math.acos(cos_z)
