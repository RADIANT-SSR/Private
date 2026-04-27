"""Box mesh — 8 vertices, 12 triangles, axis-aligned in body frame."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go


def box_mesh_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Cube of half-side `display_radius` centered on the body origin."""
    s = display_radius
    verts_body = np.array(
        [
            [-s, -s, -s],
            [+s, -s, -s],
            [+s, +s, -s],
            [-s, +s, -s],
            [-s, -s, +s],
            [+s, -s, +s],
            [+s, +s, +s],
            [-s, +s, +s],
        ],
        dtype=np.float64,
    ).T
    # 12 triangles (6 faces × 2)
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
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
            name="Target (box)",
        )
    ]
