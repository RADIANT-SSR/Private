"""Cone — right circular cone with base at z=0, apex at z=height.

Uses a faceted approximation for projected area.
See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.shapes._helpers import validate_positive, view_to_body


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
        validate_positive("Cone", self.base_radius_m, "base_radius_m")
        validate_positive("Cone", self.height_m, "height_m")
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
            v2 = np.array([r * np.cos(angles[i + 1]), r * np.sin(angles[i + 1]), 0.0])
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

        object.__setattr__(self, "_facet_normals", np.array(normals, dtype=np.float64))
        object.__setattr__(self, "_facet_areas", np.array(areas, dtype=np.float64))

    def projected_area(self, view_direction: npt.NDArray[np.float64]) -> float:
        """Sum of A_f · max(0, n̂_f · v̂) over all facets."""
        v = view_to_body(view_direction, *self.orientation_rad)
        normals: npt.NDArray[np.float64] = self._facet_normals  # type: ignore[attr-defined]
        face_areas: npt.NDArray[np.float64] = self._facet_areas  # type: ignore[attr-defined]
        dots = normals @ v
        mask = dots > 0.0
        return float(np.sum(face_areas[mask] * dots[mask]))

    def surface_area(self) -> float:
        """π·r·s + π·r² where s = √(r² + h²) is the slant height."""
        r = self.base_radius_m
        h = self.height_m
        s = math.sqrt(r**2 + h**2)
        return math.pi * r * s + math.pi * r**2
