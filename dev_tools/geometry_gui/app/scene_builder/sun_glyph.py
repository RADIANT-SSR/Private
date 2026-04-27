"""Sun glyph — labeled disk at the end of the sun ray.

Phase 8 redesign (PLAN.md §11): the sun marker sits at a fixed
`SUN_DISPLAY_DISTANCE` along the true sun direction from the target, so the
sun ray has a visible terminus. The actual sun is at infinity; this is an
illustrative marker per PLAN.md C7. Hover label carries θ_s and Δφ in deg.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

# Display-unit distance from the target to the sun glyph. Larger than
# OBSERVER_DISPLAY_DISTANCE (4.0) so the sun never overlaps the satellite.
SUN_DISPLAY_DISTANCE: Final[float] = 6.0


def sun_position_illustrative(
    target_pos_display: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Place the sun glyph at `SUN_DISPLAY_DISTANCE` along `+sun_dir`."""
    n = np.asarray(sun_dir_scene, dtype=np.float64)
    n = n / np.linalg.norm(n)
    return np.asarray(target_pos_display, dtype=np.float64) + SUN_DISPLAY_DISTANCE * n


def sun_glyph_traces(
    sun_pos_display: npt.NDArray[np.float64],
    solar_zenith_rad: float,
    relative_azimuth_rad: float,
) -> list[go.Scatter3d]:
    """Single yellow circle + label with θ_s and Δφ in deg."""
    theta_deg = math.degrees(solar_zenith_rad)
    phi_deg = math.degrees(relative_azimuth_rad)
    label = f"Sun (theta_s = {theta_deg:.1f} deg, delta_phi = {phi_deg:.1f} deg)"
    pos = np.asarray(sun_pos_display, dtype=np.float64)
    return [
        go.Scatter3d(
            x=[float(pos[0])],
            y=[float(pos[1])],
            z=[float(pos[2])],
            mode="markers+text",
            marker={"size": 18, "symbol": "circle", "color": "gold"},
            text=[label],
            textposition="top center",
            textfont={"size": 12, "color": "#aa7a00"},
            name=label,
            hoverinfo="name",
            showlegend=True,
        )
    ]
