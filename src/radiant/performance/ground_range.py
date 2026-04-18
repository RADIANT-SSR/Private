"""Ground range — arc distance from nadir to target on Earth surface.

Uses the law of cosines on the (sensor, Earth center, target) triangle
to find the central angle, then computes arc distance::

    cos(gamma) = (r_s² + R_E² - d²) / (2 × r_s × R_E)
    ground_range = R_E × gamma

where r_s = R_E + h, d = slant_range.
"""

from __future__ import annotations

import math

from radiant.core.geometry import EARTH_RADIUS_M, slant_range_spherical_m


def compute_ground_range_m(altitude_m: float, path_zenith_rad: float) -> float:
    """Arc distance from sub-satellite point to target on Earth surface [m].

    Parameters
    ----------
    altitude_m : float
        Sensor altitude above the Earth surface [m].  Must be > 0.
    path_zenith_rad : float
        Off-nadir look angle [rad].  Must be >= 0.

    Returns
    -------
    float
        Ground range in meters.  Returns 0.0 at nadir (zenith=0).

    Raises
    ------
    ValueError
        If ``path_zenith_rad`` < 0 or exceeds the horizon angle.
    """
    if path_zenith_rad < 0.0:
        raise ValueError(
            f"compute_ground_range_m: path_zenith_rad = {path_zenith_rad:.4f} "
            f"rad is negative.  Off-nadir angle must be >= 0."
        )
    if path_zenith_rad == 0.0 or altitude_m <= 0.0:
        return 0.0

    R = EARTH_RADIUS_M
    r_sensor = R + altitude_m

    # Slant range via ray-sphere intersection (raises ValueError if
    # beyond horizon).
    slant = slant_range_spherical_m(altitude_m, path_zenith_rad)

    # Law of cosines for the central (Earth-center) angle gamma.
    cos_gamma = (r_sensor * r_sensor + R * R - slant * slant) / (
        2.0 * r_sensor * R
    )
    # Clamp for floating-point safety.
    cos_gamma = max(-1.0, min(1.0, cos_gamma))
    gamma = math.acos(cos_gamma)

    return R * gamma
