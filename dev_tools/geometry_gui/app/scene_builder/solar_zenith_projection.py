"""Solar-zenith arc projection onto the ground plane at B.

Phase 10 (PLAN.md §11). The solar-zenith arc θ_sun,B at the background
point B lives in the plane spanned by `n_B` (+Z in our flat-ground
convention) and `s_B` (toward the sun). Projecting onto the ground
plane at B (normal = n_B = +Z) produces the arc's footprint on the
local terrain — useful for reading the "where on the ground does the
sun illuminate from" decomposition by inspection.

Rule 19: own file.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import arc_points
from dev_tools.geometry_gui.app.scene_builder._arc_palette import (
    PROJECTION_ALPHA,
    arc_color_for,
)
from dev_tools.geometry_gui.app.scene_builder._arc_radii import arc_radius_for
from dev_tools.geometry_gui.app.scene_builder._projection_helpers import (
    project_points_onto_plane,
)


def solar_zenith_projection_traces(
    background_pos_display: npt.NDArray[np.float64],
    surface_normal_b: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Dashed companion of the θ_sun,B arc on the ground plane at B."""
    p = np.asarray(background_pos_display, dtype=np.float64)
    radius = arc_radius_for("solar_zenith_b")
    xs, ys, zs, _ = arc_points(p, surface_normal_b, sun_dir_scene, radius=radius)
    if xs.size == 0:
        return []

    pxs, pys, pzs = project_points_onto_plane(xs, ys, zs, p, surface_normal_b)
    return [
        go.Scatter3d(
            x=pxs,
            y=pys,
            z=pzs,
            mode="lines",
            line={"color": arc_color_for("background"), "width": 2, "dash": "dot"},
            opacity=PROJECTION_ALPHA,
            name="θ_sun,B projection (ground plane)",
            hoverinfo="name",
            showlegend=False,
        )
    ]
