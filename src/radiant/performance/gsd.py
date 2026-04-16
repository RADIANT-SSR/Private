"""GSD — Ground Sample Distance.

Computes nadir ground sample distance from pixel pitch, sensor altitude,
and focal length::

    GSD = pixel_pitch × altitude / focal_length

Reports cross-track and along-track GSD separately to support rectangular
pixels.  Skips gracefully when altitude is not set (lab/TVAC scenarios)
or is zero.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GSDResult:
    """Result of GSD computation."""

    cross_track_m: float
    """GSD in the cross-track (x) direction [m]."""

    along_track_m: float
    """GSD in the along-track (y) direction [m]."""


def compute_gsd(
    pitch_x_m: float,
    pitch_y_m: float,
    altitude_m: float,
    focal_length_m: float,
) -> GSDResult:
    """Compute nadir ground sample distance.

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

    Returns
    -------
    GSDResult
        Cross-track and along-track GSD in meters.
    """
    return GSDResult(
        cross_track_m=pitch_x_m * altitude_m / focal_length_m,
        along_track_m=pitch_y_m * altitude_m / focal_length_m,
    )
