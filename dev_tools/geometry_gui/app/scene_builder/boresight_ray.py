"""Boresight ray — purple line observer→target with `o` label.

Phase 9 (PLAN.md §11). The boresight is the optical axis of the observer:
the line from the observer through the scene center (target) and onward
through the ground at background point B. We draw two segments:

  * solid: observer → target   (the actual line of sight)
  * dashed: target  → B        (the same line extended past the target so the
    angle to n_B at B is geometrically anchored)

A short text label `o` sits near the midpoint of the solid segment.

Rule 19: this is its own file. Per CLAUDE.md user memory, every numeric label
carries a unit token; here `o` is the symbolic-vector label (unitless), but
the hover text reports the off-nadir angle in degrees so the unit bearing of
the visualization remains intact.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder._arc_palette import arc_color_for

_BORESIGHT_COLOR: Final[str] = arc_color_for("target")


def boresight_ray_traces(
    observer_pos_display: npt.NDArray[np.float64],
    target_pos_display: npt.NDArray[np.float64],
    background_pos_display: npt.NDArray[np.float64],
    look_angle_rad: float,
) -> list[go.Scatter3d]:
    """Solid observer→target ray + dashed extension to B + `o` label."""
    o = np.asarray(observer_pos_display, dtype=np.float64)
    t = np.asarray(target_pos_display, dtype=np.float64)
    b = np.asarray(background_pos_display, dtype=np.float64)
    label_pos = 0.5 * (o + t)
    look_deg = math.degrees(look_angle_rad)
    name = f"boresight o (look = {look_deg:.1f} deg)"

    solid = go.Scatter3d(
        x=[float(o[0]), float(t[0])],
        y=[float(o[1]), float(t[1])],
        z=[float(o[2]), float(t[2])],
        mode="lines",
        line={"color": _BORESIGHT_COLOR, "width": 5},
        name=name,
        hoverinfo="name",
        showlegend=True,
    )
    extension = go.Scatter3d(
        x=[float(t[0]), float(b[0])],
        y=[float(t[1]), float(b[1])],
        z=[float(t[2]), float(b[2])],
        mode="lines",
        line={"color": _BORESIGHT_COLOR, "width": 3, "dash": "dot"},
        name="boresight (extended to B)",
        hoverinfo="name",
        showlegend=False,
    )
    label = go.Scatter3d(
        x=[float(label_pos[0])],
        y=[float(label_pos[1])],
        z=[float(label_pos[2])],
        mode="text",
        text=["o"],
        textposition="middle right",
        textfont={"size": 14, "color": _BORESIGHT_COLOR},
        name="boresight label",
        hoverinfo="skip",
        showlegend=False,
    )
    return [solid, extension, label]
