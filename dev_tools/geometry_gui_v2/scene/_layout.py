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

# Ground cap radius around the target footprint. T3 of the visual
# remediation widens it from 4 m → 10 m so the gridded region extends a
# usable distance around the target without the user perceiving a hard
# edge (the outer fade plane handles the void-beyond transition).
GROUND_CAP_RADIUS_M: Final[float] = 10.0

# Outer fade-plane radius — large enough to fill the entire viewport at any
# camera distance the canonical views adopt. Below the gridded cap (z =
# -0.001) so the cap sits visually on top of the fade.
GROUND_FADE_RADIUS_M: Final[float] = 500.0

# Radius for angle arcs. Arcs live on a sphere centered on the target.
# T6 of the visual remediation widens this from 2.0 → 2.6 m so the arcs
# sit clearly outside even the largest default target body (the box
# preset has a half-extent of ~1.4 m along its diagonal). At 2.0 m the
# arcs were intersecting the target geometry and reading as "decoration
# stuck to the surface" rather than "angle between two vectors".
ARC_RADIUS_M: Final[float] = 3.4
