"""Cylinder mesh — body axis along +Z, length = display height."""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

_N_AZ: Final[int] = 32


def cylinder_mesh_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Closed cylinder (lateral + two caps) of length 2·display_radius along body +Z."""
    half_h = display_radius
    r = display_radius

    az = np.linspace(0.0, 2.0 * np.pi, _N_AZ, endpoint=False)
    ring_x = r * np.cos(az)
    ring_y = r * np.sin(az)

    # Build vertex array in body frame: top ring, bottom ring, top cap centre, bottom cap centre.
    top_ring = np.stack([ring_x, ring_y, np.full_like(ring_x, half_h)], axis=0)
    bot_ring = np.stack([ring_x, ring_y, np.full_like(ring_x, -half_h)], axis=0)
    top_centre = np.array([[0.0], [0.0], [half_h]])
    bot_centre = np.array([[0.0], [0.0], [-half_h]])

    verts_body = np.hstack([top_ring, bot_ring, top_centre, bot_centre])
    scene = R_target @ verts_body + target_pos_display[:, None]
    return [
        go.Mesh3d(
            x=scene[0],
            y=scene[1],
            z=scene[2],
            alphahull=0,
            color="orange",
            opacity=0.6,
            name="Target (cylinder)",
        )
    ]
