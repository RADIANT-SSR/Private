"""Phase 3 acceptance — vector arrowheads, arc arrowheads, break-marks,
diamond observer glyph, sun disc + 8 rays.

PLAN_v2.md §11 acceptance:
  * Each angle arc visibly connects the two vectors it measures (and now
    has a cone arrowhead at the v2 endpoint).
  * Break-marks present on the satellite-target and sun-target connecting
    lines.
  * Sun rays at 45° increments around the disc.

This test verifies the Phase 3 *contract* (the right primitives exist
with the right geometric placement) — pixel-level visual fidelity is
covered by the locked golden screenshots in
``test_scene_goldens_phase1.py`` (re-locked at end of Phase 3).

Skips cleanly when PyVista is not installed.
"""

from __future__ import annotations

import math
from typing import Iterator

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402


@pytest.fixture()
def offscreen_plotter() -> Iterator[pv.Plotter]:
    p = pv.Plotter(off_screen=True)
    try:
        yield p
    finally:
        p.close()


def _bounds_center(actor: pv.Actor) -> np.ndarray:
    b = actor.GetBounds()  # (xmin,xmax,ymin,ymax,zmin,zmax)
    return np.array(
        [(b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, (b[4] + b[5]) * 0.5],
        dtype=np.float64,
    )


# -- Vector arrowheads ------------------------------------------------------


@pytest.mark.parametrize(
    "shaft_name,tip_name",
    [
        ("vec_boresight", "vec_boresight_tip"),
        ("vec_surface_normal", "vec_surface_normal_tip"),
        ("vec_sun_ray", "vec_sun_ray_tip"),
        ("vec_sun_to_background", "vec_sun_to_background_tip"),
    ],
)
def test_every_vector_has_a_tip_arrowhead(
    offscreen_plotter: pv.Plotter, shaft_name: str, tip_name: str
) -> None:
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    assert shaft_name in offscreen_plotter.actors, (
        f"shaft {shaft_name!r} missing — check the per-vector module"
    )
    assert tip_name in offscreen_plotter.actors, (
        f"tip {tip_name!r} missing — Phase 3 requires every vector to "
        "render with a cone arrowhead at the tip"
    )


# -- Break-marks on the not-to-scale connectors ----------------------------


@pytest.mark.parametrize(
    "vector_name",
    ["vec_boresight", "vec_sun_ray"],
)
def test_target_rooted_connectors_have_break_mark(
    offscreen_plotter: pv.Plotter, vector_name: str
) -> None:
    """PLAN_v2.md §11 step 4: the target → satellite and target → sun
    connecting lines render a small zigzag at the midpoint as a not-to-scale
    indicator. Other vectors (surface normal, sun → background) do not."""
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    break_name = f"{vector_name}_break"
    assert break_name in offscreen_plotter.actors, (
        f"{vector_name} is a not-to-scale connector — Phase 3 step 4 "
        f"requires a {break_name!r} actor at the midpoint"
    )


@pytest.mark.parametrize(
    "vector_name",
    ["vec_surface_normal", "vec_sun_to_background"],
)
def test_non_connector_vectors_have_no_break_mark(
    offscreen_plotter: pv.Plotter, vector_name: str
) -> None:
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    assert f"{vector_name}_break" not in offscreen_plotter.actors, (
        f"{vector_name} is not a target-rooted connector — it should not "
        "carry a break-mark"
    )


# -- Arc arrowheads --------------------------------------------------------


@pytest.mark.parametrize(
    "arc_name", ["arc_off_nadir", "arc_phase_angle", "arc_sun_zenith"]
)
def test_every_arc_has_a_tip_arrowhead(
    offscreen_plotter: pv.Plotter, arc_name: str
) -> None:
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    assert arc_name in offscreen_plotter.actors
    assert f"{arc_name}_tip" in offscreen_plotter.actors, (
        f"{arc_name} missing tip — Phase 3 step 2 requires a cone arrowhead "
        "at the v2 end of every arc"
    )


# -- Diamond observer glyph -------------------------------------------------


def test_observer_glyph_is_a_4_sided_polygon(
    offscreen_plotter: pv.Plotter,
) -> None:
    """PLAN_v2.md §11 step 6: the observer glyph is a 4-sided polygon
    (diamond). Pinning the point count anchors the polygon vs the Phase 1
    cube (8 vertices) and the Phase 1 sphere (>= 100 vertices)."""
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    actor = offscreen_plotter.actors["glyph_observer"]
    polydata = actor.GetMapper().GetInput()
    assert polydata is not None
    n_pts = polydata.GetNumberOfPoints()
    # pv.Polygon(n_sides=4) emits the 4 corner vertices.
    assert n_pts == 4, (
        f"observer glyph has {n_pts} points — expected 4 (diamond)"
    )


# -- Sun disc + 8 rays ------------------------------------------------------


def test_sun_glyph_has_eight_rays(offscreen_plotter: pv.Plotter) -> None:
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    rays = [n for n in offscreen_plotter.actors if n.startswith("glyph_sun_ray_")]
    assert sorted(rays) == [f"glyph_sun_ray_{k}" for k in range(8)], (
        f"sun glyph should have exactly 8 rays at 45° increments; got {rays!r}"
    )


def test_sun_rays_are_at_45_degree_increments(
    offscreen_plotter: pv.Plotter,
) -> None:
    """The 8 ray midpoints around the sun disc must form a regular octagon
    in the disc plane — neighbors are exactly 45° apart in that plane.

    Check by computing the ring centroid (= sun position), then the angular
    spacing of consecutive rays around that centroid in their shared plane.
    """
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    centers = np.array(
        [
            _bounds_center(offscreen_plotter.actors[f"glyph_sun_ray_{k}"])
            for k in range(8)
        ]
    )
    ring_center = centers.mean(axis=0)
    radials = centers - ring_center

    # Project into the plane spanned by the first two radials.
    e1 = radials[0] / np.linalg.norm(radials[0])
    # Use the 2nd ray to fix the orthogonal in-plane axis.
    e2_raw = radials[2] - np.dot(radials[2], e1) * e1
    e2 = e2_raw / np.linalg.norm(e2_raw)

    angles = np.array(
        [math.atan2(np.dot(r, e2), np.dot(r, e1)) for r in radials]
    )
    # Sort and take consecutive deltas, normalized to [0, 2π).
    angles_sorted = np.sort(np.mod(angles, 2.0 * math.pi))
    deltas = np.diff(np.concatenate([angles_sorted, [angles_sorted[0] + 2 * math.pi]]))
    expected = math.pi / 4.0  # 45°
    assert np.allclose(deltas, expected, atol=1e-2), (
        f"sun ray angular spacing not 45°: {np.degrees(deltas)!r}"
    )


# -- Tip cone is positioned at the shaft endpoint ---------------------------


def test_vector_tip_sits_at_shaft_endpoint(
    offscreen_plotter: pv.Plotter,
) -> None:
    """Sanity: the boresight tip cone's bounds are near the boresight
    shaft's far endpoint. Catches a regression where the tip is placed at
    the wrong position (e.g. start vs end swap)."""
    state = SceneState.default()
    build_scene(state, plotter=offscreen_plotter)

    from dev_tools.geometry_gui_v2.scene._directions import (
        observer_direction_scene,
    )
    from dev_tools.geometry_gui_v2.scene._layout import (
        SCENE_OBSERVER_DISTANCE_M,
    )

    expected_tip = (
        observer_direction_scene(state) * SCENE_OBSERVER_DISTANCE_M
    )
    tip_center = _bounds_center(offscreen_plotter.actors["vec_boresight_tip"])
    distance = np.linalg.norm(tip_center - expected_tip)
    # Cone has finite height (~ length * 0.12); allow for half a cone length.
    assert distance < 0.6, (
        f"boresight tip cone offset from expected endpoint by {distance:.3f} m "
        f"— expected {expected_tip!r}, got {tip_center!r}"
    )
