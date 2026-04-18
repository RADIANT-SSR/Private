"""GSD — Ground Sample Distance.

Computes ground sample distance from pixel pitch, sensor altitude, focal
length, and (optionally) off-nadir look angle::

    Nadir:     GSD = pixel_pitch × altitude / focal_length
    Off-nadir: GSD_cross = pixel_pitch × slant_range / focal_length
               GSD_along = pixel_pitch × slant_range / (focal_length × cos(incidence))

The spherical-Earth slant range and ground incidence angle are computed
by helpers in ``radiant.core.geometry``.  At zenith=0 the formulas reduce
to the nadir case exactly.

Reports cross-track and along-track GSD separately, plus geometric mean
(used by GIQE-5 for NIIRS).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.core.geometry import incidence_angle_rad, slant_range_spherical_m


@dataclass(frozen=True, slots=True)
class GSDResult:
    """Result of GSD computation."""

    cross_track_m: float
    """GSD in the cross-track (x) direction [m]."""

    along_track_m: float
    """GSD in the along-track (y) direction [m]."""

    @property
    def geometric_mean_m(self) -> float:
        """Geometric mean GSD [m]: sqrt(cross × along).

        Used by GIQE-5 for NIIRS computation.
        """
        return math.sqrt(self.cross_track_m * self.along_track_m)


def compute_gsd(
    pitch_x_m: float,
    pitch_y_m: float,
    altitude_m: float,
    focal_length_m: float,
    path_zenith_rad: float = 0.0,
) -> GSDResult:
    """Compute ground sample distance, optionally corrected for off-nadir viewing.

    Parameters
    ----------
    pitch_x_m : float
        Pixel pitch in the cross-track direction [m].
    pitch_y_m : float
        Pixel pitch in the along-track direction [m].
    altitude_m : float
        Sensor altitude above ground [m].  Must be > 0.
    focal_length_m : float
        Effective focal length [m].  Must be > 0.
    path_zenith_rad : float
        Off-nadir look angle [rad].  Default 0.0 (nadir).  Uses
        spherical-Earth slant range and incidence angle to compute
        cross-track and along-track GSD correctly at off-nadir angles.

    Returns
    -------
    GSDResult
        Cross-track and along-track GSD in meters, plus geometric_mean_m
        property.
    """
    if path_zenith_rad == 0.0:
        # Fast path: nadir formula (backward compatible, exact).
        gsd_x = pitch_x_m * altitude_m / focal_length_m
        gsd_y = pitch_y_m * altitude_m / focal_length_m
    else:
        slant = slant_range_spherical_m(altitude_m, path_zenith_rad)
        inc = incidence_angle_rad(altitude_m, path_zenith_rad)
        cos_inc = math.cos(inc)

        gsd_x = pitch_x_m * slant / focal_length_m
        gsd_y = pitch_y_m * slant / (focal_length_m * cos_inc)

    return GSDResult(cross_track_m=gsd_x, along_track_m=gsd_y)
