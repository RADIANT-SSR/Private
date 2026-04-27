"""Off-nadir-arc projection onto the XZ plane at the observer.

Phase 10 (PLAN.md §11). The off-nadir arc is rendered at the observer in
the plane spanned by the local nadir (−Z) and the boresight. For a
canonical observer in the −X/+Z quadrant the boresight is in the XZ plane
already, so the projection coincides with the parent arc and this module
contributes only a dashed overdraw. When the observer is rolled out of
the XZ plane the projection visibly differs from the parent — the eye
reads the difference as the parent arc's shadow on the local meridian.

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


def off_nadir_projection_traces(
    observer_pos_display: npt.NDArray[np.float64],
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Dashed companion of the off-nadir arc on the XZ plane at the observer."""
    o = np.asarray(observer_pos_display, dtype=np.float64)
    t = np.asarray(target_pos_display, dtype=np.float64)
    nadir_dir = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    boresight_dir = t - o

    radius = arc_radius_for("off_nadir")
    xs, ys, zs, _ = arc_points(o, nadir_dir, boresight_dir, radius=radius)
    if xs.size == 0:
        return []

    plane_normal = np.array([0.0, 1.0, 0.0], dtype=np.float64)  # XZ plane
    pxs, pys, pzs = project_points_onto_plane(xs, ys, zs, o, plane_normal)
    return [
        go.Scatter3d(
            x=pxs,
            y=pys,
            z=pzs,
            mode="lines",
            line={"color": arc_color_for("observer"), "width": 2, "dash": "dot"},
            opacity=PROJECTION_ALPHA,
            name="off-nadir projection (XZ)",
            hoverinfo="name",
            showlegend=False,
        )
    ]
