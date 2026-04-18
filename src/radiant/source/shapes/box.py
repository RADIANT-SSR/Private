"""Box — rectangular box (6 flat faces).

See RADIANT_Source_Target_System.md §5.1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.shapes._helpers import validate_positive, view_to_body


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
        validate_positive("Box", self.length_m, "length_m")
        validate_positive("Box", self.width_m, "width_m")
        validate_positive("Box", self.height_m, "height_m")

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """Sum of face-pair projections.

        A = W·H·|vx| + L·H·|vy| + L·W·|vz| in body frame.
        """
        v = view_to_body(view_direction, *self.orientation_rad)
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
