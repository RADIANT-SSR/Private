"""Sun azimuth arc Δφ — sun XY-projection azimuth from +X.

Phase 10 (PLAN.md §11). The relative azimuth Δφ is the angle on the local
horizontal plane between +X (along-track reference) and the XY-projection
of the sun direction. Together with θ_s it specifies the sun direction.

Anchored at the scene origin / target on the XY plane. Returns no traces
when the sun is exactly overhead (XY-projection null).

Rule 19: own file.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import arc_points
from dev_tools.geometry_gui.app.scene_builder._arc_labels import label_for
from dev_tools.geometry_gui.app.scene_builder._arc_offsets import shifted_anchor
from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for
from dev_tools.geometry_gui.app.scene_builder._arc_radii import arc_radius_for
from dev_tools.geometry_gui.app.scene_builder.arc_leader_line import (
    arc_leader_line_traces,
)


def sun_azimuth_rad(sun_dir_scene: npt.NDArray[np.float64]) -> float:
    """Δφ = atan2(s_y, s_x). Returns 0 if XY-projection is null."""
    s = np.asarray(sun_dir_scene, dtype=np.float64)
    sx, sy = float(s[0]), float(s[1])
    if sx == 0.0 and sy == 0.0:
        return 0.0
    return math.atan2(sy, sx)


def sun_azimuth_arc_traces(
    target_pos_display: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + `Δφ = …°` label on the XY plane at target."""
    t = np.asarray(target_pos_display, dtype=np.float64)
    s = np.asarray(sun_dir_scene, dtype=np.float64)
    proj = np.array([float(s[0]), float(s[1]), 0.0], dtype=np.float64)
    if float(np.linalg.norm(proj)) < 1e-12:
        return []
    plus_x = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    radius = arc_radius_for("sun_azimuth")
    color = arc_color_for("sun")
    anchor = shifted_anchor(t, plus_x, proj, "target")
    xs, ys, zs, swept = arc_points(anchor, plus_x, proj, radius=radius)
    if xs.size == 0:
        return []

    phi_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"delta_phi = {phi_deg:.1f} deg"
    label_name = f"delta_phi label ({phi_deg:.1f} deg)"
    arc = go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode="lines",
        line={"color": color, "width": 3},
        name=arc_name,
        hoverinfo="name",
        showlegend=True,
    )
    text = go.Scatter3d(
        x=[label_x],
        y=[label_y],
        z=[label_z],
        mode="text",
        text=[label_for("sun_azimuth")],
        textposition="bottom right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    leader = arc_leader_line_traces(
        t, anchor, color, leader_name=f"delta_phi leader ({phi_deg:.1f} deg)"
    )
    return [arc, text, *leader]
