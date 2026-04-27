"""Target-shape mesh dispatch.

`target_shape_traces(state, ...)` selects the right per-shape module based
on `state.target_shape`. Each shape lives in its own file (Rule 19).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes.box_mesh import (
    box_mesh_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes.cone_mesh import (
    cone_mesh_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes.cylinder_mesh import (
    cylinder_mesh_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes.flat_plate_mesh import (
    flat_plate_mesh_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes.sphere_mesh import (
    sphere_mesh_traces,
)
from dev_tools.geometry_gui.app.state import SceneState


def target_shape_traces(
    state: SceneState,
    target_pos_display: npt.NDArray[np.float64],
    R_target: npt.NDArray[np.float64],
    display_radius: float,
) -> list[go.Mesh3d]:
    """Dispatch to the per-shape mesh builder.

    All target meshes are generated at a fixed `display_radius` (not the
    real shape size) so the target is visible against the unit-Earth scene.
    The real size is shown numerically in the readout panel.
    """
    kind = state.target_shape
    if kind == "sphere":
        return sphere_mesh_traces(target_pos_display, R_target, display_radius)
    if kind == "cylinder":
        return cylinder_mesh_traces(target_pos_display, R_target, display_radius)
    if kind == "flat_plate":
        return flat_plate_mesh_traces(target_pos_display, R_target, display_radius)
    if kind == "box":
        return box_mesh_traces(target_pos_display, R_target, display_radius)
    if kind == "cone":
        return cone_mesh_traces(target_pos_display, R_target, display_radius)
    raise ValueError(
        f"target_shape_traces: unknown target_shape={kind!r}. "
        f"Expected one of sphere/cylinder/flat_plate/box/cone."
    )


__all__ = ["target_shape_traces"]
