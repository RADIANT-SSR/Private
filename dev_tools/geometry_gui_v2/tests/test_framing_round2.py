"""R2 of round-2 visual remediation — extent-driven default framing.

Acceptance:
  * ``scene_bounds`` returns a bbox that contains the target half-extent,
    the observer glyph at its display position, and the sun glyph at
    its display position.
  * ``default_camera_distance_m`` is monotone in scene extent — a
    larger target produces a larger camera distance.
  * Rendered default scene fills ≥50% of both canvas dimensions in
    width and height (Round-2 plan §3 R2 acceptance criterion).
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene._directions import (  # noqa: E402
    observer_direction_scene,
    sun_direction_scene,
)
from dev_tools.geometry_gui_v2.scene._layout import (  # noqa: E402
    SCENE_OBSERVER_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402
from dev_tools.geometry_gui_v2.scene.framing import (  # noqa: E402
    DISTANCE_EXTENT_MULTIPLIER,
    default_camera_distance_m,
    scene_bounds,
    scene_extent_m,
)


def test_scene_bounds_contains_target_and_glyphs() -> None:
    state = SceneState.default()
    bbox_min, bbox_max = scene_bounds(state)
    # Target body — sphere of radius 1 m at origin must be inside bbox.
    assert (bbox_min <= -state.target_radius_m).all()
    assert (bbox_max >= +state.target_radius_m).all()
    # Observer and sun glyph display positions must be inside the bbox
    # (this is what drives extent — without these the framing is wrong).
    obs_pos = observer_direction_scene(state) * SCENE_OBSERVER_DISTANCE_M
    sun_pos = sun_direction_scene(state) * SCENE_SUN_DISTANCE_M
    for pos, name in ((obs_pos, "observer"), (sun_pos, "sun")):
        assert (bbox_min <= pos + 1e-9).all() and (bbox_max + 1e-9 >= pos).all(), (
            f"{name} glyph at {pos} not contained in bbox [{bbox_min}, {bbox_max}]"
        )


def test_scene_extent_is_monotone_in_target_size() -> None:
    """A larger target should never produce a smaller scene extent."""
    small = dataclasses.replace(SceneState.default(), target_radius_m=0.5)
    large = dataclasses.replace(
        SceneState.default(),
        target_radius_m=4.0,
        target_length_m=8.0,
        target_shape="cylinder",
    )
    assert scene_extent_m(large) >= scene_extent_m(small)


def test_default_camera_distance_uses_documented_multiplier() -> None:
    """``default_camera_distance_m`` is exactly the documented multiplier
    times the half-extent. Locks the relationship so a future re-tune of
    the multiplier doesn't silently drift."""
    state = SceneState.default()
    expected = DISTANCE_EXTENT_MULTIPLIER * scene_extent_m(state)
    assert default_camera_distance_m(state) == pytest.approx(expected, abs=1e-12)


def test_default_framing_uses_majority_of_canvas() -> None:
    """Round-2 plan §3 acceptance: the default scene fills ≥50% of both
    canvas dimensions. The threshold here matches the plan exactly so a
    regression in framing or camera distance is caught immediately."""
    state = SceneState.default()
    p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    try:
        build_scene(state, plotter=p)
        p.show(auto_close=False)
        img = np.asarray(p.screenshot(return_img=True))
    finally:
        p.close()

    # Background is dark teal; non-background pixels are anything with
    # a noticeably non-zero RGB sum. Threshold matches the plan's
    # example test (sum > 30) — generous enough to avoid false negatives
    # from anti-aliasing fringe pixels.
    non_bg_mask = img.sum(axis=-1) > 30
    rows = np.where(non_bg_mask.any(axis=1))[0]
    cols = np.where(non_bg_mask.any(axis=0))[0]
    assert rows.size > 0 and cols.size > 0, "render produced no non-background pixels"
    y_extent = rows.max() - rows.min()
    x_extent = cols.max() - cols.min()
    h, w = img.shape[:2]
    assert y_extent / h > 0.5, (
        f"scene fills {y_extent / h:.3f} of canvas height (< 0.50)"
    )
    assert x_extent / w > 0.5, (
        f"scene fills {x_extent / w:.3f} of canvas width (< 0.50)"
    )
