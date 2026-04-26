"""Composite target assembled from multiple primitives.

A composite target is a collection of shapes. Its projected area is the
sum of its constituents' projected areas (no self-occlusion in v1).
Satisfies the TargetShape protocol.

See RADIANT_Source_Target_System.md §5.2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.source.shape import TargetShape


@dataclass(frozen=True)
class CompositeTarget:
    """A target composed of one or more TargetShape primitives.

    Projected area is the sum of constituent projected areas.
    No inter-primitive occlusion testing in v1.

    Parameters
    ----------
    shapes:
        One or more shapes that make up the target.
    name:
        Human-readable label.
    """

    shapes: tuple[TargetShape, ...]
    name: str = "composite"

    def __post_init__(self) -> None:
        if len(self.shapes) == 0:
            raise ValueError(
                f"CompositeTarget '{self.name}': shapes must be non-empty. "
                f"Provide at least one TargetShape."
            )

    def projected_area(self, view_direction: npt.NDArray[np.float64]) -> float:
        """Sum of constituent projected areas [m²].

        No occlusion testing — this is exact for non-overlapping
        primitives and an overestimate for overlapping ones.
        """
        return sum(s.projected_area(view_direction) for s in self.shapes)

    def surface_area(self) -> float:
        """Sum of constituent surface areas [m²]."""
        return sum(s.surface_area() for s in self.shapes)
