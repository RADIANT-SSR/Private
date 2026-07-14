"""Sun-zenith arc (θ_s) — angle between the local zenith (+Z) and the sun direction.

Great-arc tube from +Z to the sun-direction unit vector at ``ARC_RADIUS_M``, drawn in
``SOLAR_FAMILY``. The sun direction comes from ``ViewerState.solar_zenith_rad`` /
``relative_azimuth_rad`` — bound verbatim to ``stage_outputs["geometry"]["theta_s_rad"]``
and ``["delta_phi_rad"]`` (ADR-0007 §2). The pinned numeric value is the stage's θ_s.
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import sun_direction_scene
from radiant.gui.viewer.scene._layout import ARC_RADIUS_M
from radiant.gui.viewer.scene.arcs._arc import add_great_arc
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    add_great_arc(
        plotter,
        zenith,
        sun_direction_scene(state),
        radius=ARC_RADIUS_M,
        color=style.SOLAR_FAMILY,
        name="arc_sun_zenith",
    )
