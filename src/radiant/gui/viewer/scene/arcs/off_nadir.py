"""Off-nadir arc (η) — angle between the local zenith (+Z) and the boresight.

Great-arc tube from +Z to the observer-direction unit vector at ``ARC_RADIUS_M``, drawn
in ``SATELLITE_FAMILY`` (the off-nadir angle is part of the satellite-vector family).

The observer direction comes from ``ViewerState.observer_look_angle_rad`` — which the
adapter binds verbatim to ``stage_outputs["geometry"]["eta_rad"]`` (ADR-0007 §2). The arc
is therefore a schematic *drawing* of the stage's η; the numeric value the viewer pins to
it comes from the stage output, never from this geometry (arch doc §6.3).
"""

from __future__ import annotations

import numpy as np
import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import observer_direction_scene
from radiant.gui.viewer.scene._layout import ARC_RADIUS_M
from radiant.gui.viewer.scene.arcs._arc import add_great_arc
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    obs = observer_direction_scene(state)
    add_great_arc(
        plotter,
        zenith,
        obs,
        radius=ARC_RADIUS_M,
        color=style.SATELLITE_FAMILY,
        name="arc_off_nadir",
    )
