"""Tests for geometric primitive shapes.

Truth anchors (all hand-verified):
1. Sphere: A_proj = π r² at all orientations
2. Box broadside: A = L × W; front-on: A = L × H
3. Cylinder broadside: A = 2r × L; end-on: A = π r²
4. FlatPlate normal: A = L × W; edge-on: A = 0
5. Cone end-on: A ≈ π r²; broadside: A ≈ r × h

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.source.shape import TargetShape
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere

# View direction helpers (unit vectors in scene frame)
VZ = np.array([0.0, 0.0, 1.0])  # broadside / end-on / normal
VX = np.array([1.0, 0.0, 0.0])  # side
VY = np.array([0.0, 1.0, 0.0])  # front


def _view_at_angle(theta_deg: float) -> np.ndarray:
    """View direction tilting from +Z toward +Y by theta degrees."""
    theta = math.radians(theta_deg)
    return np.array([0.0, math.sin(theta), math.cos(theta)])


# ======================================================================
# Sphere
# ======================================================================


class TestSphere:
    @pytest.mark.level0
    def test_protocol(self) -> None:
        assert isinstance(Sphere(radius_m=1.0), TargetShape)

    @pytest.mark.level0
    def test_projected_area_orientation_independent(self) -> None:
        s = Sphere(radius_m=1.0)
        expected = math.pi
        for v in [VZ, VX, VY, _view_at_angle(45)]:
            assert s.projected_area(v) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_projected_area_small(self) -> None:
        s = Sphere(radius_m=0.1)
        assert s.projected_area(VZ) == pytest.approx(math.pi * 0.01, rel=1e-12)

    @pytest.mark.level0
    def test_surface_area(self) -> None:
        s = Sphere(radius_m=2.0)
        assert s.surface_area() == pytest.approx(4 * math.pi * 4.0, rel=1e-12)

    @pytest.mark.level0
    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="radius_m"):
            Sphere(radius_m=-1.0)

    @pytest.mark.level0
    def test_zero_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="radius_m"):
            Sphere(radius_m=0.0)

    @pytest.mark.level0
    def test_frozen(self) -> None:
        s = Sphere(radius_m=1.0)
        with pytest.raises(AttributeError):
            s.radius_m = 2.0  # type: ignore[misc]


# ======================================================================
# FlatPlate
# ======================================================================


class TestFlatPlate:
    @pytest.mark.level0
    def test_protocol(self) -> None:
        assert isinstance(FlatPlate(length_m=1.0, width_m=1.0), TargetShape)

    @pytest.mark.level0
    def test_normal_incidence(self) -> None:
        """Face-on: A = L × W."""
        fp = FlatPlate(length_m=2.0, width_m=1.0)
        assert fp.projected_area(VZ) == pytest.approx(2.0, rel=1e-12)

    @pytest.mark.level0
    def test_edge_on_zero(self) -> None:
        """Edge-on: A = 0."""
        fp = FlatPlate(length_m=2.0, width_m=1.0)
        assert fp.projected_area(VX) == pytest.approx(0.0, abs=1e-15)

    @pytest.mark.level0
    def test_oblique_angles(self) -> None:
        """A = L × W × cos(θ)."""
        fp = FlatPlate(length_m=2.0, width_m=1.0)
        for theta_deg in [30, 45, 60]:
            v = _view_at_angle(theta_deg)
            expected = 2.0 * math.cos(math.radians(theta_deg))
            assert fp.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_back_side_visible(self) -> None:
        """Viewing from back (−Z) gives same area."""
        fp = FlatPlate(length_m=2.0, width_m=1.0)
        assert fp.projected_area(-VZ) == pytest.approx(2.0, rel=1e-12)

    @pytest.mark.level0
    def test_surface_area(self) -> None:
        fp = FlatPlate(length_m=3.0, width_m=2.0)
        assert fp.surface_area() == pytest.approx(12.0, rel=1e-12)

    @pytest.mark.level0
    def test_with_orientation(self) -> None:
        """90° pitch rotates the plate normal from +Z body to +X scene."""
        fp = FlatPlate(
            length_m=2.0,
            width_m=1.0,
            orientation_rad=(0.0, math.pi / 2, 0.0),
        )
        # After 90° pitch, body +Z maps to scene +X.
        # Viewing from +X should see full area.
        assert fp.projected_area(VX) == pytest.approx(2.0, rel=1e-10)
        # Viewing from +Z should see edge-on.
        assert fp.projected_area(VZ) == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.level0
    def test_negative_dimension_raises(self) -> None:
        with pytest.raises(ValueError, match="length_m"):
            FlatPlate(length_m=-1.0, width_m=1.0)


# ======================================================================
# Box
# ======================================================================


class TestBox:
    @pytest.mark.level0
    def test_protocol(self) -> None:
        assert isinstance(Box(length_m=1.0, width_m=1.0, height_m=1.0), TargetShape)

    @pytest.mark.level0
    def test_broadside(self) -> None:
        """View along +Z: L × W = 2 × 1 = 2."""
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        assert b.projected_area(VZ) == pytest.approx(2.0, rel=1e-12)

    @pytest.mark.level0
    def test_front_on(self) -> None:
        """View along +Y: L × H = 2 × 0.5 = 1."""
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        assert b.projected_area(VY) == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_side_on(self) -> None:
        """View along +X: W × H = 1 × 0.5 = 0.5."""
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        assert b.projected_area(VX) == pytest.approx(0.5, rel=1e-12)

    @pytest.mark.level0
    def test_oblique_angles(self) -> None:
        """Tilting from +Z toward +Y: A = L×H×sin θ + L×W×cos θ."""
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        for theta_deg in [30, 45, 60]:
            v = _view_at_angle(theta_deg)
            theta = math.radians(theta_deg)
            expected = 2.0 * 0.5 * math.sin(theta) + 2.0 * 1.0 * math.cos(theta)
            assert b.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_surface_area(self) -> None:
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        expected = 2 * (2 * 1 + 2 * 0.5 + 1 * 0.5)
        assert b.surface_area() == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_cube_symmetry(self) -> None:
        """Cube has same projected area from all cardinal directions."""
        c = Box(length_m=1.0, width_m=1.0, height_m=1.0)
        a_z = c.projected_area(VZ)
        a_x = c.projected_area(VX)
        a_y = c.projected_area(VY)
        assert a_z == pytest.approx(a_x, rel=1e-12)
        assert a_z == pytest.approx(a_y, rel=1e-12)

    @pytest.mark.level0
    def test_negative_height_raises(self) -> None:
        with pytest.raises(ValueError, match="height_m"):
            Box(length_m=1.0, width_m=1.0, height_m=-0.5)

    @pytest.mark.level0
    def test_frozen(self) -> None:
        b = Box(length_m=1.0, width_m=1.0, height_m=1.0)
        with pytest.raises(AttributeError):
            b.length_m = 2.0  # type: ignore[misc]


# ======================================================================
# Cylinder
# ======================================================================


class TestCylinder:
    @pytest.mark.level0
    def test_protocol(self) -> None:
        assert isinstance(Cylinder(radius_m=0.5, length_m=2.0), TargetShape)

    @pytest.mark.level0
    def test_end_on(self) -> None:
        """View along axis: π r²."""
        c = Cylinder(radius_m=0.5, length_m=2.0)
        assert c.projected_area(VZ) == pytest.approx(math.pi * 0.25, rel=1e-12)

    @pytest.mark.level0
    def test_broadside(self) -> None:
        """View perpendicular to axis: 2r × L."""
        c = Cylinder(radius_m=0.5, length_m=2.0)
        assert c.projected_area(VX) == pytest.approx(2.0, rel=1e-12)

    @pytest.mark.level0
    def test_oblique_angles(self) -> None:
        """A = 2r·L·sin θ + π·r²·cos θ (θ from axis)."""
        c = Cylinder(radius_m=0.5, length_m=2.0)
        for theta_deg in [30, 45, 60]:
            # θ from axis means view_direction = sin θ * X + cos θ * Z
            theta = math.radians(theta_deg)
            v = np.array([math.sin(theta), 0.0, math.cos(theta)])
            expected = 2 * 0.5 * 2.0 * math.sin(theta) + math.pi * 0.25 * math.cos(theta)
            assert c.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    def test_surface_area(self) -> None:
        c = Cylinder(radius_m=0.5, length_m=2.0)
        expected = 2 * math.pi * 0.5 * 2.0 + 2 * math.pi * 0.25
        assert c.surface_area() == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_with_orientation(self) -> None:
        """90° pitch rotates axis from +Z to +X."""
        c = Cylinder(
            radius_m=0.5,
            length_m=2.0,
            orientation_rad=(0.0, math.pi / 2, 0.0),
        )
        # Axis now along +X. Viewing from +X is end-on.
        assert c.projected_area(VX) == pytest.approx(math.pi * 0.25, rel=1e-10)
        # Viewing from +Z is broadside.
        assert c.projected_area(VZ) == pytest.approx(2.0, rel=1e-10)

    @pytest.mark.level0
    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="radius_m"):
            Cylinder(radius_m=-0.5, length_m=2.0)


# ======================================================================
# Cone
# ======================================================================


class TestCone:
    @pytest.mark.level0
    def test_protocol(self) -> None:
        assert isinstance(Cone(base_radius_m=1.0, height_m=2.0), TargetShape)

    @pytest.mark.level0
    def test_end_on_base(self) -> None:
        """View from below base (−Z): A ≈ π r²."""
        cone = Cone(base_radius_m=1.0, height_m=2.0, n_facets=256)
        assert cone.projected_area(-VZ) == pytest.approx(math.pi, rel=1e-3)

    @pytest.mark.level0
    def test_broadside(self) -> None:
        """View perpendicular to axis: A ≈ r × h."""
        cone = Cone(base_radius_m=1.0, height_m=2.0, n_facets=256)
        assert cone.projected_area(VX) == pytest.approx(2.0, rel=1e-2)

    @pytest.mark.level0
    def test_convergence(self) -> None:
        """High facet count produces stable result for oblique view."""
        # Use oblique view to avoid symmetry-related exact convergence.
        v_oblique = np.array([0.5, 0.3, 0.8])
        v_oblique = v_oblique / np.linalg.norm(v_oblique)
        areas = []
        for n in [8, 32, 128, 512]:
            cone = Cone(base_radius_m=1.0, height_m=2.0, n_facets=n)
            areas.append(cone.projected_area(v_oblique))
        # Value stabilizes: last two are closer than first two.
        diff_first = abs(areas[1] - areas[0])
        diff_last = abs(areas[3] - areas[2])
        assert diff_last < diff_first

    @pytest.mark.level0
    def test_surface_area(self) -> None:
        """π r s + π r² where s = √(r² + h²)."""
        cone = Cone(base_radius_m=1.0, height_m=2.0)
        s = math.sqrt(1.0 + 4.0)
        expected = math.pi * s + math.pi
        assert cone.surface_area() == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_apex_view(self) -> None:
        """View from above apex (+Z): only lateral facets visible ≈ π r²."""
        cone = Cone(base_radius_m=1.0, height_m=2.0, n_facets=256)
        # From above, the silhouette is a circle of radius r.
        area = cone.projected_area(VZ)
        assert area == pytest.approx(math.pi, rel=5e-2)

    @pytest.mark.level0
    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="base_radius_m"):
            Cone(base_radius_m=-1.0, height_m=2.0)

    @pytest.mark.level0
    def test_negative_height_raises(self) -> None:
        with pytest.raises(ValueError, match="height_m"):
            Cone(base_radius_m=1.0, height_m=-2.0)

    @pytest.mark.level0
    def test_too_few_facets_raises(self) -> None:
        with pytest.raises(ValueError, match="n_facets"):
            Cone(base_radius_m=1.0, height_m=2.0, n_facets=2)

    @pytest.mark.level0
    def test_frozen(self) -> None:
        cone = Cone(base_radius_m=1.0, height_m=2.0)
        with pytest.raises(AttributeError):
            cone.base_radius_m = 2.0  # type: ignore[misc]


# ======================================================================
# Projected area table (all primitives at standard orientations)
# ======================================================================


class TestProjectedAreaTable:
    """Projected area at 0°, 30°, 45°, 60°, 90° — hand-verified.

    The angle is from the shape's primary axis (+Z body):
    - 0° = view along axis (end-on / normal-to-plate / broadside for box)
    - 90° = view perpendicular to axis
    """

    @pytest.mark.level0
    @pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 90])
    def test_sphere(self, theta_deg: int) -> None:
        s = Sphere(radius_m=1.0)
        theta = math.radians(theta_deg)
        v = np.array([math.sin(theta), 0.0, math.cos(theta)])
        assert s.projected_area(v) == pytest.approx(math.pi, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 90])
    def test_flat_plate(self, theta_deg: int) -> None:
        fp = FlatPlate(length_m=2.0, width_m=1.0)
        theta = math.radians(theta_deg)
        v = np.array([math.sin(theta), 0.0, math.cos(theta)])
        expected = 2.0 * abs(math.cos(theta))
        assert fp.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    @pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 90])
    def test_box(self, theta_deg: int) -> None:
        """Box(2, 1, 0.5), tilting from +Z toward +X."""
        b = Box(length_m=2.0, width_m=1.0, height_m=0.5)
        theta = math.radians(theta_deg)
        v = np.array([math.sin(theta), 0.0, math.cos(theta)])
        # A = W·H·|vx| + L·H·0 + L·W·|vz|
        expected = 1.0 * 0.5 * abs(math.sin(theta)) + 2.0 * 1.0 * abs(math.cos(theta))
        assert b.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    @pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 90])
    def test_cylinder(self, theta_deg: int) -> None:
        c = Cylinder(radius_m=0.5, length_m=2.0)
        theta = math.radians(theta_deg)
        v = np.array([math.sin(theta), 0.0, math.cos(theta)])
        expected = 2 * 0.5 * 2.0 * math.sin(theta) + math.pi * 0.25 * abs(math.cos(theta))
        assert c.projected_area(v) == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level0
    @pytest.mark.parametrize("theta_deg", [0, 90])
    def test_cone_cardinal(self, theta_deg: int) -> None:
        """Cone at cardinal angles only (faceted → looser tolerance)."""
        cone = Cone(base_radius_m=1.0, height_m=2.0, n_facets=256)
        theta = math.radians(theta_deg)
        v = np.array([math.sin(theta), 0.0, math.cos(theta)])
        if theta_deg == 0:
            # Apex view ≈ π r²
            assert cone.projected_area(v) == pytest.approx(math.pi, rel=5e-2)
        else:
            # Broadside ≈ r × h
            assert cone.projected_area(v) == pytest.approx(2.0, rel=1e-2)
