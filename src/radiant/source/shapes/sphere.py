"""Sphere — orientation-independent projected area π r².

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy.typing as npt
import numpy as np

from radiant.source.shapes._helpers import validate_positive


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
        validate_positive("Sphere", self.radius_m, "radius_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """π r² regardless of view direction."""
        return math.pi * self.radius_m ** 2

    def surface_area(self) -> float:
        """4 π r²."""
        return 4.0 * math.pi * self.radius_m ** 2
