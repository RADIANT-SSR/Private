"""Cone mesh — base at body z=0, apex at body z=2·display_radius."""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

_N_AZ: Final[int] = 32


def cone_mesh_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Right circular cone with base radius and height = `display_radius`.

    Base sits at body z = -display_radius/2 (so the centroid is roughly at
    body origin) and apex at body z = +display_radius/2 — centered for the
    target marker to coincide visually with the cone centroid.
    """
    h = display_radius
    r = display_radius
    z_base = -0.5 * h
    z_apex = +0.5 * h

    az = np.linspace(0.0, 2.0 * np.pi, _N_AZ, endpoint=False)
    base_x = r * np.cos(az)
    base_y = r * np.sin(az)
    base_ring = np.stack([base_x, base_y, np.full_like(base_x, z_base)], axis=0)
    apex = np.array([[0.0], [0.0], [z_apex]])
    base_centre = np.array([[0.0], [0.0], [z_base]])

    verts_body = np.hstack([base_ring, apex, base_centre])
    scene = R_target @ verts_body + target_pos_display[:, None]
    return [
        go.Mesh3d(
            x=scene[0],
            y=scene[1],
            z=scene[2],
            alphahull=0,
            color="orange",
            opacity=0.6,
            name="Target (cone)",
        )
    ]
