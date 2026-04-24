"""Geometric primitive shapes for target modeling.

Each shape satisfies the TargetShape protocol with analytic
projected-area formulas. Split per Rule 19 — one shape per file.

See RADIANT_Source_Target_System.md §5.1.
"""

from radiant.source.shapes.box import Box  # noqa: F401
from radiant.source.shapes.cone import Cone  # noqa: F401
from radiant.source.shapes.cylinder import Cylinder  # noqa: F401
from radiant.source.shapes.flat_plate import FlatPlate  # noqa: F401
from radiant.source.shapes.sphere import Sphere  # noqa: F401

__all__ = ["Sphere", "FlatPlate", "Box", "Cylinder", "Cone"]
