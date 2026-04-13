"""Target shape protocol for geometric primitives.

Defines the contract that all target shapes (sphere, cylinder, box,
flat plate, cone) must satisfy. Shapes compute projected area as seen
from a given view direction, and total surface area.

See RADIANT_Source_Target_System.md §5.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt


@runtime_checkable
class TargetShape(Protocol):
    """Protocol for target geometric primitives.

    Every shape must compute projected area (as seen from a given
    view direction) and total surface area. All areas in m².

    The ``view_direction`` is a unit 3-vector in the scene frame,
    pointing from the target toward the observer (per §5.2:
    ``(observer_position - target_position).normalized()``).
    A surface element is visible when its outward normal has a
    positive dot product with the view direction.
    """

    def projected_area(
        self, view_direction: npt.NDArray[np.float64]
    ) -> float:
        """Projected area [m²] as seen from view_direction.

        Parameters
        ----------
        view_direction:
            Unit 3-vector in scene frame, target → observer.

        Returns
        -------
        float
            Projected area in m². Always ≥ 0.
        """
        ...

    def surface_area(self) -> float:
        """Total surface area [m²]."""
        ...
