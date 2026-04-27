"""Background point B — anchor on the ground for n_B and θ_sun,B annotations.

Phase 8 redesign (PLAN.md §11): the background point B is the boresight–ground
intersection (where the line of sight pierces the ground plane). Phase 9 hangs
the surface-normal arrow `n_B` and the solar-zenith arc `θ_sun,B` off this
anchor. Here in Phase 8 we draw a small marker + label so the location is
identifiable in the scene.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder.ground_patch import (
    BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET,
)

# Vertical drop from target to background point in display units. Must be at
# least BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET so B sits on (or below) the
# ground patch. We use exactly that distance; the boresight ray's projection
# onto the ground plane sets the lateral position.
_DROP_TO_GROUND: Final[float] = BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET


def background_point_position_display(
    target_pos_display: npt.NDArray[np.float64],
    boresight_unit_scene: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Where the boresight extended past the target hits the ground plane.

    Parameters
    ----------
    target_pos_display
        Target's position in display coordinates (above the ground plane by
        `_DROP_TO_GROUND`).
    boresight_unit_scene
        Unit vector pointing from observer toward target. Extended past the
        target by parameter `t`, the line is `target + t * boresight_unit`.
        We solve for the `t` that lands the line on the ground plane
        z = target_z − _DROP_TO_GROUND.

    Returns the (x, y, z) on that ground plane. If the boresight is parallel
    to the ground (b_z ≈ 0), the function returns the target's lateral
    projection straight down — the only sensible fallback for an off-nadir
    look angle of 90°.
    """
    t_pos = np.asarray(target_pos_display, dtype=np.float64)
    b = np.asarray(boresight_unit_scene, dtype=np.float64)
    b = b / np.linalg.norm(b)

    target_z = t_pos[2]
    ground_z = target_z - _DROP_TO_GROUND

    if abs(b[2]) < 1e-9:
        return np.array([t_pos[0], t_pos[1], ground_z], dtype=np.float64)

    t = (ground_z - target_z) / b[2]
    return t_pos + t * b


def background_point_traces(
    bg_pos_display: npt.NDArray[np.float64],
) -> list[go.Scatter3d]:
    """Small dark marker labeled `B` at the boresight-ground intersection."""
    pos = np.asarray(bg_pos_display, dtype=np.float64)
    return [
        go.Scatter3d(
            x=[float(pos[0])],
            y=[float(pos[1])],
            z=[float(pos[2])],
            mode="markers+text",
            marker={"size": 6, "symbol": "circle", "color": "#7a3a1a"},
            text=["B (background point)"],
            textposition="bottom center",
            textfont={"size": 11, "color": "#7a3a1a"},
            name="Background point B",
            hoverinfo="name",
            showlegend=True,
        )
    ]
