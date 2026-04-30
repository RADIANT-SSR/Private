"""Round-3 S3 hard test — central-cluster labels spread out, not piled up.

The constraint, per ``PLAN_v2_remediation_round3.md`` §5: the cluster of
six labels whose anchors project near the target centroid (``θ_off``,
``s_t``, ``θ_s``, ``α_t``, ``o``, ``n_B``) must be distributed around
the target after solver convergence — not piled up on the same screen
point.

Quantitative gate: the standard deviation of those labels' final screen
positions must exceed 60 px (i.e. labels are spread, not clumped). This
is the "central cluster is spread out" assertion from plan §5 step 3.

The test renders the default scene (with ``background_kind="ground"``
so all six cluster anchors are present) off-screen and runs the
deconfliction solver; it asserts the spread invariant on the converged
layout.
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


_WINDOW_SIZE: Final[tuple[int, int]] = (1920, 1080)
_MIN_STD_PX: Final[float] = 60.0

# Anchor names that form the "central cluster" — the angle arc midpoints
# and the vector midpoints whose 3D positions project to nearly the same
# screen point as the target centroid in the default look-down camera.
_CENTRAL_CLUSTER_ANCHOR_NAMES: Final[tuple[str, ...]] = (
    "lbl_arc_off_nadir",
    "lbl_vec_sun_ray",
    "lbl_arc_sun_zenith",
    "lbl_arc_phase_angle",
    "lbl_vec_boresight",
    "lbl_vec_surface_normal",
)


def _solve_default_with_background() -> dict[str, np.ndarray]:
    """Render default-with-background, run the layout solver, return a
    dict mapping anchor name to converged label center (screen px).
    """
    state = dataclasses.replace(SceneState.default(), background_kind="ground")
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
        for anchor, label in zip(anchors, labels):
            screen_xy = project_world_to_display(p, label.anchor_world)
            mesh_bbox = _projected_mesh_bbox(p, _ANCHOR_MESH_ACTORS.get(anchor.name))
            inputs.append(
                LabelLayoutInput(
                    anchor_screen_xy=np.array(screen_xy, dtype=np.float64),
                    label_size_px=label.estimated_screen_size_px(),
                    mesh_bbox_px=mesh_bbox,
                )
            )
        results = solve_layout(inputs, viewport_size_px=_WINDOW_SIZE)
        return {a.name: r.label_screen_xy for a, r in zip(anchors, results)}
    finally:
        p.close()


def test_central_cluster_is_spread_out() -> None:
    """The six central-cluster labels must be distributed around the
    target after deconfliction, not piled up.

    Round-3 §0 defect 1: all six anchors project to nearly the same
    screen point (the target centroid in the look-down view), and the
    pre-S3 solver could not pull them apart from a near-co-located
    initial state. After the S3 retune (cluster detection + angular
    initial spread + halved attraction + boosted repulsion), the
    converged label positions have std distance > 60 px.
    """
    positions_by_name = _solve_default_with_background()
    cluster_positions = [
        positions_by_name[name] for name in _CENTRAL_CLUSTER_ANCHOR_NAMES
    ]
    assert len(cluster_positions) == len(_CENTRAL_CLUSTER_ANCHOR_NAMES), (
        f"missing one or more central-cluster anchors; "
        f"have {sorted(positions_by_name.keys())}"
    )
    xs = np.array([p[0] for p in cluster_positions], dtype=np.float64)
    ys = np.array([p[1] for p in cluster_positions], dtype=np.float64)
    std_distance = float(np.sqrt(np.var(xs) + np.var(ys)))
    assert std_distance > _MIN_STD_PX, (
        f"central cluster labels are piled up; "
        f"std distance = {std_distance:.1f} px (need > {_MIN_STD_PX:.1f}); "
        f"positions = {dict(zip(_CENTRAL_CLUSTER_ANCHOR_NAMES, cluster_positions))!r}"
    )
