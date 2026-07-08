"""Circular-orbit kinematics — period, orbital velocity, ground-track speed.

Pure kinematics (no radiometry, no sensor knowledge): converts a circular
LEO altitude into the orbital quantities that downstream coverage
calculations consume. Found needed by scenario 3.1, where Raj plans passes
and coverage: the existing `performance.access_rate` takes a
`ground_speed_m_s` it cannot itself compute, and swath/revisit reasoning
needs the orbital period.

Model (two-body circular orbit, spherical Earth):

    a   = R_E + h                          (orbital radius)
    v   = √(μ / a)                         (orbital speed, inertial frame)
    T   = 2π √(a³ / μ) = 2π a / v          (orbital period)
    v_g = v · R_E / a                      (sub-satellite ground-track speed)

The ground-track speed is the inertial speed scaled by the ratio of the
Earth's surface radius to the orbital radius — the sub-satellite point
sweeps a smaller circle than the satellite. Earth's rotation is neglected
(a few percent cross-term at LEO, direction-dependent); this is the
non-rotating-Earth ground speed, adequate for coverage-rate sizing.

This lives in ``core`` because it is orbital geometry, not sensor physics —
the same category as :func:`radiant.core.solar_geometry.solar_zenith_angle_rad`
and :func:`radiant.core.geometry.slant_range_spherical_m`.
"""

from __future__ import annotations

import math

from radiant.core.constants import mu_earth_m3_s2
from radiant.core.exceptions import RadiantError
from radiant.core.geometry import EARTH_RADIUS_M

__all__ = [
    "OrbitError",
    "ground_track_speed_m_s",
    "orbital_period_s",
    "orbital_velocity_m_s",
]


class OrbitError(RadiantError):
    """Raised for out-of-range orbital-kinematics inputs."""


def _orbital_radius_m(altitude_m: float) -> float:
    """Circular-orbit radius a = R_E + h [m], validating altitude > 0."""
    if altitude_m <= 0.0:
        raise OrbitError(f"altitude_m must be positive (a LEO altitude), got {altitude_m}.")
    return EARTH_RADIUS_M + altitude_m


def orbital_velocity_m_s(altitude_m: float) -> float:
    """Circular-orbit inertial speed v = √(μ/a) [m/s]."""
    a = _orbital_radius_m(altitude_m)
    return math.sqrt(mu_earth_m3_s2 / a)


def orbital_period_s(altitude_m: float) -> float:
    """Circular-orbit period T = 2π √(a³/μ) [s]."""
    a = _orbital_radius_m(altitude_m)
    return 2.0 * math.pi * math.sqrt(a**3 / mu_earth_m3_s2)


def ground_track_speed_m_s(altitude_m: float) -> float:
    """Sub-satellite ground-track speed v_g = v · R_E / a [m/s].

    The inertial orbital speed scaled by R_E / (R_E + h): the nadir point
    traces a smaller circle than the satellite. Earth rotation neglected
    (non-rotating-Earth ground speed).
    """
    a = _orbital_radius_m(altitude_m)
    v = math.sqrt(mu_earth_m3_s2 / a)
    return v * EARTH_RADIUS_M / a
