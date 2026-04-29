"""Scene builder — orchestrator that turns a ``SceneState`` into a populated
``pyvista.Plotter``.

Phase 1 contract (PLAN_v2.md §9 step 2): iterate the per-primitive modules
in a fixed order — ground → contact-shadow → target → frames → vectors →
arcs → glyphs → labels — and call each module's ``add_to_plotter`` helper.
The ground/contact-shadow split is folded into ``scene.ground`` (its own
package handles both in the documented order).

C7: this module imports nothing from Qt. The plotter object is consumed
by the Qt shell via ``pyvistaqt.QtInteractor``, but PyVista itself does
not depend on Qt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyvista as pv

from dev_tools.geometry_gui_v2.scene import (
    arcs,
    frames,
    glyphs,
    ground,
    labels,
    target,
    vectors,
)
from dev_tools.geometry_gui_v2.scene._lighting import install_lighting
from dev_tools.geometry_gui_v2.scene.camera_views import set_default_camera
from dev_tools.geometry_gui_v2.scene.framing import default_camera_distance_m
from dev_tools.geometry_gui_v2.scene.style import VIEWPORT_BACKGROUND_COLOR

if TYPE_CHECKING:
    from dev_tools.geometry_gui_v2.app.state import SceneState


def build_scene(
    state: "SceneState",
    plotter: pv.Plotter | None = None,
) -> pv.Plotter:
    """Populate a ``pv.Plotter`` from a ``SceneState``.

    If ``plotter`` is ``None``, a fresh on-screen plotter is created. The
    Qt shell passes its own ``QtInteractor`` instance (which subclasses
    ``pv.Plotter``), so this function is identical whether driven from a
    notebook or from the desktop app.

    Iteration order matches PLAN_v2.md §9 step 2:
      1. ground (cap + contact shadow)
      2. target body
      3. reference frames (body + world axes)
      4. geometric vectors (boresight, n_B, s_t, s_B)
      5. angle arcs (off-nadir, alpha_t, theta_sun)
      6. glyphs (observer, sun, background)
      7. labels (Phase 1 stub)
    """
    if plotter is None:
        plotter = pv.Plotter()

    plotter.set_background(VIEWPORT_BACKGROUND_COLOR)
    install_lighting(plotter, state)

    ground.add_to_plotter(plotter, state)
    target.add_to_plotter(plotter, state)
    frames.add_to_plotter(plotter, state)
    vectors.add_to_plotter(plotter, state)
    arcs.add_to_plotter(plotter, state)
    glyphs.add_to_plotter(plotter, state)

    # R1: set the default camera AFTER all 3D primitives are added so
    # the labels solver projects against the same camera the next render
    # will use. Labels used to call reset_camera() themselves; that
    # discarded any pose set earlier in this function. The default pose
    # is the round-2 isometric three-quarter view (25° elev / 45° az).
    # R2: distance is extent-driven so the scene fills the majority of
    # the canvas regardless of target size or geometry.
    set_default_camera(plotter, distance=default_camera_distance_m(state))

    labels.add_to_plotter(plotter, state)

    return plotter
