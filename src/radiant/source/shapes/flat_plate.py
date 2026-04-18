"""FlatPlate — rectangular plate with normal along body +Z.

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.shapes._helpers import validate_positive, view_to_body


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
        validate_positive("FlatPlate", self.length_m, "length_m")
        validate_positive("FlatPlate", self.width_m, "width_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """L × W × |cos θ|. Zero at edge-on."""
        v = view_to_body(view_direction, *self.orientation_rad)
        return self.length_m * self.width_m * abs(float(v[2]))

    def surface_area(self) -> float:
        """2 × L × W (front + back)."""
        return 2.0 * self.length_m * self.width_m
