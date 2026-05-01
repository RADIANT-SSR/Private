"""Round-3 S6 regression — target sits cleanly on the ground at alt=0.

Round-3 §0 defect 6: at target altitude = 0 km the sphere target was
half-buried in the ground because its centroid sat at z=0 with no
ground-clearance lift. Visually this read as a clipping bug.

The fix (Option A from ``PLAN_v2_remediation_round3.md`` §8) lives in
``scene/target/_pose.py::apply_target_pose``: after the body-frame
Euler rotation, the mesh is translated by ``-z_min`` so its lowest
point sits exactly on the ground plane (z = 0). The schematic
altitude lift is then *added on top*, so the alt=0 case has the
mesh's bottom at z = 0 and alt > 0 case has the bottom at the
schematic-lifted altitude.

This invariant must hold for every target shape — sphere, box,
cylinder, cone, flat plate — and at every Euler rotation (rotated
shapes change the z_min, but the ground-clearance step compensates).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Final

import pytest
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.builder import build_scene


_WINDOW_SIZE: Final[tuple[int, int]] = (1024, 768)
_GROUND_TOLERANCE_M: Final[float] = 0.01


def _target_z_min(plotter: pv.Plotter) -> float:
    bx = plotter.actors["target"].GetBounds()
    return float(bx[4])


_SHAPES: Final[tuple[str, ...]] = (
    "sphere",
    "box",
    "cylinder",
    "cone",
    "flat_plate",
)


@pytest.mark.parametrize("shape", _SHAPES)
def test_target_z_min_sits_on_ground_at_alt_zero(shape: str) -> None:
    """At alt=0, the lowest point of the target mesh sits at z=0
    (within a millimeter of tolerance)."""
    state = dataclasses.replace(
        SceneState.default(), target_shape=shape, target_altitude_m=0.0
    )
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        z_min = _target_z_min(p)
    finally:
        p.close()

    assert -_GROUND_TOLERANCE_M <= z_min <= _GROUND_TOLERANCE_M, (
        f"{shape}: target z_min = {z_min:.4f} m at alt=0; expected "
        f"|z_min| ≤ {_GROUND_TOLERANCE_M} m (target should sit cleanly "
        f"on the ground, neither buried nor floating)"
    )


@pytest.mark.parametrize(
    "yaw_deg,pitch_deg,roll_deg",
    [(0.0, 0.0, 0.0), (45.0, 30.0, 15.0), (0.0, 90.0, 0.0)],
)
def test_rotated_target_still_sits_on_ground_at_alt_zero(
    yaw_deg: float, pitch_deg: float, roll_deg: float
) -> None:
    """The ground-clearance lift compensates for body-frame rotations:
    a rotated box/cone/cylinder still sits on the ground at alt=0."""
    state = dataclasses.replace(
        SceneState.default(),
        target_shape="box",
        target_altitude_m=0.0,
        target_yaw_rad=math.radians(yaw_deg),
        target_pitch_rad=math.radians(pitch_deg),
        target_roll_rad=math.radians(roll_deg),
    )
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        z_min = _target_z_min(p)
    finally:
        p.close()

    assert -_GROUND_TOLERANCE_M <= z_min <= _GROUND_TOLERANCE_M, (
        f"box (yaw={yaw_deg}, pitch={pitch_deg}, roll={roll_deg}): "
        f"z_min = {z_min:.4f} m at alt=0; expected |z_min| ≤ "
        f"{_GROUND_TOLERANCE_M} m"
    )


def test_target_rises_off_ground_with_altitude() -> None:
    """The schematic altitude lift is additive on top of the ground-
    clearance step: at alt > 0 the target rises off the ground by the
    schematic lift amount, with the bottom at z = lift (not buried)."""
    from dev_tools.geometry_gui_v2.scene.target._pose import schematic_lift_m

    state = dataclasses.replace(
        SceneState.default(), target_shape="sphere", target_altitude_m=600_000.0
    )
    expected_lift = schematic_lift_m(state.target_altitude_m)
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        z_min = _target_z_min(p)
    finally:
        p.close()

    assert abs(z_min - expected_lift) <= _GROUND_TOLERANCE_M, (
        f"sphere at alt=600 km: z_min = {z_min:.4f} m; expected "
        f"~{expected_lift:.4f} m (the schematic lift)"
    )
