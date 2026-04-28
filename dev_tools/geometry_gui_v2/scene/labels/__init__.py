"""Labels package — collect every primitive's anchor, deconflict in
screen space, render leader-labels.

Phase 4 wiring (PLAN_v2.md §12 step 3): a single ``add_to_plotter``
orchestrates anchor collection, screen-space layout, and leader-label
rendering. Per-primitive label data lives in ``_anchors.py``; the layout
solver lives in ``layout.py``; the renderer lives in ``leader_label.py``.

C7: this package imports nothing from Qt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    """Phase-4 entry point — replaces the Phase-1 ``add_point_labels`` stub.

    Steps:
      1. Reset the camera so the screen-projection inputs the layout
         solver sees match what the next ``screenshot`` / ``show`` call
         will render. Without this, the projection silently uses a
         default identity camera and every label lands at (0, 0).
      2. Project every anchor's world position to display (pixel) coords.
      3. Run the force-directed solver to assign per-label screen
         positions that don't overlap.
      4. Render each LeaderLabel — a vtkTextActor at the label position
         + a vtkLeaderActor2D from anchor → label.
    """
    from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors
    from dev_tools.geometry_gui_v2.scene.labels.layout import (
        LabelLayoutInput,
        solve_layout,
    )
    from dev_tools.geometry_gui_v2.scene.labels.leader_label import (
        LeaderLabel,
        add_leader_label,
        project_world_to_display,
    )

    anchors = collect_anchors(state)
    if not anchors:
        return

    plotter.reset_camera()

    labels = [
        LeaderLabel(
            name=a.name, anchor_world=a.anchor_world, text=a.text, color=a.color
        )
        for a in anchors
    ]

    win_size = plotter.window_size  # (w, h) in pixels
    inputs: list[LabelLayoutInput] = []
    anchor_screens: list[tuple[float, float]] = []
    for label in labels:
        screen_xy = project_world_to_display(plotter, label.anchor_world)
        anchor_screens.append(screen_xy)
        inputs.append(
            LabelLayoutInput(
                anchor_screen_xy=np.array(screen_xy, dtype=np.float64),
                label_size_px=label.estimated_screen_size_px(),
            )
        )

    results = solve_layout(inputs, viewport_size_px=(int(win_size[0]), int(win_size[1])))
    for label, result, anchor_screen in zip(labels, results, anchor_screens):
        add_leader_label(
            plotter,
            label,
            label_screen_xy=tuple(result.label_screen_xy),
            anchor_screen_xy=anchor_screen,
        )
