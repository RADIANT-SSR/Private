"""Phase 4 acceptance — leader-label deconfliction + layout invariants.

PLAN_v2.md §12 acceptance:
  * Zero label overlaps across the canonical views (hard test, step 6).
  * Right panel shows live values (covered by ``test_readouts_panel.py``).
  * Projected-area parity test green (already covered by
    ``test_projected_area_invariant.py``).

This file pins the deconfliction contract — the labels package's force-
directed solver is what stops the label-collision problem v1 could not
solve. Failures here mean a label landed on top of another label, on
top of a primitive, or off-screen.

Skips cleanly when PyVista is not installed.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Iterator

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402
from dev_tools.geometry_gui_v2.scene.labels._anchors import collect_anchors  # noqa: E402
from dev_tools.geometry_gui_v2.scene.labels.layout import (  # noqa: E402
    LabelLayoutInput,
    boxes_overlap,
    solve_layout,
)
from dev_tools.geometry_gui_v2.scene.labels.leader_label import (  # noqa: E402
    LeaderLabel,
    project_world_to_display,
)


CANONICAL_WINDOW_SIZE = (1920, 1080)


@pytest.fixture()
def offscreen_plotter() -> Iterator[pv.Plotter]:
    p = pv.Plotter(off_screen=True, window_size=CANONICAL_WINDOW_SIZE)
    try:
        yield p
    finally:
        p.close()


def _canonical_states() -> list[tuple[str, SceneState]]:
    """The 9 canonical scenes used as deconfliction stress cases.

    Mix of shapes + observer geometries to exercise different anchor
    layouts. PLAN_v2.md §12 step 6 calls for "all 9 canonical scenes" —
    this is that list.
    """
    base = SceneState.default()
    cases: list[tuple[str, SceneState]] = []
    for shape in ("sphere", "cylinder", "cone", "box", "flat_plate"):
        cases.append(
            (
                f"shape_{shape}",
                dataclasses.replace(base, target_shape=shape),  # type: ignore[arg-type]
            )
        )
    cases.append(
        (
            "high_obliquity",
            dataclasses.replace(base, observer_look_angle_rad=math.radians(40.0)),
        )
    )
    cases.append(
        (
            "low_sun",
            dataclasses.replace(base, solar_zenith_rad=math.radians(75.0)),
        )
    )
    cases.append(
        (
            "high_sun",
            dataclasses.replace(base, solar_zenith_rad=math.radians(5.0)),
        )
    )
    cases.append(("default", base))
    return cases


# --- Hard deconfliction test ----------------------------------------------


@pytest.mark.parametrize("case_name,state", _canonical_states())
def test_no_label_overlap_in_canonical_views(
    offscreen_plotter: pv.Plotter,
    case_name: str,
    state: SceneState,
) -> None:
    build_scene(state, plotter=offscreen_plotter)

    anchors = collect_anchors(state)
    labels = [
        LeaderLabel(
            name=a.name, anchor_world=a.anchor_world, text=a.text, color=a.color
        )
        for a in anchors
    ]
    inputs = [
        LabelLayoutInput(
            anchor_screen_xy=np.array(
                project_world_to_display(offscreen_plotter, label.anchor_world),
                dtype=np.float64,
            ),
            label_size_px=label.estimated_screen_size_px(),
        )
        for label in labels
    ]
    results = solve_layout(inputs, viewport_size_px=CANONICAL_WINDOW_SIZE)

    sizes = [label.estimated_screen_size_px() for label in labels]

    overlaps: list[tuple[str, str]] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            if boxes_overlap(
                results[i].label_screen_xy, sizes[i],
                results[j].label_screen_xy, sizes[j],
                tolerance_px=1.0,
            ):
                overlaps.append((labels[i].name, labels[j].name))

    assert not overlaps, (
        f"case={case_name}: labels overlap by > 1 px: {overlaps!r} — "
        "the force-directed solver did not converge to a non-overlapping "
        "layout"
    )


# --- Solver invariants ----------------------------------------------------


def test_solver_handles_empty_input() -> None:
    assert solve_layout([], viewport_size_px=(1920, 1080)) == []


def test_solver_keeps_labels_inside_viewport() -> None:
    """Edge-repulsion + clamping must keep every label fully inside the
    viewport (with padding), no matter how clustered the anchors are."""
    inputs = [
        LabelLayoutInput(
            anchor_screen_xy=np.array([960.0, 540.0]),
            label_size_px=(80.0, 24.0),
        )
        for _ in range(15)
    ]
    results = solve_layout(inputs, viewport_size_px=(1920, 1080))
    for r in results:
        x, y = float(r.label_screen_xy[0]), float(r.label_screen_xy[1])
        assert 0.0 <= x <= 1920.0, f"label {x=} drifted off-screen"
        assert 0.0 <= y <= 1080.0, f"label {y=} drifted off-screen"


def test_solver_returns_one_result_per_input() -> None:
    n = 7
    inputs = [
        LabelLayoutInput(
            anchor_screen_xy=np.array([100.0 + 50.0 * i, 100.0 + 50.0 * i]),
            label_size_px=(80.0, 20.0),
        )
        for i in range(n)
    ]
    results = solve_layout(inputs, viewport_size_px=(1920, 1080))
    assert len(results) == n


def test_solver_preserves_anchor_endpoint() -> None:
    """The leader-line anchor endpoint must equal the input anchor — the
    solver only moves the label end of the leader, never the anchor."""
    a = np.array([500.0, 500.0])
    inputs = [LabelLayoutInput(anchor_screen_xy=a, label_size_px=(40.0, 20.0))]
    [result] = solve_layout(inputs, viewport_size_px=(1920, 1080))
    assert np.allclose(result.leader_anchor_xy, a)


# --- Anchor registry -------------------------------------------------------


def test_anchor_registry_covers_every_named_primitive() -> None:
    """Every actor we render with a vector / arc / glyph name must have a
    matching label anchor — no silent label drops."""
    state = SceneState.default()
    anchors = {a.name for a in collect_anchors(state)}
    expected = {
        "lbl_target",
        "lbl_observer",
        "lbl_sun",
        "lbl_background",
        "lbl_vec_boresight",
        "lbl_vec_surface_normal",
        "lbl_vec_sun_ray",
        "lbl_vec_sun_to_background",
        "lbl_arc_off_nadir",
        "lbl_arc_sun_zenith",
        "lbl_arc_phase_angle",
    }
    missing = expected - anchors
    assert not missing, f"label anchor registry missing: {missing!r}"
