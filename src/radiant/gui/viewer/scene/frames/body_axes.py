"""Target body-frame axes triad — the on-target RPY orientation gizmo (Part B).

Three short tubes at the target centroid along the body +X / +Y / +Z axes **after** the
target's yaw/pitch/roll rotation is applied, so the triad visibly reports the target's
orientation. The axes are colour-coded per the arch doc §6.2 / ADR-0007 §8.5 convention:

  * body +X = **roll** → pink   (``BODY_AXIS_ROLL_COLOR``)
  * body +Y = **pitch** → green  (``BODY_AXIS_PITCH_COLOR``)
  * body +Z = **yaw** → purple   (``BODY_AXIS_YAW_COLOR``)

The rotation uses the exact same ``radiant.core.geometry.euler_to_rotation_matrix``
(``R = R_z(yaw) @ R_y(pitch) @ R_x(roll)``) that ``target/_pose.apply_target_pose`` uses
for the target body mesh, so the triad and the body it annotates rotate together. The
triad origin is the lifted target centroid (``target/_pose.target_centroid_scene``), so it
sits on the (possibly altitude-lifted) target rather than at the world origin.

Rebound from the prototype (``dev_tools/geometry_gui_v2/scene/frames/body_axes.py``):
``SceneState`` → the production ``ViewerState`` (same field names), and the single neutral
axis colour → the three RPY-coded colours. No Qt, no physics stage.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import pyvista as pv

from radiant.core.geometry import euler_to_rotation_matrix
from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.scene.vectors._tube import add_tube
from radiant.gui.viewer.viewer_state import ViewerState as SceneState

# Body axis index → (actor name, RPY-coded colour). +X = roll, +Y = pitch, +Z = yaw.
_AXES: Final[tuple[tuple[int, str, str], ...]] = (
    (0, "body_axis_x", style.BODY_AXIS_ROLL_COLOR),
    (1, "body_axis_y", style.BODY_AXIS_PITCH_COLOR),
    (2, "body_axis_z", style.BODY_AXIS_YAW_COLOR),
)


def _characteristic_length(state: SceneState) -> float:
    return max(
        state.target_radius_m,
        state.target_length_m,
        state.target_width_m,
        state.target_height_m,
        state.target_base_radius_m,
        1.0,
    )


def _arm_length(state: SceneState) -> float:
    """Triad arm length in scene-metres (clamped so a tiny target still reads)."""
    body = _characteristic_length(state) * style.BODY_AXES_LENGTH_FRACTION
    return max(body, style.BODY_AXES_MIN_LENGTH_M)


def axis_endpoints(state: SceneState) -> dict[str, npt.NDArray[np.float64]]:
    """Pure geometry: the world-space endpoint of each RPY-rotated body axis.

    The triad's origin is the (altitude-lifted) target centroid; each axis end is
    ``origin + R(yaw,pitch,roll) @ (arm · ê_axis)`` using the **same**
    ``euler_to_rotation_matrix`` (ZYX) the target body mesh uses, so the triad and the
    body it annotates rotate together. Exposed so a test can assert the triad reflects the
    ``source.target.shape_{yaw,pitch,roll}_rad`` params without introspecting a VTK actor.
    """
    arm = _arm_length(state)
    origin = np.array(target_centroid_scene(state), dtype=np.float64)
    rotation = euler_to_rotation_matrix(
        state.target_yaw_rad,
        state.target_pitch_rad,
        state.target_roll_rad,
    )
    ends: dict[str, npt.NDArray[np.float64]] = {}
    for axis_idx, name, _color in _AXES:
        body_axis = np.zeros(3, dtype=np.float64)
        body_axis[axis_idx] = arm
        ends[name] = origin + rotation @ body_axis
    return ends


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    """Draw the RPY-coloured body-axes triad at the (rotated) target centroid."""
    origin = np.array(target_centroid_scene(state), dtype=np.float64)
    ends = axis_endpoints(state)
    for _axis_idx, name, color in _AXES:
        add_tube(plotter, origin, ends[name], color=color, name=name)
