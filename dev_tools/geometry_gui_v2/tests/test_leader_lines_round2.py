"""Round-2 R6 acceptance — leader lines, anchor dots, max-distance clamp.

PLAN_v2_remediation_round2.md §7:
  * Every label has a visible leader line connecting it to its anchor.
  * Leader lines end in a small dot at the anchor point (3 px diameter).
  * No label is more than 240 px from its anchor in screen space.
  * Leader lines use a single neutral color (LEADER_LINE_COLOR), not the
    per-label family color, so the connector reads as annotation chrome.

These tests pin the contract; pixel-level verification of "the dot is
visible at the right place" is covered by the canonical-view PNG audit.

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
from dev_tools.geometry_gui_v2.scene import style  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402
from dev_tools.geometry_gui_v2.scene.labels._anchors import (  # noqa: E402
    collect_anchors,
)
from dev_tools.geometry_gui_v2.scene.labels.layout import (  # noqa: E402
    LabelLayoutInput,
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


def test_every_label_has_a_leader_line_and_an_anchor_dot(
    offscreen_plotter: pv.Plotter,
) -> None:
    """Each label registers three actors: text, leader, dot. Round-2 R6
    introduced the dot — the leader and text actors were already there."""
    state = SceneState.default()
    build_scene(state, plotter=offscreen_plotter)

    for anchor in collect_anchors(state):
        for suffix in ("_text", "_leader", "_dot"):
            assert f"{anchor.name}{suffix}" in offscreen_plotter.actors, (
                f"label {anchor.name!r} missing {suffix} actor — "
                "R6 requires text + leader + anchor dot per label"
            )


def _canonical_states() -> list[tuple[str, SceneState]]:
    base = SceneState.default()
    return [
        ("default", base),
        ("box", dataclasses.replace(base, target_shape="box")),
        ("cone", dataclasses.replace(base, target_shape="cone")),
        ("flat_plate", dataclasses.replace(base, target_shape="flat_plate")),
        ("sphere", dataclasses.replace(base, target_shape="sphere")),
        (
            "high_obliquity",
            dataclasses.replace(base, observer_look_angle_rad=math.radians(40.0)),
        ),
        (
            "low_sun",
            dataclasses.replace(base, solar_zenith_rad=math.radians(75.0)),
        ),
        (
            "background_on",
            dataclasses.replace(base, background_kind="ground"),
        ),
    ]


@pytest.mark.parametrize("case_name,state", _canonical_states())
def test_no_label_drifts_past_the_240px_anchor_cap(
    offscreen_plotter: pv.Plotter,
    case_name: str,
    state: SceneState,
) -> None:
    """The post-deconfliction clamp must keep every label within
    LABEL_MAX_ANCHOR_DISTANCE_PX of its anchor (with a 1 px slack for
    floating-point round-trip through the clamp arithmetic)."""
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
    cap = float(style.LABEL_MAX_ANCHOR_DISTANCE_PX) + 1.0
    for label, result in zip(labels, results):
        d = float(np.linalg.norm(result.label_screen_xy - result.leader_anchor_xy))
        assert d <= cap, (
            f"case={case_name}: label {label.name!r} sits {d:.1f} px from "
            f"its anchor — round-2 R6 caps this at "
            f"{style.LABEL_MAX_ANCHOR_DISTANCE_PX} px"
        )


def test_leader_actor_uses_the_neutral_leader_color(
    offscreen_plotter: pv.Plotter,
) -> None:
    """Round-2 R6: the per-label *family* color drives the text and pill
    background; the *leader* line uses the single neutral
    LEADER_LINE_COLOR. Mixing leader hue with vector hue produced a
    visually noisy 'colored connector' read; the neutral connector
    reads as chrome and lets the family-coded vectors carry the color
    information unmolested."""
    state = SceneState.default()
    build_scene(state, plotter=offscreen_plotter)
    expected = _hex_to_rgb_float(style.LEADER_LINE_COLOR)
    sample_name = "lbl_target_leader"
    actor = offscreen_plotter.actors.get(sample_name)
    assert actor is not None, f"missing {sample_name!r} actor"
    rgb = actor.GetProperty().GetColor()
    for got, want in zip(rgb, expected):
        assert abs(got - want) < 1e-3, (
            f"leader color {rgb!r} != expected {expected!r} "
            "— per-label colors leaked back into the leader actor"
        )


def _hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)
