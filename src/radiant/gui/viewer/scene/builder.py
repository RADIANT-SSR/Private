"""Static-scene builder — turns a bound :class:`ViewerState` into a populated plotter.

Part-A (ADR-0007 Phase 7 tasks 1–3) renders the **static** subset only: the ground
reference, the target body (when the source declares a shape), the regime overlay, the
four geometric vectors, the sensor/sun/background glyphs, and the deconflicted leader
labels. Deferred to Part B and intentionally **not** called here: angle-arc annotations
(``arcs/``), the RPY body-axes triad (``frames/``), and the corner view-cube / gnomon
widgets (``widgets/``) — their source is not lifted yet.

Theme integration (ADR-0007 §3): the viewport background and the label/leader chrome are
resolved from the active :class:`~radiant.gui.themes.tokens.Theme` via
:class:`~radiant.gui.viewer.scene.chrome.SceneChrome`, so the panel matches the light app
and a later theme toggle restyles it. Semantic glyph colors (sun/sensor/normal/target)
stay fixed (:mod:`radiant.gui.viewer.scene.palette`).

Not-to-scale (ADR-0007 §4, owner-endorsed): altitudes/ranges are shown via **leader
labels**; geometry is never rescaled or translated to fake proportionality. Glyphs sit at
schematic display distances (``_display_distance``), not true metric range.

This module imports nothing from Qt and no physics stage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyvista as pv

from radiant.gui.viewer.scene import (
    extended_pixel_cell,
    glyphs,
    ground,
    labels,
    point_source_marker,
    target,
    vectors,
)
from radiant.gui.viewer.scene._lighting import install_lighting
from radiant.gui.viewer.scene.camera_views import set_default_camera
from radiant.gui.viewer.scene.chrome import SceneChrome
from radiant.gui.viewer.scene.framing import default_camera_distance_m

if TYPE_CHECKING:
    from radiant.gui.themes.tokens import Theme
    from radiant.gui.viewer.viewer_state import ViewerState


def build_static_scene(
    state: ViewerState,
    plotter: pv.Plotter | None = None,
    theme: Theme | None = None,
) -> pv.Plotter:
    """Populate *plotter* with the static bound scene for *state*.

    If *plotter* is ``None`` a fresh ``pv.Plotter`` is created; the GUI passes its own
    ``QtInteractor`` (a ``pv.Plotter`` subclass) so this function is identical on-screen
    and offscreen. If *theme* is ``None`` the light default is used so an un-themed
    offscreen render still resolves its chrome.

    Composition order (back to front): ground → target body → regime overlay → vectors →
    glyphs → labels. The camera is set after all 3D primitives so the label solver
    projects against the pose the next render uses.
    """
    if plotter is None:
        plotter = pv.Plotter()

    if theme is None:
        from radiant.gui.themes.tokens import LIGHT

        theme = LIGHT
    chrome = SceneChrome.from_theme(theme)

    plotter.set_background(chrome.viewport_bg)
    install_lighting(plotter, state)

    ground.add_to_plotter(plotter, state, chrome)
    # The target *body* only renders when the source declares a concrete shape; an
    # extended / sub-pixel scene (shape "none") has no discrete body — the regime
    # overlay below is its representation.
    if state.target_shape != "none":
        target.add_to_plotter(plotter, state)
    # Regime-gated overlays; each no-ops when its regime is not active (Rule 10 regime
    # from stage_outputs["optics"], carried on ViewerState.regime_override).
    extended_pixel_cell.add_to_plotter(plotter, state)
    point_source_marker.add_to_plotter(plotter, state)
    vectors.add_to_plotter(plotter, state)
    glyphs.add_to_plotter(plotter, state)

    # Camera before labels: the label solver projects anchors against the pose the next
    # render will use (the round-2 ordering invariant).
    set_default_camera(plotter, distance=default_camera_distance_m(state))

    labels.add_to_plotter(plotter, state, chrome)

    return plotter


__all__ = ["build_static_scene"]
