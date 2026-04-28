"""Schematic placement constants — target-centric, not-to-scale.

The actual physics (slant range = 600 km, target radius = 1 m) cannot be
rendered to scale; the satellite would be a sub-pixel speck. Per PLAN_v2.md
§3 (C5 / Rule 19) and §10 the scene draws the target at true size at the
origin and places the observer/sun glyphs at fixed *schematic* distances
along their physically correct directions, with break-marks on the
connecting lines indicating "not to scale". Phase 1 ships the schematic
distances; Phase 3 adds the break-marks and screen-space glyphs.

These constants are scene-units (meters in PyVista's coordinate space, but
without a physical interpretation — just the schematic frame).

C7: zero Qt imports.
"""

from __future__ import annotations

from typing import Final

# Schematic distances along the physically correct direction unit vectors.
# Chosen so the target body (≤ ~2 m for the default scenes) reads clearly
# while the observer/sun glyphs stay outside the target's bounding sphere.
SCENE_OBSERVER_DISTANCE_M: Final[float] = 6.0
SCENE_SUN_DISTANCE_M: Final[float] = 9.0
SCENE_BACKGROUND_DISTANCE_M: Final[float] = 12.0

# Ground cap radius around the target footprint. Phase 2 swaps this for a
# textured plane sized to the target's projected footprint plus a margin.
GROUND_CAP_RADIUS_M: Final[float] = 4.0

# Unit-radius for angle arcs. Arcs live on a sphere centered on the target.
ARC_RADIUS_M: Final[float] = 2.0
