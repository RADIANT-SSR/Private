"""Phase 1 acceptance — every primitive renders, every shape is identifiable.

PLAN_v2.md §9 acceptance:
  * ``build_scene(default_state())`` populates every documented primitive.
  * All six target shapes render and are visually distinguishable
    (verified here by point-count: each shape produces a different
    number of mesh points; shape-distinction at the visual level lands
    in the golden-screenshot test below).
  * Iteration order matches the documented build order (ground →
    target → frames → vectors → arcs → glyphs → labels).
  * No Qt binding is loaded along the way — re-asserts C7 with the
    full Phase-1 builder, not just the Phase-0 stub.

This test runs only when PyVista is installed (the C7 invariant is
"PyVista without Qt"). Before ``install_deps.py`` runs, it skips cleanly.
"""

from __future__ import annotations

import dataclasses
import sys
import unittest.mock
from typing import Iterator

import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402

_QT_BINDINGS = ("PySide6", "PySide2", "PyQt5", "PyQt6")


@pytest.fixture()
def offscreen_plotter() -> Iterator[pv.Plotter]:
    """Provide an off-screen plotter and clean it up after the test."""
    p = pv.Plotter(off_screen=True)
    try:
        yield p
    finally:
        p.close()


# -- Primitive enumeration --------------------------------------------------

# Names every Phase 1 primitive's ``add_to_plotter`` registers. Pinning these
# explicitly catches a Phase-2 / 3 / 4 rename that silently breaks the actor-
# update API the Qt shell depends on.
_EXPECTED_NAMED_ACTORS = (
    # Phase-7 diet: drop ``ground_fade`` + ``ground_cap`` (the gridded
    # ground is gone — only the contact-shadow ellipse remains as the
    # ground reference). Drop the 8 sun-ray tubes (sun is one solid
    # sphere). Drop the boresight/sun_ray break-mark zigzags. With
    # ``state.background_kind == "none"`` (the default), the background
    # marker, the s_B vector, and the n_B surface-normal vector are
    # also suppressed; the matching label anchors are gated alongside.
    "contact_shadow",
    # target (default state = sphere)
    "target",
    # frames
    "body_axis_x",
    "body_axis_y",
    "body_axis_z",
    # vectors (background-coupled vectors are gated by background_kind)
    "vec_boresight",
    "vec_boresight_tip",
    "vec_sun_ray",
    "vec_sun_ray_tip",
    # arcs (each: tube + tip cone)
    "arc_off_nadir",
    "arc_off_nadir_tip",
    "arc_phase_angle",
    "arc_phase_angle_tip",
    "arc_sun_zenith",
    "arc_sun_zenith_tip",
    # glyphs (sun is now a single sphere; background gated off by default)
    "glyph_observer",
    "glyph_sun",
    # labels (anchor list excludes background-coupled labels by default)
    "lbl_target_text",
    "lbl_target_leader",
    "lbl_observer_text",
    "lbl_observer_leader",
    "lbl_sun_text",
    "lbl_sun_leader",
    "lbl_vec_boresight_text",
    "lbl_vec_boresight_leader",
    "lbl_vec_sun_ray_text",
    "lbl_vec_sun_ray_leader",
    "lbl_arc_off_nadir_text",
    "lbl_arc_off_nadir_leader",
    "lbl_arc_sun_zenith_text",
    "lbl_arc_sun_zenith_leader",
    "lbl_arc_phase_angle_text",
    "lbl_arc_phase_angle_leader",
)


def test_all_phase1_primitives_register(offscreen_plotter: pv.Plotter) -> None:
    build_scene(SceneState.default(), plotter=offscreen_plotter)
    actor_names = set(offscreen_plotter.actors)
    missing = [name for name in _EXPECTED_NAMED_ACTORS if name not in actor_names]
    assert not missing, (
        f"Phase 1 builder did not register expected actors: {missing!r}. "
        f"Registered: {sorted(actor_names)!r}"
    )


