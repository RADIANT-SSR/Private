"""Elevation arc — boresight angle above the local-horizontal plane.

Phase 10 (PLAN.md §11). Elevation is the angle between the boresight (target
→ observer view direction `−o`) and its projection onto the XY plane at the
target. For the canonical observer in −X/+Z the elevation equals
(π/2 − θ_look); when the observer is rolled out of XZ, az and el together
reconstruct the boresight.

Anchor at target/origin. The arc is drawn from the XY-projection of the
**view-direction** (target → observer = `−boresight`) up to that view
direction itself. Returns no traces if the projection is null (boresight
exactly vertical).

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


def view_elevation_rad(boresight_unit_display: npt.NDArray[np.float64]) -> float:
    """el = arcsin(view_z) where view = −boresight. Range [−π/2, π/2]."""
    b = np.asarray(boresight_unit_display, dtype=np.float64)
    view_z = float(-b[2])
    return math.asin(max(-1.0, min(1.0, view_z)))


def elevation_arc_traces(
    target_pos_display: npt.NDArray[np.float64],
    boresight_unit_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + `el = …°` label at the target between view-XY-projection and view."""
    t = np.asarray(target_pos_display, dtype=np.float64)
    b = np.asarray(boresight_unit_display, dtype=np.float64)
    view = -b  # target → observer
    proj = np.array([float(view[0]), float(view[1]), 0.0], dtype=np.float64)
    if float(np.linalg.norm(proj)) < 1e-12:
        return []
    radius = arc_radius_for("elevation")
    color = arc_color_for("observer")
    xs, ys, zs, swept = arc_points(t, proj, view, radius=radius)
    if xs.size == 0:
        return []

    el_deg = math.degrees(swept)
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

    arc_name = f"el = {el_deg:.1f} deg"
    label_name = f"el label ({el_deg:.1f} deg)"
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
        text=[label_for("elevation")],
        textposition="middle right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
