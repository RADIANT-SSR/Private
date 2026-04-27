"""Sphere mesh — parametric tessellation, body frame ⇒ display frame."""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

_N_LAT: Final[int] = 16
_N_LON: Final[int] = 32


def sphere_mesh_traces(
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Translucent solid sphere centred on the target."""
    lat = np.linspace(-np.pi / 2.0, np.pi / 2.0, _N_LAT)
    lon = np.linspace(0.0, 2.0 * np.pi, _N_LON, endpoint=False)
    lat_g, lon_g = np.meshgrid(lat, lon, indexing="ij")
    x_body = (display_radius * np.cos(lat_g) * np.cos(lon_g)).ravel()
    y_body = (display_radius * np.cos(lat_g) * np.sin(lon_g)).ravel()
    z_body = (display_radius * np.sin(lat_g)).ravel()
    body = np.vstack([x_body, y_body, z_body])
    scene = R_target @ body + target_pos_display[:, None]
    return [
        go.Mesh3d(
            x=scene[0],
            y=scene[1],
            z=scene[2],
            alphahull=0,
            color="orange",
            opacity=0.6,
            name="Target (sphere)",
        )
    ]