# -- Per-shape rendering ----------------------------------------------------


@pytest.mark.parametrize(
    "shape_kind",
    ["sphere", "cylinder", "cone", "box", "flat_plate"],
)
def test_target_shape_renders(
    offscreen_plotter: pv.Plotter, shape_kind: str
) -> None:
    """Each of the five concrete target shapes registers a 'target' actor
    with a non-empty mesh.

    The extended-cell shape is not in ``ShapeKind``; it is wired in at
    Phase 2 / 4 when the regime selector grows that view (see
    ``scene/target/extended_cell.py`` docstring).
    """
    state = dataclasses.replace(SceneState.default(), target_shape=shape_kind)  # type: ignore[arg-type]
    build_scene(state, plotter=offscreen_plotter)
    assert "target" in offscreen_plotter.actors, (
        f"shape={shape_kind} did not register a 'target' actor"
    )
    actor = offscreen_plotter.actors["target"]
    mapper = actor.GetMapper()
    assert mapper is not None
    polydata = mapper.GetInput()
    assert polydata is not None
    assert polydata.GetNumberOfPoints() > 0, (
        f"shape={shape_kind} target mesh has zero points"
    )


def test_target_shapes_are_visually_distinguishable() -> None:
    """Different shapes produce meshes with different point counts.

    Acceptance text in PLAN_v2.md §9 says the six target shapes must be
    visually distinguishable. A weaker but objective proxy: each shape's
    PyVista mesh has a different point count (sphere theta_res=48 + phi_res=48
    is not the same as a 6-face cube, etc.). The pixel-level "is it
    visually distinguishable" check is the locked golden-screenshot test
    that runs separately.
    """
    counts: dict[str, int] = {}
    for shape_kind in ("sphere", "cylinder", "cone", "box", "flat_plate"):
        state = dataclasses.replace(
            SceneState.default(), target_shape=shape_kind  # type: ignore[arg-type]
        )
        p = pv.Plotter(off_screen=True)
        try:
            build_scene(state, plotter=p)
            counts[shape_kind] = (
                p.actors["target"].GetMapper().GetInput().GetNumberOfPoints()
            )
        finally:
            p.close()
    assert len(set(counts.values())) == len(counts), (
        f"Two shapes produced meshes with identical point counts — they are "
        f"not distinguishable at the geometry level: {counts!r}"
    )


# -- Builder return contract ------------------------------------------------


def test_build_scene_returns_provided_plotter(offscreen_plotter: pv.Plotter) -> None:
    returned = build_scene(SceneState.default(), plotter=offscreen_plotter)
    assert returned is offscreen_plotter


def test_build_scene_creates_plotter_when_none() -> None:
    p = build_scene(SceneState.default())
    try:
        assert isinstance(p, pv.Plotter)
    finally:
        p.close()


# -- C7 re-assertion with the Phase 1 build pipeline ------------------------


def _purge_scene_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("dev_tools.geometry_gui_v2.scene"):
            del sys.modules[name]


def test_phase1_build_runs_without_any_qt_binding() -> None:
    """Re-runs the C7 enforcement against the full Phase-1 build pipeline.

    The Phase-0 C7 test only exercised the empty cube. With the full per-
    primitive tree wired, each new module is a fresh chance to accidentally
    pull a Qt binding through. This test guards against that drift.
    """
    blocked = {name: None for name in _QT_BINDINGS}
    _purge_scene_modules()
    with unittest.mock.patch.dict(sys.modules, blocked):
        from dev_tools.geometry_gui_v2.app.state import SceneState as _State
        from dev_tools.geometry_gui_v2.scene.builder import (
            build_scene as _build,
        )

        p = pv.Plotter(off_screen=True)
        try:
            _build(_State.default(), plotter=p)
        finally:
            p.close()

        for binding in _QT_BINDINGS:
            assert sys.modules.get(binding) is None, (
                f"Phase 1 builder transitively imported {binding} — C7 violation"
            )
