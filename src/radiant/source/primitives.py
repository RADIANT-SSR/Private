"""Geometric primitive shapes for target modeling.

Implements Sphere, Cylinder, Box, FlatPlate, and Cone — each satisfying
the TargetShape protocol. All use analytic projected-area formulas where
possible; Cone uses a faceted approximation.

Body-frame conventions (per RADIANT_Conventions.md §1):
  - Right-handed. Euler ZYX (yaw → pitch → roll).
  - Each shape's "long axis" or primary normal aligns with body +Z.
  - Orientation transforms body → scene frame.

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.geometry import euler_to_rotation_matrix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_positive(name: str, value: float, field: str) -> None:
    """Raise ValueError if value is not strictly positive."""
    if value <= 0.0:
        raise ValueError(
            f"{name}: {field} must be positive, got {value}. "
            f"All dimensions are in meters."
        )


def _view_to_body(
    view_direction: npt.NDArray[np.float64],
    yaw: float,
    pitch: float,
    roll: float,
) -> npt.NDArray[np.float64]:
    """Transform a scene-frame view direction into the body frame.

    R transforms body → scene, so R.T transforms scene → body.
    """
    v = np.asarray(view_direction, dtype=np.float64)
    if yaw == 0.0 and pitch == 0.0 and roll == 0.0:
        return v
    R = euler_to_rotation_matrix(yaw, pitch, roll)
    return R.T @ v


# ---------------------------------------------------------------------------
# Sphere
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sphere:
    """Sphere with orientation-independent projected area π r².

    Parameters
    ----------
    radius_m:
        Radius [m]. Must be > 0.
    orientation_rad:
        (yaw, pitch, roll) in radians. Unused for sphere (isotropic).
    position_m:
        (x, y, z) position of center in scene frame [m].
    """

    radius_m: float
    orientation_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _validate_positive("Sphere", self.radius_m, "radius_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """π r² regardless of view direction."""
        return math.pi * self.radius_m ** 2

    def surface_area(self) -> float:
        """4 π r²."""
        return 4.0 * math.pi * self.radius_m ** 2


# ---------------------------------------------------------------------------
# FlatPlate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlatPlate:
    """Flat rectangular plate with normal along body +Z.

    Two facets: front (+Z normal) and back (−Z normal). Both contribute
    to projected area, so ``A_proj = L × W × |cos θ|`` where θ is the
    angle between the view direction and the plate normal.

    Parameters
    ----------
    length_m:
        Extent along body X [m].
    width_m:
        Extent along body Y [m].
    orientation_rad:
        (yaw, pitch, roll) in radians. Body +Z is the plate normal.
    position_m:
        (x, y, z) center position in scene frame [m].
    """

    length_m: float
    width_m: float
    orientation_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _validate_positive("FlatPlate", self.length_m, "length_m")
        _validate_positive("FlatPlate", self.width_m, "width_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """L × W × |cos θ|. Zero at edge-on."""
        v = _view_to_body(view_direction, *self.orientation_rad)
        return self.length_m * self.width_m * abs(float(v[2]))

    def surface_area(self) -> float:
        """2 × L × W (front + back)."""
        return 2.0 * self.length_m * self.width_m


# ---------------------------------------------------------------------------
# Box
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Box:
    """Rectangular box (6 flat faces).

    Body-frame layout: length along X, width along Y, height along Z.
    The +Z face (L × W) is the "broadside" face.

    Parameters
    ----------
    length_m:
        Extent along body X [m].
    width_m:
        Extent along body Y [m].
    height_m:
        Extent along body Z [m].
    orientation_rad:
        (yaw, pitch, roll) in radians.
    position_m:
        (x, y, z) center position in scene frame [m].
    """

    length_m: float
    width_m: float
    height_m: float
    orientation_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _validate_positive("Box", self.length_m, "length_m")
        _validate_positive("Box", self.width_m, "width_m")
        _validate_positive("Box", self.height_m, "height_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """Sum of face-pair projections.

        A = W·H·|vx| + L·H·|vy| + L·W·|vz| in body frame.
        """
        v = _view_to_body(view_direction, *self.orientation_rad)
        L, W, H = self.length_m, self.width_m, self.height_m
        return (
            W * H * abs(float(v[0]))
            + L * H * abs(float(v[1]))
            + L * W * abs(float(v[2]))
        )

    def surface_area(self) -> float:
        """2(LW + LH + WH)."""
        L, W, H = self.length_m, self.width_m, self.height_m
        return 2.0 * (L * W + L * H + W * H)


# ---------------------------------------------------------------------------
# Cylinder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cylinder:
    """Right circular cylinder with axis along body +Z.

    Projected area (analytic):
      A = 2r·L·sin θ + π·r²·cos θ
    where θ is the angle between the view direction and the cylinder axis.

    Parameters
    ----------
    radius_m:
        Radius [m].
    length_m:
        Length along body Z axis [m].
    orientation_rad:
        (yaw, pitch, roll) in radians. Body +Z is the cylinder axis.
    position_m:
        (x, y, z) center position in scene frame [m].
    """

    radius_m: float
    length_m: float
    orientation_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _validate_positive("Cylinder", self.radius_m, "radius_m")
        _validate_positive("Cylinder", self.length_m, "length_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """2r·L·sin θ + π·r²·cos θ."""
        v = _view_to_body(view_direction, *self.orientation_rad)
        r = self.radius_m
        L = self.length_m
        cos_theta = abs(float(v[2]))
        sin_theta = math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2)
        return 2.0 * r * L * sin_theta + math.pi * r ** 2 * cos_theta

    def surface_area(self) -> float:
        """2πrL + 2πr² (lateral + two caps)."""
        r = self.radius_m
        return 2.0 * math.pi * r * self.length_m + 2.0 * math.pi * r ** 2


# ---------------------------------------------------------------------------
# Cone
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cone:
    """Right circular cone with base at z=0, apex at z=height.

    Uses a faceted approximation for projected area. The base is at
    z=0 with normal −Z; the lateral surface is approximated by
    triangular facets from the apex to the base circumference.

    Parameters
    ----------
    base_radius_m:
        Base circle radius [m].
    height_m:
        Height from base to apex [m].
    orientation_rad:
        (yaw, pitch, roll) in radians. Body +Z points from base to apex.
    position_m:
        (x, y, z) position of base center in scene frame [m].
    n_facets:
        Number of lateral facets (default 64). Higher = more accurate.
    """

    base_radius_m: float
    height_m: float
    orientation_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    n_facets: int = 64

    def __post_init__(self) -> None:
        _validate_positive("Cone", self.base_radius_m, "base_radius_m")
        _validate_positive("Cone", self.height_m, "height_m")
        if self.n_facets < 3:
            raise ValueError(
                f"Cone: n_facets must be >= 3, got {self.n_facets}. "
                f"More facets improve projected-area accuracy."
            )

        # Pre-compute facet normals and areas in body frame.
        r = self.base_radius_m
        h = self.height_m
        N = self.n_facets
        angles = np.linspace(0.0, 2.0 * np.pi, N + 1)

        normals: list[npt.NDArray[np.float64]] = []
        areas: list[float] = []

        apex = np.array([0.0, 0.0, h])

        # Lateral facets (triangles: apex → base_i → base_{i+1}).
        for i in range(N):
            v1 = np.array([r * np.cos(angles[i]), r * np.sin(angles[i]), 0.0])
            v2 = np.array(
                [r * np.cos(angles[i + 1]), r * np.sin(angles[i + 1]), 0.0]
            )
            edge_a = v1 - apex
            edge_b = v2 - apex
            cross = np.cross(edge_a, edge_b)
            mag = float(np.linalg.norm(cross))
            if mag > 0.0:
                normals.append(cross / mag)
                areas.append(0.5 * mag)

        # Base facets (fan from center, normal = −Z).
        base_normal = np.array([0.0, 0.0, -1.0])
        dtheta = 2.0 * np.pi / N
        base_wedge_area = 0.5 * r * r * np.sin(dtheta)
        for _ in range(N):
            normals.append(base_normal)
            areas.append(float(base_wedge_area))

        object.__setattr__(
            self, "_facet_normals", np.array(normals, dtype=np.float64)
        )
        object.__setattr__(
            self, "_facet_areas", np.array(areas, dtype=np.float64)
        )

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """Sum of A_f · max(0, n̂_f · v̂) over all facets."""
        v = _view_to_body(view_direction, *self.orientation_rad)
        normals: npt.NDArray[np.float64] = self._facet_normals  # type: ignore[attr-defined]
        face_areas: npt.NDArray[np.float64] = self._facet_areas  # type: ignore[attr-defined]
        dots = normals @ v
        mask = dots > 0.0
        return float(np.sum(face_areas[mask] * dots[mask]))

    def surface_area(self) -> float:
        """π·r·s + π·r² where s = √(r² + h²) is the slant height."""
        r = self.base_radius_m
        h = self.height_m
        s = math.sqrt(r ** 2 + h ** 2)
        return math.pi * r * s + math.pi * r ** 2
