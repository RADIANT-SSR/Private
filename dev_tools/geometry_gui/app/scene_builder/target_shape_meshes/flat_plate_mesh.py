"""Flat-plate mesh — rectangle in body XY, normal along body +Z."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go


def flat_plate_mesh_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Square plate of half-side `display_radius` in the body XY plane."""
    s = display_radius
    verts_body = np.array(
        [
            [-s, -s, 0.0],
            [+s, -s, 0.0],
            [+s, +s, 0.0],
            [-s, +s, 0.0],
        ],
        dtype=np.float64,
    ).T
    i = [0, 0]
    j = [1, 2]
    k = [2, 3]
    scene = R_target @ verts_body + target_pos_display[:, None]
    return [
        go.Mesh3d(
            x=scene[0],
            y=scene[1],
            z=scene[2],
            i=i,
            j=j,
            k=k,
            color="orange",
            opacity=0.6,
            name="Target (flat plate)",
        )
    ]
