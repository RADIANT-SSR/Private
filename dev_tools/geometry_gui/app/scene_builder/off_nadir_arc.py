"""Off-nadir angle arc — drawn at the observer between nadir and boresight.

Phase 9 (PLAN.md §11). At the observer, the angle between the nadir reference
(−Z in display) and the boresight is the off-nadir look angle θ_look (in deg).
This module draws a small arc spanning that angle and labels it.

Rule 19: this is its own file. The shared circular-arc primitive lives in
`_arc_helpers.arc_points`; only the styling, anchor, and label logic live
here.
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


def off_nadir_arc_traces(
    observer_pos_display: npt.NDArray[np.float64],
    target_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Arc + label for the off-nadir angle at the observer.

    The off-nadir angle is *measured geometrically* from the observer and
    target positions: it is the angle between the local nadir (−Z) and the
    boresight (target − observer). Caller does not pass the look angle;
    this keeps the visualization and the label inseparable by construction.
    """
    o = np.asarray(observer_pos_display, dtype=np.float64)
    t = np.asarray(target_pos_display, dtype=np.float64)
    nadir_dir = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    boresight_dir = t - o

    radius = arc_radius_for("off_nadir")
    color = arc_color_for("observer")
    xs, ys, zs, swept = arc_points(o, nadir_dir, boresight_dir, radius=radius)
    if xs.size == 0:
        return []

    look_deg = math.degrees(swept)
    arc_name = f"off-nadir = {look_deg:.1f} deg"
    label_name = f"off-nadir label ({look_deg:.1f} deg)"
    label_x = float(xs[len(xs) // 2])
    label_y = float(ys[len(ys) // 2])
    label_z = float(zs[len(zs) // 2])

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
        text=[label_for("off_nadir")],
        textposition="middle right",
        textfont={"size": 12, "color": color},
        name=label_name,
        hoverinfo="skip",
        showlegend=False,
    )
    return [arc, text]
