"""Visual-scene-frame direction unit vectors derived from ``SceneState``.

These helpers compute the unit vectors the visual primitives consume. They
intentionally use a *visual* scene convention — distinct from the
``view_model.compute_view_direction_scene`` convention, which is rooted in
the observer body frame and is harder to read at a glance.

**Visual scene convention** (this file):
  * +Z = local zenith at the target (intuitive "up")
  * +X = projected look azimuth (look-direction's horizontal component)
  * +Y = orthogonal complement (right-hand rule)
  * Origin = target centroid

This is *only* the visual placement frame for the scene library. Physics
quantities — projected area, regime classification, slant range, GSD —
remain authoritative in ``view_model.py`` and use the body-frame-rooted
convention from CLAUDE.md §"Coordinate System". The two frames meet at
the readout panel (Phase 4): visual-scene-frame for placement, view-model
for numbers. The C3 invariant (``A_t`` shown = ``shape.projected_area``)
is unaffected because it never goes through this file.

C6 / C7:
  * No private ``radiant`` symbols.
  * No Qt imports.
  * Only stdlib + numpy.

Rule 19: distinct from ``_layout.py`` (scalar lengths) and from any
view_model file. This file owns the visual-scene-frame unit-vector math.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def observer_direction_scene(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit vector from target → observer (visual scene frame).

    Off-nadir angle is the slider's ``observer_look_angle_rad``. Observer
    azimuth is taken as 0 (along +X) — the scene rotates around this
    axis when the user re-orients the camera. Returns a unit-norm vector
    by construction.
    """
    theta = state.observer_look_angle_rad
    return np.array([math.sin(theta), 0.0, math.cos(theta)], dtype=np.float64)


def sun_direction_scene(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit vector from target → sun (visual scene frame).

    Solar zenith ``θ_s`` is measured from local zenith (+Z). The sun's
    azimuth is placed at ``observer_azimuth + relative_azimuth_rad`` ; the
    observer azimuth is 0 by convention (see ``observer_direction_scene``),
    so the sun azimuth equals the relative azimuth.
    """
    theta_s = state.solar_zenith_rad
    phi = state.relative_azimuth_rad
    sin_z = math.sin(theta_s)
    return np.array(
        [sin_z * math.cos(phi), sin_z * math.sin(phi), math.cos(theta_s)],
        dtype=np.float64,
    )


def background_direction_scene(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit vector toward the background marker (visual scene frame).

    Phase 1 places the background along the *anti-sun* ray — the
    radiometry's "anti-solar / cold-background" position. Phase 4
    replaces this with a per-``state.background_kind`` placement (e.g.
    ground patch, cold-space marker).
    """
    return -sun_direction_scene(state)
