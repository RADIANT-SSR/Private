"""Azimuth arc — view-direction projection on the local-horizontal plane.

Phase 10 (PLAN.md §11). The azimuth angle is the rotation of the
view direction (target → observer) about the local zenith, measured from
+X (along-track reference) on the XY plane at the target. It is one of the
two angles in the standard observer (az, el) decomposition; elevation is
the other. (The "view direction" convention — az/el measured on the ray
*toward the satellite as seen from the target* — matches conventional
astronomical az/el.)

Anchor at target/origin, on the XY plane. Returns no traces if the
view-XY projection is null (observer directly overhead).

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


def view_azimuth_rad(boresight_unit_display: npt.NDArray[np.float64]) -> float:
    """az = atan2(view_y, view_x) where view = −boresight."""
    b = np.asarray(boresight_unit_display, dtype=np.float64)
    vx, vy = float(-b[0]), float(-b[1])
    if vx == 0.0 and vy == 0.0:
        return 0.0
    return math.atan2(vy, vx)


def azimuth_arc_traces(
    target_pos_display: npt.NDArray[np.float64],
    boresight_unit_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + `az = …°` label at the target on the XY plane.

    Uses view = −boresight so a satellite in the −X/+Z quadrant reads
    az = 180° (sat lies in the −X half of the local horizon), matching
    the conventional observer-az convention.
    """
    t = np.asarray(target_pos_display, dtype=np.float64)
    b = np.asarray(boresight_unit_display, dtype=np.float64)
    view_proj = np.array([float(-b[0]), float(-b[1]), 0.0], dtype=np.float64)
    if float(np.linalg.norm(view_proj)) < 1e-12:
        return []
    plus_x = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    radius = arc_radius_for("azimuth")
    color = arc_color_for("observer")
    xs, ys, zs, swept = arc_points(t, plus_x, view_proj, radius=radius)
    if xs.size == 0:
        return []

    az_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"az = {az_deg:.1f} deg"
    label_name = f"az label ({az_deg:.1f} deg)"
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
        text=[label_for("azimuth")],
        textposition="bottom right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
