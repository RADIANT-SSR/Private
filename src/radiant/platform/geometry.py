"""GSD, IFOV, slant range, and look angle helpers.

These geometric quantities relate the detector pixel to the ground
sample distance and instantaneous field of view.

All angles in radians, all lengths in metres (canonical units).

See RADIANT_Metrics.md §4.6 and RADIANT_Conventions.md §1.
"""

from __future__ import annotations

import math


def gsd_m(
    pixel_pitch_m: float,
    altitude_m: float,
    focal_length_m: float,
) -> float:
    """Ground Sample Distance [m].

    GSD = pixel_pitch × altitude / focal_length.

    For nadir viewing with altitude as the slant range.

    Parameters
    ----------
    pixel_pitch_m:
        Detector pixel pitch [m].
    altitude_m:
        Platform altitude or slant range [m].
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    float
        GSD in metres.
    """
    if pixel_pitch_m <= 0.0:
        raise ValueError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    if altitude_m <= 0.0:
        raise ValueError(f"altitude_m must be positive, got {altitude_m}")
    if focal_length_m <= 0.0:
        raise ValueError(f"focal_length_m must be positive, got {focal_length_m}")

    return pixel_pitch_m * altitude_m / focal_length_m


def ifov_rad(
    pixel_pitch_m: float,
    focal_length_m: float,
) -> float:
    """Instantaneous Field of View [rad].

    IFOV = pixel_pitch / focal_length.

    Parameters
    ----------
    pixel_pitch_m:
        Detector pixel pitch [m].
    focal_length_m:
        Effective focal length [m].

    Returns
    -------
    float
        IFOV in radians.
    """
    if pixel_pitch_m <= 0.0:
        raise ValueError(f"pixel_pitch_m must be positive, got {pixel_pitch_m}")
    if focal_length_m <= 0.0:
        raise ValueError(f"focal_length_m must be positive, got {focal_length_m}")

    return pixel_pitch_m / focal_length_m


def slant_range_m(
    altitude_m: float,
    look_angle_rad: float = 0.0,
) -> float:
    """Slant range from platform to ground point [m].

    For nadir viewing (look_angle = 0), slant range = altitude.
    For off-nadir: slant_range = altitude / cos(look_angle).

    Parameters
    ----------
    altitude_m:
        Platform altitude [m].
    look_angle_rad:
        Off-nadir look angle [rad]. Must be in [0, π/2).

    Returns
    -------
    float
        Slant range [m].
    """
    if altitude_m <= 0.0:
        raise ValueError(f"altitude_m must be positive, got {altitude_m}")
    if look_angle_rad < 0.0 or look_angle_rad >= math.pi / 2:
        raise ValueError(
            f"look_angle_rad must be in [0, π/2), got {look_angle_rad}"
        )

    return altitude_m / math.cos(look_angle_rad)


def gsd_at_angle_m(
    pixel_pitch_m: float,
    altitude_m: float,
    focal_length_m: float,
    look_angle_rad: float = 0.0,
) -> float:
    """GSD at off-nadir look angle [m].

    GSD = pixel_pitch × slant_range / focal_length.

    Parameters
    ----------
    pixel_pitch_m:
        Detector pixel pitch [m].
    altitude_m:
        Platform altitude [m].
    focal_length_m:
        Effective focal length [m].
    look_angle_rad:
        Off-nadir look angle [rad].

    Returns
    -------
    float
        GSD at the specified look angle [m].
    """
    sr = slant_range_m(altitude_m, look_angle_rad)
    return gsd_m(pixel_pitch_m, sr, focal_length_m)
