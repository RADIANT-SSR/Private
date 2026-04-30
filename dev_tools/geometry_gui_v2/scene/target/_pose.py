"""Apply target body-frame pose (yaw / pitch / roll + schematic lift) to a mesh.

The target shape modules (``sphere.py``, ``cylinder.py``, ``cone.py``,
``box.py``, ``flat_plate.py``) build their mesh in the body frame at the
origin. This helper rotates that mesh by the ZYX (yaw → pitch → roll)
Euler triple from ``SceneState`` and lifts it so it sits above the
ground (z = 0).

Two stacked offsets contribute to the lift:

  * **Ground-clearance**: ``-z_min`` of the rotated mesh, so the lowest
    point of the body sits at z = 0 instead of bisecting the ground.
  * **Schematic altitude**: a log-mapped offset (0 km → 0 m,
    2000 km → ``LIFT_MAX_M``) added on top so a high-altitude target
    visibly floats above ground. The mapping is intentionally schematic
    — physical altitude (up to 2000 km LEO) cannot fit in the
    not-to-scale frame (sensor at 6 m, sun at 9 m). The actual altitude
    is also surfaced as text on the target leader label.

Rotation convention matches ``radiant.core.geometry.euler_to_rotation_matrix``:
``R = R_z(yaw) @ R_y(pitch) @ R_x(roll)``. Same convention used by
``view_model.compute_view_direction_body`` so the projected-area
read-out and the rendered orientation stay consistent.

Rule 19: one helper, one purpose. Each shape module calls this exactly
once after building its body-frame mesh.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from radiant.core.geometry import euler_to_rotation_matrix

# Maximum schematic lift at the top of the target-altitude slider
# (2000 km). Tuned to read "clearly above ground" without colliding with
# the observer glyph at SCENE_OBSERVER_DISTANCE_M = 6 m.
LIFT_MAX_M: Final[float] = 4.0
_LIFT_REFERENCE_KM: Final[float] = 2_000.0


def schematic_lift_m(target_altitude_m: float) -> float:
    """Schematic altitude → scene-meter offset.

    Log-mapped so 0/1/10/100/600/2000 km read as ~0/0.4/1.3/2.4/3.4/4.0 m
    in the scene frame. The map is monotonic and clamped to
    ``[0, LIFT_MAX_M]``.
    """
    alt_km = max(target_altitude_m / 1_000.0, 0.0)
    if alt_km <= 0.0:
        return 0.0
    capped = min(alt_km, _LIFT_REFERENCE_KM)
    return LIFT_MAX_M * math.log10(1.0 + capped) / math.log10(1.0 + _LIFT_REFERENCE_KM)


def target_centroid_scene(state: SceneState) -> tuple[float, float, float]:
    """Z position the target *centroid* settles at after lift.

    Approximated as ``schematic_lift_m + body_half_height`` where
    ``body_half_height`` is the largest possible vertical half-extent
    of the unrotated body (used by labels to avoid an O(rebuild-mesh)
    pass — exact post-rotation z is computed inside ``apply_target_pose``).
    """
    half_height = _approx_body_half_height(state)
    return (0.0, 0.0, schematic_lift_m(state.target_altitude_m) + half_height)


def _approx_body_half_height(state: SceneState) -> float:
    """Conservative upper bound on the body's vertical half-extent for any
    rotation — diagonal of the body-frame AABB / 2.
    """
    kind = state.target_shape
    if kind == "sphere":
        return state.target_radius_m
    if kind == "cylinder":
        return 0.5 * math.hypot(state.target_length_m, 2.0 * state.target_radius_m)
    if kind == "cone":
        return 0.5 * math.hypot(state.target_height_m, 2.0 * state.target_base_radius_m)
    if kind == "box":
        return 0.5 * math.sqrt(
            state.target_length_m**2
            + state.target_width_m**2
            + state.target_height_m**2
        )
    if kind == "flat_plate":
        return 0.5 * math.hypot(state.target_length_m, state.target_width_m)
    return state.target_radius_m


def apply_target_pose(mesh: pv.PolyData, state: SceneState) -> pv.PolyData:
    """Rotate ``mesh`` by the target Euler triple, then lift it so its
    base sits at the ground plane plus a schematic altitude offset.
    Mutates and returns ``mesh`` for call-site brevity.
    """
    R = euler_to_rotation_matrix(
        state.target_yaw_rad,
        state.target_pitch_rad,
        state.target_roll_rad,
    )
    transform = np.eye(4)
    transform[:3, :3] = R
    mesh.transform(transform, inplace=True)

    z_min = mesh.bounds[4]
    lift_z = -z_min + schematic_lift_m(state.target_altitude_m)
    if abs(lift_z) > 1e-9:
        translation = np.eye(4)
        translation[2, 3] = lift_z
        mesh.transform(translation, inplace=True)
    return mesh
