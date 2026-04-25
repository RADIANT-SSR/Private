"""Public re-export of unit-conversion helpers for the CLI layer.

The unit-conversion registry lives in :mod:`radiant.core.units`, but the
``cli`` layer must not reach directly into ``core``
(see ``CLAUDE.md`` import rules — cli may import only ``api`` + ``io``).
This module is the public seam.
"""

from __future__ import annotations

from radiant.core.units import _CONVERSIONS, convert

__all__ = ["_CONVERSIONS", "convert"]
