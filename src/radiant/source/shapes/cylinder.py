"""Cylinder — right circular cylinder with axis along body +Z.

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.shapes._helpers import validate_positive, view_to_body


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
        validate_positive("Cylinder", self.radius_m, "radius_m")
        validate_positive("Cylinder", self.length_m, "length_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """2r·L·sin θ + π·r²·cos θ."""
        v = view_to_body(view_direction, *self.orientation_rad)
        r = self.radius_m
        L = self.length_m
        cos_theta = abs(float(v[2]))
        sin_theta = math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2)
        return 2.0 * r * L * sin_theta + math.pi * r ** 2 * cos_theta

    def surface_area(self) -> float:
        """2πrL + 2πr² (lateral + two caps)."""
        r = self.radius_m
        return 2.0 * math.pi * r * self.length_m + 2.0 * math.pi * r ** 2
