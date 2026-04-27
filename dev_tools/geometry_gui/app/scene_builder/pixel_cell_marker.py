"""Pixel-cell marker — used in the EXTENDED regime in place of a target mesh.

In an extended-scene regime the radiometry uses one ground cell of side GSD
and a target shape is irrelevant. This marker draws a small filled square
centered on the target position to communicate that to the developer.

Display sizing
--------------
Real GSDs span sub-meter to ~hundreds of meters; the scene is drawn in
display units where Earth radius = 1.0, so a literal `side = GSD_m`
square would either be invisible or larger than the Earth depending on
configuration. We render at a fixed display size (`PIXEL_CELL_DISPLAY_SIDE`)
so the cell is always visible; the actual GSD value in meters is what the
readout panel reports. (Same convention `target_shape_meshes` uses for
real shapes — see PLAN.md §"Coordinate convention (display)".)
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

# Display side length — scales with TARGET_DISPLAY_RADIUS = 1.0 (Phase 8
# redesign, PLAN.md §11). 1.5× target radius keeps the cell readable but
# distinct from the shape mesh size.
PIXEL_CELL_DISPLAY_SIDE: Final[float] = 1.5


def pixel_cell_traces(
    target_pos_display: npt.NDArray[np.float64],
    gsd_m: float,
) -> list[go.Mesh3d]:
    """Filled square of side `PIXEL_CELL_DISPLAY_SIDE` in the local x-y plane.

    The square sits flat against the target's local horizontal plane (at the
    +Z pole this is the global x-y plane). Two triangles form the quad. The
    real-world side length (`gsd_m`, in meters) appears in the trace name
    so it shows on hover.
    """
    half = PIXEL_CELL_DISPLAY_SIDE / 2.0
    cx, cy, cz = (
        float(target_pos_display[0]),
        float(target_pos_display[1]),
        float(target_pos_display[2]),
    )
    xs = np.array([cx - half, cx + half, cx + half, cx - half], dtype=np.float64)
    ys = np.array([cy - half, cy - half, cy + half, cy + half], dtype=np.float64)
    zs = np.array([cz, cz, cz, cz], dtype=np.float64)
    # Two triangles: (0,1,2) and (0,2,3).
    i = np.array([0, 0], dtype=np.int64)
    j = np.array([1, 2], dtype=np.int64)
    k = np.array([2, 3], dtype=np.int64)
    return [
        go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=i,
            j=j,
            k=k,
            color="orange",
            opacity=0.85,
            name=f"Pixel cell (GSD = {gsd_m:.3g} m)",
            showlegend=True,
        )
    ]
