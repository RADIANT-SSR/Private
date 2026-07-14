"""Schematic glyph display distance — scales with target altitude.

Round-3 S5 (PLAN_v2_remediation_round3.md §7): pre-S5 the satellite,
sun, and background-marker glyphs were anchored at fixed scene-meter
distances *from the world origin* — ``direction * SCENE_*_DISTANCE_M``.
That made sense in round 1 when the target sat at the origin. Round 2
introduced the schematic altitude lift (``schematic_lift_m`` in
``scene/target/_pose.py``) which pushes the target centroid up to
z ≈ 4–5 m at high altitudes; the glyphs stayed at their original world
positions, so at high target altitude the lifted target visually
intruded on (or in the round-three reel's slant=0 case, *passed*) the
satellite glyph.

S5 fixes this two ways:

1. Anchor the glyph display position at ``target_centroid + display *
   direction`` instead of at ``direction * fixed_scene_distance``.
   This alone keeps the glyph the same schematic distance "above" the
   target at every altitude.

2. Grow ``display`` with target altitude so the glyph does not collapse
   onto a target that has rotated or grown. The altitude term is
   ``target_altitude_m / 50_000`` (i.e. km / 50): at 600 km altitude the
   scene extent grows to 12 m and the satellite ends up ~36 m from the
   target along the boresight; at 2000 km it grows to 40 m and ~120 m.
   The framing policy in ``scene/framing.py`` reads the same display
   distances via the per-glyph helper so the camera pulls back to keep
   the full scene in frame.

Pure function — no Qt, no PyVista, only stdlib + ``SceneState``.
Rule 19: this module owns the schematic-distance scaling formula; each
glyph file picks the floor (``SCENE_OBSERVER_DISTANCE_M`` etc.) and the
direction unit vector.
"""

from __future__ import annotations

from typing import Final

from radiant.gui.viewer.viewer_state import ViewerState as SceneState

# Altitude term divisor — tuned so 600 km altitude maps to 12 m of
# scene extent (3 × 12 = 36 m display distance). Above this floor, the
# display distance grows linearly with altitude; below, the per-glyph
# floor (``base_distance_m``) is unchanged.
_ALTITUDE_DIVISOR_M: Final[float] = 50_000.0

# Plan §7 step 1: ``display_distance = 3.0 * scene_extent``.
_DISTANCE_MULTIPLIER: Final[float] = 3.0


def schematic_display_distance_m(state: SceneState, base_distance_m: float) -> float:
    """Glyph display distance from ``target_centroid`` along its
    direction unit vector.

    ``base_distance_m`` is the round-1 schematic floor for this glyph
    (``SCENE_OBSERVER_DISTANCE_M``, ``SCENE_SUN_DISTANCE_M``, or
    ``SCENE_BACKGROUND_DISTANCE_M``). At low altitudes the floor is
    returned unchanged so the default-state visuals are preserved; the
    altitude term takes over above ~50 km of target altitude.
    """
    target_max_extent = _target_max_extent_m(state)
    altitude_scale = state.target_altitude_m / _ALTITUDE_DIVISOR_M
    scene_extent = max(target_max_extent, altitude_scale)
    return max(base_distance_m, _DISTANCE_MULTIPLIER * scene_extent)


def _target_max_extent_m(state: SceneState) -> float:
    """Largest full dimension of the target's body-frame AABB.

    Mirrors ``framing._target_half_extent`` but returns the *full*
    extent (twice the half-extent) since plan §7's formula uses
    ``target_max_extent``, not ``target_half_extent``.
    """
    kind = state.target_shape
    if kind == "sphere":
        return 2.0 * state.target_radius_m
    if kind == "cylinder":
        return max(2.0 * state.target_radius_m, state.target_length_m)
    if kind == "cone":
        return max(2.0 * state.target_base_radius_m, state.target_height_m)
    if kind == "box":
        return max(
            state.target_width_m,
            state.target_length_m,
            state.target_height_m,
        )
    if kind == "flat_plate":
        return max(state.target_width_m, state.target_length_m)
    return 2.0
