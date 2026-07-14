"""Phase-angle arc (α_t) — angle between the sun and observer directions at the target.

Great-arc tube from the sun direction to the observer direction at ``ARC_RADIUS_M``, drawn
in ``TARGET_VECTOR_FAMILY`` (desaturated teal), the prototype convention for the at-target
phase angle.

**No stage-output truth.** The phase angle is *not* an emitted ``stage_outputs["geometry"]``
value, so — unlike the off-nadir (η) and sun-zenith (θ_s) arcs — the viewer draws this arc
as a geometric annotation but pins **only its symbol** (α_t), never a fabricated numeric
value (arch doc §6.3: "the viewer never computes physics angles for display"). It is
therefore excluded from the angle-truth consistency check (``angle_truth`` has no key for
it), analogous to the MTF-only TDI term's exclusion from the Rule-4 consistency compare.
"""

from __future__ import annotations

import pyvista as pv

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import (
    observer_direction_scene,
    sun_direction_scene,
)
from radiant.gui.viewer.scene._layout import ARC_RADIUS_M
from radiant.gui.viewer.scene.arcs._arc import add_great_arc
from radiant.gui.viewer.viewer_state import ViewerState as SceneState


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    add_great_arc(
        plotter,
        sun_direction_scene(state),
        observer_direction_scene(state),
        radius=ARC_RADIUS_M,
        color=style.TARGET_VECTOR_FAMILY,
        name="arc_phase_angle",
    )
