"""R4 of round-2 visual remediation — restore visible ground plane.

Acceptance:
  * The cap, fade, and contact-shadow actors are all added to the
    plotter (Phase-7 diet had collapsed ground rendering to the
    contact-shadow disc only).
  * The ground is visibly rendered in the bottom 20%% of a
    default-state screenshot — i.e., the gridded cap is producing
    non-background pixels there, not just the dark viewport.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pyvista")

import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402


def test_ground_actors_present_in_default_scene() -> None:
    """The cap, fade, and contact-shadow actors must all be added.

    Phase-7 diet had collapsed ground rendering to contact_shadow only,
    leaving the target floating in dark space. R4 re-wires all three.
    """
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        build_scene(SceneState.default(), plotter=p)
        names = set(p.actors.keys())
    finally:
        p.close()

    for required in ("ground_cap", "ground_fade", "contact_shadow"):
        assert required in names, f"{required} missing from default scene"


def test_ground_plane_is_visible_in_render() -> None:
    """The bottom 20%% of a default-state screenshot must contain
    visibly non-background pixels from the gridded cap.

    Without this test, an off-by-one in the procedural-texture generator
    (alpha=0 everywhere) or a z-fight that hides the cap behind the
    fade plane will silently regress to the round-1 "target floating
    in dark space" failure.
    """
    p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    try:
        build_scene(SceneState.default(), plotter=p)
        p.show(auto_close=False)
        img = np.asarray(p.screenshot(return_img=True))
    finally:
        p.close()

    # Bottom 20% of the canvas — the camera's elevation 25° puts the
    # ground here.
    bottom_strip = img[864:, :, :]
    # Background is VIEWPORT_BACKGROUND_COLOR = #1F242B = (31, 36, 43).
    # Sum ≈ 110. Anything noticeably brighter is a non-background pixel
    # (the gridded cap base is RGB 200 lightening the dark bg through
    # alpha blending).
    pixel_sum = bottom_strip.sum(axis=-1)
    non_bg_pixels = int((pixel_sum > 130).sum())
    total_pixels = int(bottom_strip.shape[0] * bottom_strip.shape[1])
    fraction = non_bg_pixels / total_pixels
    # The grid lines are thin (1-px wide in the texture, blending through
    # alpha = 0.45 against bg sum ≈ 110 to produce lit pixels at sum ≈
    # 320), so only the actual line pixels exceed the threshold. ≥1.5%
    # coverage is what catches a fully-blank ground (round 1's regression)
    # without false-failing on the legitimate sparse-grid composition.
    assert fraction > 0.015, (
        f"ground plane invisible in bottom 20% of canvas — "
        f"only {fraction:.3%} non-bg pixels (need >1.5%)"
    )
