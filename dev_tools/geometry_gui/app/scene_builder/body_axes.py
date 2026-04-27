"""Three short arrows showing the target body frame X/Y/Z (red/green/blue)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go


def body_axes_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    axis_length_display: float,
) -> list[go.Scatter3d]:
    """One Scatter3d line per body axis, anchored at the target position.

    Conventional colors: X red, Y green, Z blue (matches the right-hand
    +X/+Y/+Z convention printed in CLAUDE.md §"Coordinate System").
    """
    body_axes_basis = np.eye(3, dtype=np.float64)  # columns: e_x, e_y, e_z
    colors = ("red", "green", "blue")
    names = ("body +X", "body +Y", "body +Z")

    traces: list[go.Scatter3d] = []
    for i in range(3):
        tip = target_pos_display + axis_length_display * (R_target @ body_axes_basis[:, i])
        traces.append(
            go.Scatter3d(
                x=[float(target_pos_display[0]), float(tip[0])],
                y=[float(target_pos_display[1]), float(tip[1])],
                z=[float(target_pos_display[2]), float(tip[2])],
                mode="lines",
                line={"color": colors[i], "width": 4},
                name=names[i],
            )
        )
    return traces
