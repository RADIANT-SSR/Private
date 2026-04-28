"""Scene lighting — directional sun + ambient fill.

Phase 2 (PLAN_v2.md §10 step 2): a single directional light pointing from
the sun glyph position toward the target centroid (so the lit hemisphere
on the target body is physically correct), plus a faint ambient fill so
the dark side reads as shadowed rather than pitch-black.

Rule 19: own file — distinct from glyphs/sun.py (which draws the visual
sun marker). The lighting and the marker share the same direction vector
but they are separate concerns: the marker is a geometric primitive, the
light is a render-state setup that the target's PBR shader consumes.

C7: zero Qt imports.
"""

from __future__ import annotations

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene._directions import sun_direction_scene
from dev_tools.geometry_gui_v2.scene._layout import SCENE_SUN_DISTANCE_M

# Intensities chosen per PLAN_v2.md §10 step 2: directional light at 1.0,
# faint ambient fill at 0.15 so the dark side has detail without competing
# with the lit side.
_SUN_INTENSITY = 1.0
_AMBIENT_INTENSITY = 0.15


def install_lighting(plotter: pv.Plotter, state: SceneState) -> None:
    """Replace the plotter's default lights with sun + ambient fill.

    PyVista's default plotter ships with three lights aimed for general-
    purpose scenes; for a physically meaningful sun terminator we want a
    single directional sun + a low-intensity ambient. ``remove_all_lights``
    clears the defaults; the two new lights are then registered.
    """
    plotter.remove_all_lights()

    sun_pos = sun_direction_scene(state) * SCENE_SUN_DISTANCE_M
    sun_light = pv.Light(
        position=tuple(sun_pos),
        focal_point=(0.0, 0.0, 0.0),
        intensity=_SUN_INTENSITY,
        light_type="scene light",
    )
    plotter.add_light(sun_light)

    ambient = pv.Light(
        light_type="headlight",
        intensity=_AMBIENT_INTENSITY,
    )
    plotter.add_light(ambient)
