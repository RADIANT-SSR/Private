"""Integration-boundary canary (PLAN_v2.md §8 step 6).

The v2 dev tool talks to RADIANT through exactly two surfaces:
``radiant.core.geometry`` (observer / scene / target geometry types) and
``radiant.source.shapes.*`` (the five concrete shape classes). This test
confirms both can be imported and instantiated, so a future RADIANT
refactor that breaks either surface fails this test loudly instead of
silently breaking every Phase 1+ scene-build call.

C6: only public symbols (no leading underscore) from ``radiant`` are
imported here.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.geometry import (
    ObserverGeometry,
    SceneGeometry,
    TargetGeometry,
    euler_to_rotation_matrix,
)
from radiant.core.regime import RadiometricRegime
from radiant.source.shape import TargetShape
from radiant.source.shapes.box import Box
from radiant.source.shapes.cone import Cone
from radiant.source.shapes.cylinder import Cylinder
from radiant.source.shapes.flat_plate import FlatPlate
from radiant.source.shapes.sphere import Sphere


def test_geometry_types_importable_and_constructible() -> None:
    observer = ObserverGeometry(
        altitude_m=600_000.0,
        look_angle_rad=math.radians(20.0),
        yaw_rad=0.0,
        pitch_rad=0.0,
        roll_rad=0.0,
    )
    target = TargetGeometry(altitude_m=0.0)
    scene = SceneGeometry(observer=observer, target=target)
    assert scene.slant_range_m > 0.0
    assert scene.ground_range_m > 0.0


def test_euler_to_rotation_matrix_identity_at_zero() -> None:
    R = euler_to_rotation_matrix(0.0, 0.0, 0.0)
    assert R.shape == (3, 3)
    for i in range(3):
        for j in range(3):
            expected = 1.0 if i == j else 0.0
            assert R[i, j] == pytest.approx(expected, abs=1e-15)


def test_radiometric_regime_enum_has_expected_members() -> None:
    members = {m.value for m in RadiometricRegime}
    assert {"extended", "sub_pixel", "point_source"}.issubset(members)


@pytest.mark.parametrize(
    "shape",
    [
        Sphere(radius_m=1.0),
        Cylinder(radius_m=0.5, length_m=2.0),
        FlatPlate(length_m=2.0, width_m=1.0),
        Box(length_m=2.0, width_m=1.0, height_m=0.5),
        Cone(base_radius_m=0.7, height_m=1.5),
    ],
    ids=["sphere", "cylinder", "flat_plate", "box", "cone"],
)
def test_each_shape_constructs_and_exposes_projected_area(shape: TargetShape) -> None:
    """Every concrete shape implements the ``projected_area(view)`` contract.

    Computed at the unit +Z view direction (boresight in the body frame)
    so the result is well-defined for every shape.
    """
    A = shape.projected_area([0.0, 0.0, 1.0])
    assert A > 0.0, f"{type(shape).__name__}: projected_area must be positive at +Z"
