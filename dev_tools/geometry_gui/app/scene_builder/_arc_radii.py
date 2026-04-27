"""Per-group display radii for arc annotations.

Phase 11 (PLAN.md §12). Earlier phases used a single `ARC_DISPLAY_RADIUS`
for every arc, which causes overlap when multiple arcs share an anchor
(e.g. observer-anchored off-nadir + az + el at the target). This table
gives each angle group its own concentric radius so arcs nest visibly
rather than piling up.

This file is internal to the scene-builder package. Each arc module
reads its radius via `arc_radius_for(<key>)` instead of importing the
shared default. Tests pin the table contents.
"""

from __future__ import annotations

from typing import Final

# Per-arc display radii (illustrative; PLAN.md §12 frozen mapping).
ARC_DISPLAY_RADII: Final[dict[str, float]] = {
    "off_nadir": 0.40,
    "azimuth": 0.40,
    "elevation": 0.40,
    "phase_angle": 0.60,
    "sun_zenith": 0.80,
    "sun_azimuth": 0.80,
    "solar_zenith_b": 0.45,
}


def arc_radius_for(key: str) -> float:
    """Return the display radius for `key`. Raises KeyError on unknown keys."""
    return ARC_DISPLAY_RADII[key]
