"""R3 of round-2 visual remediation — stylized sun glyph (disc + 8 rays).

Acceptance:
  * The sun renders as a disc + 8 rays, not as a sphere.
  * 9 distinct actors are added to the plotter (1 disc + 8 rays).
  * All 9 actors use ``lighting=False`` so the glyph reads as an icon
    rather than a shaded body.
  * The sun glyph is visibly smaller than the target on screen at the
    default camera pose.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pyvista")

import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402


def test_sun_glyph_has_nine_actors() -> None:
    """The disc + 8 rays produce exactly 9 named actors. A regression to
    the Phase-7 single-sphere implementation would have 1, not 9."""
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        build_scene(SceneState.default(), plotter=p)
        names = set(p.actors.keys())
    finally:
        p.close()

    assert "glyph_sun" in names, "disc actor missing"
    for i in range(8):
        assert f"glyph_sun_ray_{i}" in names, f"ray {i} missing"


def test_sun_glyph_actors_have_lighting_disabled() -> None:
    """All sun-glyph actors render with lighting off — round-2 plan §4
    requires the glyph to read as an icon, not a shaded body. PyVista
    surfaces this on the actor's ``GetProperty().GetLighting()`` flag."""
    p = pv.Plotter(off_screen=True, window_size=(640, 480))
    try:
        build_scene(SceneState.default(), plotter=p)
        sun_actor_names = ["glyph_sun"] + [f"glyph_sun_ray_{i}" for i in range(8)]
        for name in sun_actor_names:
            actor = p.actors[name]
            prop = actor.GetProperty()
            assert prop.GetLighting() == 0, (
                f"{name}: lighting enabled (expected lighting=False)"
            )
    finally:
        p.close()


def test_sun_glyph_smaller_than_target_on_screen() -> None:
    """At the default camera pose, the sun glyph occupies fewer pixels
    than the target. Catches a regression to a sphere of literal solar
    scale (which would be larger than the target on screen)."""
    p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    try:
        build_scene(SceneState.default(), plotter=p)
        p.show(auto_close=False)
        img = np.asarray(p.screenshot(return_img=True))
    finally:
        p.close()

    # Solar amber is ~ #C28A1F (RGB ≈ 194, 138, 31). Target is teal —
    # green dominates over red. Use channel ratios to segment.
    R, G, B = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    # Sun amber: red dominates, blue depressed.
    sun_mask = (R > 120) & (R > G + 20) & (R > B + 60)
    # Target teal: green dominates, red depressed.
    target_mask = (G > 80) & (G > R + 20) & (G > B - 10)
    sun_pixels = int(sun_mask.sum())
    target_pixels = int(target_mask.sum())
    assert sun_pixels > 0, "sun glyph not detected (color segmentation failed)"
    assert target_pixels > 0, "target not detected"
    assert sun_pixels < target_pixels, (
        f"sun glyph occupies {sun_pixels} px ≥ target {target_pixels} px — "
        f"regression to literal-scale sun"
    )
