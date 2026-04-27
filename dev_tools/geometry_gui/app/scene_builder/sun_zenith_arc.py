"""Sun zenith arc θ_s — sun angle from local-zenith at the target.

Phase 10 (PLAN.md §11). At the target, θ_s is the angle between local
zenith (+Z) and the sun direction. This is the *target-anchored* zenith, in
contrast to θ_sun,B which is the same physics evaluated at the background
point (`solar_zenith_arc.py`). They are equal in the flat-ground display
convention because n_B = +Z, but are conceptually distinct anchors and
belong to different angle-groups (sun vs. background) in the Phase 10 UI.

Rule 19: own file.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_helpers import arc_points
from dev_tools.geometry_gui.app.scene_builder._arc_labels import label_for
from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for
from dev_tools.geometry_gui.app.scene_builder._arc_radii import arc_radius_for


def sun_zenith_at_target_rad(sun_dir_scene: npt.NDArray[np.float64]) -> float:
    """θ_s = arccos(+Z · s_hat). Input is normalized internally."""
    s = np.asarray(sun_dir_scene, dtype=np.float64)
    s = s / np.linalg.norm(s)
    return math.acos(float(np.clip(s[2], -1.0, 1.0)))


def sun_zenith_arc_traces(
    target_pos_display: npt.NDArray[np.float64],
    sun_dir_scene: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + `θ_s = …°` label at the target between +Z and the sun direction."""
    t = np.asarray(target_pos_display, dtype=np.float64)
    plus_z = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    radius = arc_radius_for("sun_zenith")
    color = arc_color_for("sun")
    xs, ys, zs, swept = arc_points(t, plus_z, sun_dir_scene, radius=radius)
    if xs.size == 0:
        return []

    theta_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"theta_s = {theta_deg:.1f} deg"
    label_name = f"theta_s label ({theta_deg:.1f} deg)"
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
        text=[label_for("sun_zenith")],
        textposition="top right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
