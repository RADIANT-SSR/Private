"""Tests for CompositeTarget.

Truth anchors:
1. Composite of single sphere = bare sphere
2. Two non-overlapping shapes: A_comp = A_1 + A_2

See RADIANT_Source_Target_System.md §5.2.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.source.composite import CompositeTarget
from radiant.source.shape import TargetShape
from radiant.source.shapes import Box, Cylinder, FlatPlate, Sphere

VZ = np.array([0.0, 0.0, 1.0])
VX = np.array([1.0, 0.0, 0.0])


class TestCompositeTarget:
    def test_protocol(self) -> None:
        comp = CompositeTarget(shapes=(Sphere(radius_m=1.0),))
        assert isinstance(comp, TargetShape)

    def test_single_sphere_matches_bare(self) -> None:
        """Composite of one sphere = bare sphere."""
        sphere = Sphere(radius_m=1.0)
        comp = CompositeTarget(shapes=(sphere,))
        for v in [VZ, VX]:
            assert comp.projected_area(v) == pytest.approx(
                sphere.projected_area(v), rel=1e-12
            )
        assert comp.surface_area() == pytest.approx(
            sphere.surface_area(), rel=1e-12
        )

    def test_two_spheres_add(self) -> None:
        """Two spheres: projected areas add (no occlusion)."""
        s1 = Sphere(radius_m=1.0)
        s2 = Sphere(radius_m=0.5)
        comp = CompositeTarget(shapes=(s1, s2))
        expected = math.pi * 1.0 + math.pi * 0.25
        assert comp.projected_area(VZ) == pytest.approx(expected, rel=1e-12)

    def test_sphere_plus_box(self) -> None:
        """Mixed primitives: areas add."""
        s = Sphere(radius_m=0.5)
        b = Box(length_m=1.0, width_m=1.0, height_m=1.0)
        comp = CompositeTarget(shapes=(s, b))
        expected = s.projected_area(VZ) + b.projected_area(VZ)
        assert comp.projected_area(VZ) == pytest.approx(expected, rel=1e-12)

    def test_surface_area_sums(self) -> None:
        s = Sphere(radius_m=1.0)
        c = Cylinder(radius_m=0.5, length_m=2.0)
        comp = CompositeTarget(shapes=(s, c))
        expected = s.surface_area() + c.surface_area()
        assert comp.surface_area() == pytest.approx(expected, rel=1e-12)

    def test_empty_shapes_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            CompositeTarget(shapes=())

    def test_frozen(self) -> None:
        comp = CompositeTarget(shapes=(Sphere(radius_m=1.0),))
        with pytest.raises(AttributeError):
            comp.name = "changed"  # type: ignore[misc]

    def test_orientation_per_primitive(self) -> None:
        """Each primitive in the composite uses its own orientation."""
        # Two flat plates: one normal to +Z, one rotated 90° around Y (normal to +X).
        fp1 = FlatPlate(length_m=2.0, width_m=1.0)
        fp2 = FlatPlate(
            length_m=2.0, width_m=1.0,
            orientation_rad=(0.0, math.pi / 2, 0.0),
        )
        comp = CompositeTarget(shapes=(fp1, fp2))
        # View from +Z: fp1 is face-on (2.0), fp2 is edge-on (0.0)
        assert comp.projected_area(VZ) == pytest.approx(2.0, rel=1e-10)
        # View from +X: fp1 is edge-on (0.0), fp2 is face-on (2.0)
        assert comp.projected_area(VX) == pytest.approx(2.0, rel=1e-10)
