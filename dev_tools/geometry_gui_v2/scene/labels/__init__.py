"""Labels package — collect every primitive's anchor, deconflict in
screen space, render leader-labels.

Phase 4 wiring (PLAN_v2.md §12 step 3): a single ``add_to_plotter``
orchestrates anchor collection, screen-space layout, and leader-label
rendering. Per-primitive label data lives in ``_anchors.py``; the layout
solver lives in ``layout.py``; the renderer lives in ``leader_label.py``.

Round-3 S2: anchors whose primitive is a *mesh* (target body, satellite
glyph, sun disc, background sphere) supply the projected screen-space
AABB of that mesh to the layout solver so the label box can be kept
outside the mesh silhouette.

C7: this package imports nothing from Qt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np

from dev_tools.geometry_gui_v2.app.state import SceneState

if TYPE_CHECKING:
    import pyvista as pv


# Round-3 S2: anchors whose label must stay outside the silhouette of a
# rendered mesh. Maps anchor name → primary actor name. Vector-midpoint
# and arc-midpoint anchors are intentionally absent — they're points
# along a tube/arc, not silhouettes the label can be "inside".
_ANCHOR_MESH_ACTORS: Final[dict[str, str]] = {
    "lbl_target": "target",
    "lbl_observer": "glyph_observer",
    "lbl_sun": "glyph_sun",
    "lbl_background": "glyph_background",
}


def _projected_mesh_bbox(
    plotter: "pv.Plotter", actor_name: str | None
) -> tuple[float, float, float, float] | None:
    """Project the 8 corners of an actor's world-space AABB to display
    pixels and return the screen-space AABB padded by
    ``MESH_EXCLUSION_PADDING_PX``.

    Returns ``None`` if ``actor_name`` is ``None`` or the actor is not in
    the plotter — the layout solver treats ``None`` as "no exclusion
    zone" and falls back to the standard repulsion / clamp behavior.
    """
    if actor_name is None:
        return None
    actor = plotter.actors.get(actor_name)
    if actor is None:
        return None
    from dev_tools.geometry_gui_v2.scene.labels.layout import (
        MESH_EXCLUSION_PADDING_PX as PAD,
    )
    from dev_tools.geometry_gui_v2.scene.labels.leader_label import (
        project_world_to_display,
    )

    bounds = actor.GetBounds()
    if bounds is None:
        return None
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    if xmax < xmin or ymax < ymin or zmax < zmin:
        return None

    corners_world = np.array(
        [
            (xmin, ymin, zmin),
            (xmax, ymin, zmin),
            (xmin, ymax, zmin),
            (xmax, ymax, zmin),
            (xmin, ymin, zmax),
            (xmax, ymin, zmax),
            (xmin, ymax, zmax),
            (xmax, ymax, zmax),
        ],
        dtype=np.float64,
    )
    xs: list[float] = []
    ys: list[float] = []
    for corner in corners_world:
        px, py = project_world_to_display(plotter, corner)
        xs.append(px)
        ys.append(py)

    return (min(xs) - PAD, min(ys) - PAD, max(xs) + PAD, max(ys) + PAD)


def remove_from_plotter(plotter: "pv.Plotter") -> None:
    """Remove every label-pair actor that ``add_to_plotter`` previously added.

    Used by the camera-change rebuild path: rotating the camera invalidates
    every projected anchor pixel coordinate, so the label set must be torn
    down and re-added against the new projection.
    """
    from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors

    # Use the default state purely to enumerate the anchor names — the names
    # are state-independent (one per labeled primitive). Ask state.default()
    # rather than passing the live state so this helper is callable even from
    # a context that doesn't yet have one (e.g. teardown paths).
    state_for_names = SceneState.default()
    for anchor in collect_anchors(state_for_names):
        for suffix in ("_text", "_leader", "_dot"):
            actor_name = f"{anchor.name}{suffix}"
            try:
                plotter.remove_actor(actor_name)
            except Exception:
                # The actor may not exist (first call, or partial build);
                # remove_actor is idempotent in spirit but raises on miss
                # in some PyVista versions.
                pass


def add_to_plotter(plotter: "pv.Plotter", state: SceneState) -> None:
    """Phase-4 entry point — replaces the Phase-1 ``add_point_labels`` stub.

    Steps:
      1. Project every anchor's world position to display (pixel) coords
         using the camera the call site has already set on the plotter.
         R1 of round-2 visual remediation: ``builder.build_scene`` now
         calls ``set_default_camera`` immediately before this function,
         so the projection is well-defined. Earlier code reset the
         camera here, which silently discarded any pose the call site
         had set.
      2. Run the force-directed solver to assign per-label screen
         positions that don't overlap.
      3. Render each LeaderLabel — a vtkTextActor at the label position
         + a vtkLeaderActor2D from anchor → label.
    """
    from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors
    from dev_tools.geometry_gui_v2.scene.labels.layout import (
        MESH_EXCLUSION_PADDING_PX,
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

    labels = [
        LeaderLabel(
            name=a.name, anchor_world=a.anchor_world, text=a.text, color=a.color
        )
        for a in anchors
    ]

    win_size = plotter.window_size  # (w, h) in pixels
    inputs: list[LabelLayoutInput] = []
    anchor_screens: list[tuple[float, float]] = []
    for anchor, label in zip(anchors, labels):
        screen_xy = project_world_to_display(plotter, label.anchor_world)
        anchor_screens.append(screen_xy)
        mesh_bbox_px = _projected_mesh_bbox(
            plotter, _ANCHOR_MESH_ACTORS.get(anchor.name)
        )
        inputs.append(
            LabelLayoutInput(
                anchor_screen_xy=np.array(screen_xy, dtype=np.float64),
                label_size_px=label.estimated_screen_size_px(),
                mesh_bbox_px=mesh_bbox_px,
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
