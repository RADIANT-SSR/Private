"""Public re-export of unit-conversion helpers for the CLI and GUI layers.

The unit-conversion registry lives in :mod:`radiant.core.units`, but the
``cli`` layer must not reach directly into ``core``
(see ``CLAUDE.md`` import rules — cli may import only ``api`` + ``io``).
This module is the public seam.

Unit *enumeration* is exposed through named accessors — :func:`units_for`,
:func:`input_units`, :func:`targets_for` (CU-109) — rather than the underscored
``_CONVERSIONS`` registry, which stays private to ``core``.
"""

from __future__ import annotations

from radiant.core.units import (
    convert,
    input_units,
    inverse_convert,
    targets_for,
    units_for,
)

__all__ = [
    "convert",
    "input_units",
    "inverse_convert",
    "targets_for",
    "units_for",
]
