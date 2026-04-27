"""Phase-angle arc projection onto the target's tangent plane (XY at target).

Phase 10 (PLAN.md §11). The phase-angle arc α_t at the target lives in
the plane spanned by `−o` (target → observer) and `s_t` (target → sun).
That plane is generally tilted relative to the local horizon. Projecting
the arc onto the local-horizontal plane (normal = +Z, the local zenith
at the target) gives a dashed companion that lets the eye read the
phase-angle's "ground footprint" — the arc as it would appear from
straight overhead.

Rule 19: own file.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import arc_points
from dev_tools.geometry_gui.app.scene_builder._arc_offsets import shifted_anchor
from dev_tools.geometry_gui.app.scene_builder._arc_palette import (
    PROJECTION_ALPHA,
    arc_color_for,
)
from dev_tools.geometry_gui.app.scene_builder._arc_radii import arc_radius_for
from dev_tools.geometry_gui.app.scene_builder._projection_helpers import (
    project_points_onto_plane,
)


def phase_angle_projection_traces(
    target_pos_display: npt.NDArray[np.float64],
    view_dir_target_to_observer: npt.NDArray[np.float64],
    sun_dir_target_to_sun: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Dashed companion of the α_t arc on the target's tangent plane.

    Phase 12: anchor follows the parent arc's outward shift so the
    projection sits beside its parent rather than inside the target mesh.
    """
    t = np.asarray(target_pos_display, dtype=np.float64)
    radius = arc_radius_for("phase_angle")
    anchor = shifted_anchor(
        t, view_dir_target_to_observer, sun_dir_target_to_sun, "target"
    )
    xs, ys, zs, _ = arc_points(
        anchor, view_dir_target_to_observer, sun_dir_target_to_sun, radius=radius
    )
    if xs.size == 0:
        return []

    plane_normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    pxs, pys, pzs = project_points_onto_plane(xs, ys, zs, t, plane_normal)
    return [
        go.Scatter3d(
            x=pxs,
            y=pys,
            z=pzs,
            mode="lines",
            line={"color": arc_color_for("target"), "width": 2, "dash": "dot"},
            opacity=PROJECTION_ALPHA,
            name="α_t projection (target tangent plane)",
            hoverinfo="name",
            showlegend=False,
        )
    ]
