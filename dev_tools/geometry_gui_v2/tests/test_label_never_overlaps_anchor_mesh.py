"""Round-3 S2 hard test — label boxes never overlap their own anchor's mesh.

The constraint, per ``PLAN_v2_remediation_round3.md`` §4: a label's
screen-space bounding box must never intersect the projected screen-space
AABB of its own anchor's mesh (target body, satellite glyph, sun disc,
background sphere). Vector-midpoint and arc-midpoint anchors are exempt
— they're points along a tube/arc with no silhouette to be "inside".

This test renders each canonical view (plus the round-3 altitude sweep)
off-screen, runs the label deconfliction solver, and asserts the
invariant on every label whose anchor has a registered mesh.
"""

from __future__ import annotations

import dataclasses
from typing import Final

import numpy as np
import pytest
import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.builder import build_scene
from dev_tools.geometry_gui_v2.scene.labels import _ANCHOR_MESH_ACTORS, _projected_mesh_bbox
from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors
from dev_tools.geometry_gui_v2.scene.labels.layout import (
    LabelLayoutInput,
    solve_layout,
)
from dev_tools.geometry_gui_v2.scene.labels.leader_label import (
    LeaderLabel,
    project_world_to_display,
)
from dev_tools.geometry_gui_v2.tests.audit_round2.render_canonical_views import (
    CANONICAL_VIEWS,
    _state_for,
)


_WINDOW_SIZE: Final[tuple[int, int]] = (1920, 1080)


def _altitude_sweep_states() -> list[tuple[str, SceneState]]:
    base = SceneState.default()
    return [
        (f"alt_{km:04d}km", dataclasses.replace(base, target_altitude_m=km * 1_000.0))
        for km in (0, 1, 10, 100, 600, 2000)
    ]


def _solve_for(state: SceneState) -> tuple[
    list[str],
    list[np.ndarray],
    list[tuple[float, float]],
    list[tuple[float, float, float, float] | None],
]:
    """Render the scene off-screen, project anchors, run the solver.

    Returns parallel lists: anchor names, label center positions,
    label sizes, and per-anchor mesh bboxes (None for non-mesh anchors).
    """
    p = pv.Plotter(off_screen=True, window_size=_WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        p.show(auto_close=False)

        anchors = collect_anchors(state)
        labels = [
            LeaderLabel(
                name=a.name, anchor_world=a.anchor_world, text=a.text, color=a.color
            )
            for a in anchors
        ]
        inputs: list[LabelLayoutInput] = []
        bboxes: list[tuple[float, float, float, float] | None] = []
        for anchor, label in zip(anchors, labels):
            screen_xy = project_world_to_display(p, label.anchor_world)
            mesh_bbox = _projected_mesh_bbox(
                p, _ANCHOR_MESH_ACTORS.get(anchor.name)
            )
            bboxes.append(mesh_bbox)
            inputs.append(
                LabelLayoutInput(
                    anchor_screen_xy=np.array(screen_xy, dtype=np.float64),
                    label_size_px=label.estimated_screen_size_px(),
                    mesh_bbox_px=mesh_bbox,
                )
            )
        results = solve_layout(inputs, viewport_size_px=_WINDOW_SIZE)
        return (
            [a.name for a in anchors],
            [r.label_screen_xy for r in results],
            [tuple(label.estimated_screen_size_px()) for label in labels],
            bboxes,
        )
    finally:
        p.close()


def _label_overlaps_mesh(
    label_center: np.ndarray,
    label_size: tuple[float, float],
    mesh_bbox: tuple[float, float, float, float],
) -> bool:
    half_w, half_h = label_size[0] * 0.5, label_size[1] * 0.5
    cx_label, cy_label = label_center[0], label_center[1]
    bx_min, by_min, bx_max, by_max = mesh_bbox
    cx_mesh = 0.5 * (bx_min + bx_max)
    cy_mesh = 0.5 * (by_min + by_max)
    half_bx = 0.5 * (bx_max - bx_min)
    half_by = 0.5 * (by_max - by_min)
    gap_x = abs(cx_label - cx_mesh) - (half_w + half_bx)
    gap_y = abs(cy_label - cy_mesh) - (half_h + half_by)
    return gap_x < 0.0 and gap_y < 0.0


@pytest.mark.parametrize("view_name", CANONICAL_VIEWS)
def test_canonical_view_label_never_overlaps_anchor_mesh(view_name: str) -> None:
    state = _state_for(view_name)
    names, positions, sizes, bboxes = _solve_for(state)
    for name, pos, size, bbox in zip(names, positions, sizes, bboxes):
        if bbox is None:
            continue
        assert not _label_overlaps_mesh(pos, size, bbox), (
            f"{view_name}: label '{name}' at {tuple(pos)} (size {size}) "
            f"overlaps its anchor mesh bbox {bbox}"
        )


@pytest.mark.parametrize("name,state", _altitude_sweep_states())
def test_altitude_sweep_label_never_overlaps_anchor_mesh(
    name: str, state: SceneState
) -> None:
    names, positions, sizes, bboxes = _solve_for(state)
    for anchor_name, pos, size, bbox in zip(names, positions, sizes, bboxes):
        if bbox is None:
            continue
        assert not _label_overlaps_mesh(pos, size, bbox), (
            f"{name}: label '{anchor_name}' at {tuple(pos)} (size {size}) "
            f"overlaps its anchor mesh bbox {bbox}"
        )
