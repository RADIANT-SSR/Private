"""Tests for the 2D geometry schematic viewer (Pass 1 — renderer core, ADR-0007).

The PyVista/VTK raster viewer was replaced by a pure-Qt 2D orthographic schematic
(owner-ratified 2026-07-14). Everything here renders **offscreen** via ``QWidget.grab()``
— fully faithful, no VTK, no segfault-prone live interactor.

Coverage:

* :class:`TestProjectionParity` — the ported ``geometry.js`` projection/direction math
  reproduces known reference outputs (``dirFromAzZen`` + a projected point).
* :class:`TestSceneBuild` — the abstract scene binds the stage-derived directions and
  honours the not-to-scale rule (display distance independent of raw altitude).
* :class:`TestSchematicCanvas` — the canvas renders bound to a real evaluation, draws the
  vectors + legend, and yaw/pitch rotation changes the projection.
* :class:`TestGeometryViewerWidget` — the embedded widget's preserved public surface
  (mode/availability, show_result render, Pass-2 stubs, theme swap, guard panel).
* :class:`TestGeometryPaneIntegration` — the Geometry center tabs "Inputs | Schematic"
  and the viewer renders after a full-chain evaluate.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtGui import QColor, QImage  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.themes.tokens import DARK, LIGHT  # noqa: E402
from radiant.gui.viewer import angle_catalog, angle_truth  # noqa: E402
from radiant.gui.viewer.projection import (  # noqa: E402
    compute_angles,
    dir_from_az_zen,
    make_camera,
)
from radiant.gui.viewer.scene import palette  # noqa: E402
from radiant.gui.viewer.schematic_view import (  # noqa: E402
    _SENSOR_DIST,
    _SUN_DIST,
    SchematicView,
    _format_km,
    build_scene,
)
from radiant.gui.viewer.viewer_state import ViewerState  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


@pytest.fixture(scope="module")
def evaluated() -> tuple[Sensor, object]:
    sensor = Sensor.from_yaml(_EXAMPLE)
    return sensor, _evaluate(sensor)


@pytest.fixture
def offnadir_sphere() -> tuple[Sensor, object]:
    """An off-nadir sensor with a discrete sphere target (fresh, mutable)."""
    sensor = Sensor.from_yaml(_EXAMPLE)
    sensor.set("geometry.path_zenith_rad", 0.4)
    sensor.set("source.target.shape", "sphere")
    sensor.set("source.target.shape_radius_m", 1.0)
    return sensor, _evaluate(sensor)


def _has_color(img: QImage, hex_color: str, tol: int = 24, step: int = 2) -> bool:
    """True when a pixel close to *hex_color* appears in *img* (swatch/vector present)."""
    target = QColor(hex_color)
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if (
                abs(c.red() - target.red())
                + abs(c.green() - target.green())
                + abs(c.blue() - target.blue())
            ) <= tol:
                return True
    return False


class TestProjectionParity:
    """The ported geometry.js math reproduces known reference outputs (verbatim port)."""

    def test_dir_from_az_zen_reference_cases(self) -> None:
        # Zenith direction: az/zen = 0 → straight up (+Z).
        assert np.allclose(dir_from_az_zen(0.0, 0.0), [0.0, 0.0, 1.0], atol=1e-12)
        # Due East on the horizon: az=90, zen=90 → +X.
        assert np.allclose(dir_from_az_zen(90.0, 90.0), [1.0, 0.0, 0.0], atol=1e-9)
        # A general case: az=45, zen=30 (sin30=0.5, sin45=cos45).
        s = 0.5 * math.sqrt(0.5)
        cz = math.cos(math.radians(30))
        assert np.allclose(dir_from_az_zen(45.0, 30.0), [s, s, cz], atol=1e-9)

    def test_camera_project_reference_point(self) -> None:
        """make_camera(35,22,100,400,300).project((2,0,0)) matches the geometry.js formula."""
        cam = make_camera(35.0, 22.0, 100.0, 400.0, 300.0)
        p = cam.project(np.array([2.0, 0.0, 0.0]))
        # Independently hand-computed from the geometry.js project() closure.
        assert p.x == pytest.approx(563.8304, abs=1e-3)
        assert p.y == pytest.approx(342.9731, abs=1e-3)
        assert p.depth == pytest.approx(-1.063622, abs=1e-5)

    def test_top_down_drops_z(self) -> None:
        """At pitch=90 (top-down) a +Z point projects to the canvas anchor (Z dropped)."""
        cam = make_camera(0.0, 90.0, 100.0, 200.0, 200.0)
        p = cam.project(np.array([0.0, 0.0, 5.0]))
        assert p.x == pytest.approx(200.0, abs=1e-6)
        assert p.y == pytest.approx(200.0, abs=1e-6)


class TestSceneBuild:
    """The abstract scene binds stage directions and honours the not-to-scale rule."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_glyphs_sit_at_fixed_abstract_distance(self) -> None:
        scene = build_scene(self._state(target_shape="sphere"))
        assert np.linalg.norm(scene.sun_pos) == pytest.approx(_SUN_DIST, abs=1e-9)
        assert np.linalg.norm(scene.sensor_pos) == pytest.approx(_SENSOR_DIST, abs=1e-9)

    def test_display_distance_independent_of_raw_altitude(self) -> None:
        """Not-to-scale: a 75x change in raw altitude does not move the glyphs."""
        low = build_scene(self._state(observer_altitude_m=8_000.0))
        high = build_scene(self._state(observer_altitude_m=600_000.0))
        assert np.allclose(low.sensor_pos, high.sensor_pos)
        assert np.allclose(low.sun_pos, high.sun_pos)

    def test_sphere_and_box_have_wireframe_edges(self) -> None:
        assert build_scene(self._state(target_shape="sphere")).target_edges
        assert build_scene(self._state(target_shape="box")).target_edges

    def test_none_shape_is_point_reticle(self) -> None:
        scene = build_scene(self._state(target_shape="none"))
        assert scene.is_point
        assert scene.target_edges == ()

    def test_relative_azimuth_places_sun_off_sensor(self) -> None:
        """The sun sits at the relative azimuth from the sensor (relative geometry kept)."""
        scene = build_scene(self._state(relative_azimuth_rad=math.radians(30.0)))
        # Sensor is at azimuth 0; a nonzero relative azimuth gives the sun a +X component.
        assert scene.sun_pos[0] != pytest.approx(0.0, abs=1e-6)


class TestSchematicCanvas:
    """The QPainter canvas renders and rotates."""

    def test_renders_bound_to_evaluation(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        img = canvas.grab().toImage()
        assert img.width() == 900 and img.height() == 600
        # Both physics vector colours are painted (sun amber + sensor blue → vectors/legend).
        assert _has_color(img, palette.SOLAR_FAMILY)
        assert _has_color(img, palette.SATELLITE_FAMILY)

    def test_legend_panel_is_drawn(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The VECTORS legend pill (theme.panel fill) appears top-left."""
        sensor, result = offnadir_sphere
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        img = canvas.grab().toImage()
        # The legend pill is filled with theme.panel over the theme.bg background.
        assert _has_color(img, LIGHT.panel, tol=6, step=1)

    def test_yaw_rotation_changes_projection(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(600, 400)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.set_orientation(0.0, 22.0)
        img_a = canvas.grab().toImage()
        canvas.set_orientation(90.0, 22.0)
        img_b = canvas.grab().toImage()
        assert canvas.yaw_deg == 90.0
        assert img_a != img_b  # a different yaw produces a different render

    def test_pitch_is_clamped(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_orientation(10.0, 200.0)
        assert canvas.pitch_deg == pytest.approx(89.0)
        canvas.set_orientation(10.0, -50.0)
        assert canvas.pitch_deg == pytest.approx(2.0)


class TestFitToViewport:
    """Owner report 2026-07-14: the scene must be CENTRED + framed, never bottom-anchored.

    The orthographic camera fits the projected scene bounding box into the *live* paint rect
    with a symmetric margin and centres it — so the schematic stays centred at any size and
    the too-tall-canvas bottom-anchoring is gone. Also asserts the canvas *fills* its viewport
    (Expanding policy + a sensible minimum) rather than reporting an unbounded size.
    """

    def _canvas(self, qtbot, offnadir_sphere, w: int, h: int) -> SchematicView:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.resize(w, h)
        return canvas

    def test_scene_bbox_is_centred_in_rect(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 620)
        bounds = canvas.projected_content_bounds()
        assert bounds is not None
        min_x, min_y, max_x, max_y = bounds
        cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        # The scene bbox centre lands on the rect centre (both axes), not near the bottom.
        assert cx == pytest.approx(760 / 2, abs=2.0)
        assert cy == pytest.approx(620 / 2, abs=2.0)

    def test_scene_fits_with_margin_not_flush(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 620)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        # Every side clears the rect edge by a real margin — the scene is framed, not clipped.
        assert min_x > 8.0 and min_y > 8.0
        assert max_x < 760 - 8.0 and max_y < 620 - 8.0

    def test_centring_holds_when_tall(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """A tall panel keeps the scene centred (the exact regression the owner saw)."""
        canvas = self._canvas(qtbot, offnadir_sphere, 760, 1000)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        assert (min_x + max_x) / 2.0 == pytest.approx(760 / 2, abs=2.0)
        assert (min_y + max_y) / 2.0 == pytest.approx(1000 / 2, abs=2.0)
        # Not bottom-anchored: the top margin is a real fraction of the panel, not ~0.
        assert min_y > 40.0

    def test_centring_holds_when_wide(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        canvas = self._canvas(qtbot, offnadir_sphere, 1200, 600)
        min_x, min_y, max_x, max_y = canvas.projected_content_bounds()  # type: ignore[misc]
        assert (min_x + max_x) / 2.0 == pytest.approx(1200 / 2, abs=2.0)
        assert (min_y + max_y) / 2.0 == pytest.approx(600 / 2, abs=2.0)

    def test_canvas_fills_not_grows_unbounded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The canvas policy fills its viewport with a sane minimum — no unbounded growth."""
        from PySide6.QtWidgets import QSizePolicy

        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert canvas.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert canvas.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
        # A concrete, bounded sizeHint + minimum — never the degenerate (-1, -1) a scroll
        # area would inflate.
        hint = canvas.sizeHint()
        assert hint.isValid() and 300 <= hint.height() <= 1200
        assert canvas.minimumSize().width() >= 360 and canvas.minimumSize().height() >= 360

    def test_bounds_none_before_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        assert canvas.projected_content_bounds() is None


class TestGeometryViewerWidget:
    """The embedded widget's preserved public surface (2D pivot)."""

    def test_mode_is_schematic_and_available(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        assert viewer.mode == "schematic"
        assert viewer.is_available and not viewer.is_degraded
        assert viewer.canvas is not None

    def test_show_result_renders(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.resize(720, 520)
        viewer.show_result(result, sensor)
        assert viewer.canvas is not None and viewer.canvas.scene is not None

    def test_pass2_stubs_track_state_without_error(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """set_angle_revealed / set_triad_visible are no-op-safe stubs that track state."""
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("sun_zenith", True)
        assert viewer.revealed_angles == frozenset({"sun_zenith"})
        viewer.set_angle_revealed("sun_zenith", False)
        assert viewer.revealed_angles == frozenset()
        viewer.set_triad_visible(True)
        assert viewer.triad_visible is True

    def test_set_theme_repaints(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer(theme=LIGHT)
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_theme(DARK)
        assert viewer.canvas is not None and viewer.canvas.theme is DARK

    def test_guard_panel_on_build_failure(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        """A build failure surfaces the actionable guard panel (minimal, near-unreachable)."""
        from PySide6.QtWidgets import QLabel

        from radiant.gui.viewer import viewer_widget
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)

        def _boom(_result, _params):  # type: ignore[no-untyped-def]
            raise RuntimeError("bad state")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(viewer_widget.ViewerState, "from_chain_result", staticmethod(_boom))
        try:
            viewer.show_result(result, sensor)
        finally:
            monkey.undo()

        assert viewer.is_degraded and viewer.mode == "unavailable"
        assert "bad state" in (viewer.unavailable_reason or "")
        panels = [w for w in viewer.findChildren(QLabel) if w.objectName() == "viewerUnavailable"]
        assert panels and "unavailable" in panels[0].text().lower()

    def test_close_viewer_is_safe(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.close_viewer()  # no VTK window to release — must not raise


class TestGeometryPaneIntegration:
    """The Geometry center tabs "Inputs | Schematic" and renders on evaluate."""

    def test_pane_tabs_and_viewer(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        assert pane.has_tabs
        assert pane.tab_titles() == ["Inputs", "Schematic"]
        assert pane.geometry_viewer is not None

        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))
        viewer = pane.geometry_viewer
        assert viewer is not None and viewer.is_available
        assert viewer.canvas is not None and viewer.canvas.scene is not None

    def test_schematic_canvas_fills_bounded_window_not_balloons(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Mounted in a bounded window the Schematic canvas fills the viewport, never taller.

        Owner report 2026-07-14: the tall "Inputs" tab inflated the shared stack and ballooned
        the sibling "Schematic" canvas past the window height (scene then bottom-anchored). The
        canvas must stay within the window it is shown in.
        """
        from PySide6.QtWidgets import QMainWindow, QTabWidget

        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        win = QMainWindow()
        qtbot.addWidget(win)
        win.setCentralWidget(pane)
        win.resize(1000, 760)
        win.show()
        tabs = pane.findChild(QTabWidget)
        assert tabs is not None
        tabs.setCurrentIndex(1)  # Schematic

        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))
        for _ in range(4):
            qtbot.wait(1)

        canvas = pane.geometry_viewer.canvas  # type: ignore[union-attr]
        assert canvas is not None
        # The canvas must not balloon taller than the window it lives in.
        assert canvas.height() <= win.height()
        # And it still frames the scene centred within that bounded height.
        bounds = canvas.projected_content_bounds()
        assert bounds is not None
        cy = (bounds[1] + bounds[3]) / 2.0
        assert cy == pytest.approx(canvas.height() / 2, abs=3.0)


class TestShapeLibrary:
    """CU-131: the full shape library draws distinct wireframes reflecting dim aspect ratio."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_each_shape_has_wireframe_edges(self) -> None:
        for shape in ("sphere", "cylinder", "cone", "box", "flat_plate"):
            scene = build_scene(self._state(target_shape=shape))
            assert scene.target_edges, f"{shape} drew no edges"
            assert not scene.is_point

    def test_shapes_are_distinct(self) -> None:
        """cylinder / cone / box are no longer the same box stand-in (Pass-1 gap closed)."""
        counts = {
            shape: len(build_scene(self._state(target_shape=shape)).target_edges)
            for shape in ("box", "cylinder", "cone", "flat_plate")
        }
        # Box=12 edges; cylinder/cone/plate use their own generators with different counts.
        assert counts["box"] == 12
        assert counts["cylinder"] != counts["box"]
        assert counts["cone"] != counts["box"]
        assert counts["flat_plate"] != counts["box"]

    def test_none_shape_is_point_reticle(self) -> None:
        scene = build_scene(self._state(target_shape="none"))
        assert scene.is_point
        assert scene.target_edges == ()

    def test_dimensions_change_the_wireframe_aspect(self) -> None:
        """A long cylinder and a squat cylinder produce different wireframes (aspect ratio)."""
        long_cyl = build_scene(
            self._state(target_shape="cylinder", target_radius_m=1.0, target_length_m=8.0)
        )
        squat_cyl = build_scene(
            self._state(target_shape="cylinder", target_radius_m=2.0, target_length_m=1.0)
        )
        # Compare the top-ring height (max z) — a long cylinder reaches higher than a squat one.
        long_top = max(float(b[2]) for e in long_cyl.target_edges for b in e)
        squat_top = max(float(b[2]) for e in squat_cyl.target_edges for b in e)
        assert long_top > squat_top

    def test_display_size_ignores_metric_magnitude(self) -> None:
        """Not-to-scale: scaling both dims by 1000 (same ratio) leaves the wireframe unchanged."""
        small = build_scene(
            self._state(
                target_shape="box", target_length_m=2.0, target_width_m=1.0, target_height_m=1.0
            )
        )
        huge = build_scene(
            self._state(
                target_shape="box",
                target_length_m=2000.0,
                target_width_m=1000.0,
                target_height_m=1000.0,
            )
        )
        for (a0, b0), (a1, b1) in zip(small.target_edges, huge.target_edges, strict=True):
            assert np.allclose(a0, a1) and np.allclose(b0, b1)


class TestAngleArcs:
    """CU-128: revealed arcs draw + carry a degree value pill sourced from the stage."""

    def test_revealing_an_arc_changes_the_render(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        before = canvas.grab().toImage()
        canvas.set_revealed_angles({"sun_zenith"})
        after = canvas.grab().toImage()
        assert canvas.revealed_angles == frozenset({"sun_zenith"})
        assert before != after

    def test_azimuth_arc_paints_its_family_colour(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView(theme=LIGHT)
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        canvas.set_revealed_angles({"relative_azimuth"})
        img = canvas.grab().toImage()
        assert _has_color(img, palette.AZIMUTH_FAMILY, tol=40)

    def test_arc_label_reads_stage_value_in_degrees(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The pinned value is the stage angle (via ViewerState) converted to degrees (§6.3)."""
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(vs)
        ann = angle_catalog.annotation("off_nadir")
        text = canvas._arc_label_text(ann)  # noqa: SLF001 — exercises the display path
        expected_deg = math.degrees(result.stage_outputs["geometry"]["eta_rad"])
        assert f"{expected_deg:.1f}" in text and "°" in text

    def test_phase_arc_is_symbol_only(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """No stage-output phase angle → symbol alone, never a fabricated number (§6.3)."""
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.set_state(vs)
        ann = angle_catalog.annotation("phase_angle")
        assert canvas._arc_label_text(ann) == ann.symbol  # noqa: SLF001


class TestLeaderLabels:
    """CU-129: altitude leader-label magnitudes come verbatim from the stage-bound state."""

    def test_altitude_km_bound_from_state(self) -> None:
        base = ViewerState.default()
        vs = ViewerState(**{**base.__dict__, "observer_altitude_m": 705_000.0})
        scene = build_scene(vs)
        assert scene.altitude_km == pytest.approx(705.0, abs=1e-9)

    def test_format_km_matches_owner_example(self) -> None:
        assert _format_km(705.0) == "705 km"
        assert _format_km(8.0) == "8.0 km"
        assert _format_km(0.5) == "500 m"


class TestRpyTriad:
    """CU-130: the on-target body-axes triad renders and follows the ZYX Euler orientation."""

    def _state(self, **overrides: object) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, **overrides})

    def test_triad_toggle_changes_render(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.resize(900, 600)
        canvas.set_state(ViewerState.from_chain_result(result, sensor))
        off = canvas.grab().toImage()
        canvas.set_triad_visible(True)
        on = canvas.grab().toImage()
        assert canvas.triad_visible is True
        assert off != on

    def test_yaw_rotates_roll_axis_onto_scene_y(self) -> None:
        """A yaw of π/2 rotates the body +X (roll) axis onto scene +Y (mockup Euler)."""
        scene = build_scene(self._state(target_shape="box", target_yaw_rad=math.pi / 2))
        roll_dir = dict(scene.body_axes)["roll"]
        assert roll_dir[1] == pytest.approx(1.0, abs=1e-9)
        assert roll_dir[0] == pytest.approx(0.0, abs=1e-9)

    def test_pitch_change_moves_the_body_wireframe(self) -> None:
        flat = build_scene(self._state(target_shape="box"))
        tilted = build_scene(self._state(target_shape="box", target_pitch_rad=0.5))
        assert not np.allclose(
            np.array([a for e in flat.target_edges for a in e]),
            np.array([a for e in tilted.target_edges for a in e]),
        )


class TestAngleTruthConsistency:
    """CU-133 (binding, §6.3): viewer-local angle recomputation == stage output."""

    def test_recomputation_matches_stage_within_tolerance(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        geo = result.stage_outputs["geometry"]
        vs = ViewerState.from_chain_result(result, sensor)
        tol = angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD
        worst = 0.0
        for name, key in angle_truth.ANGLE_TRUTH_KEYS.items():
            recomputed = angle_truth.recompute_angle_rad(vs, name)
            stage_value = float(geo[key])
            err = abs(recomputed - stage_value)
            worst = max(worst, err)
            assert err <= tol, f"{name}: viewer {recomputed} vs stage {stage_value} (Δ={err})"
        assert float(geo["eta_rad"]) > 0.1  # the fixture exercised a non-trivial off-nadir

    def test_tolerance_is_explicit_and_tight(self) -> None:
        assert angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD == 1e-9

    def test_compute_angles_round_trips_construction(self) -> None:
        """compute_angles on scene-built directions reproduces the input zenith/azimuth."""
        sun = dir_from_az_zen(30.0, 40.0)
        sen = dir_from_az_zen(0.0, 20.0)
        a = compute_angles(sun, sen)
        assert math.degrees(a.theta_s_rad) == pytest.approx(40.0, abs=1e-9)
        assert math.degrees(a.theta_v_rad) == pytest.approx(20.0, abs=1e-9)
        assert math.degrees(a.delta_phi_rad) == pytest.approx(30.0, abs=1e-9)


class TestAnnotationFrameSplit:
    """CU-128: the catalog frame split matches the Phase-5 GeometryReadout grouping."""

    def test_annotation_frames(self) -> None:
        frames = {a.name: a.frame for a in angle_catalog.annotations()}
        assert frames["off_nadir"] == angle_catalog.FRAME_GROUND
        assert frames["sun_zenith"] == angle_catalog.FRAME_TARGET
        assert frames["relative_azimuth"] == angle_catalog.FRAME_TARGET
        assert frames["phase_angle"] == angle_catalog.FRAME_TARGET

    def test_stage_keys_grouped_like_the_readout(self) -> None:
        from radiant.gui.widgets import geometry_readout as gr

        target_keys: set[str] = set()
        ground_keys: set[str] = set()
        for title, keys in gr._GROUPS:  # noqa: SLF001 — reading the readout's own grouping
            if title == gr._TARGET_FRAME:
                target_keys = set(keys)
            elif title == gr._GROUND_FRAME:
                ground_keys = set(keys)
        for ann in angle_catalog.annotations():
            if ann.stage_key is None:
                continue
            if ann.frame == angle_catalog.FRAME_TARGET:
                assert ann.stage_key in target_keys
            else:
                assert ann.stage_key in ground_keys


class TestViewerRevealWiring:
    """CU-128/130: GeometryViewer forwards reveal/triad toggles to the canvas."""

    def test_reveal_and_triad_reach_the_canvas(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("relative_azimuth", True)
        assert viewer.canvas is not None
        assert viewer.canvas.revealed_angles == frozenset({"relative_azimuth"})
        viewer.set_triad_visible(True)
        assert viewer.canvas.triad_visible is True
        viewer.set_angle_revealed("relative_azimuth", False)
        assert viewer.canvas.revealed_angles == frozenset()


class TestAngleOverlay:
    """The angle-arc reveal selector is an on-canvas bottom-left overlay (2026-07-14 relayout)."""

    def test_overlay_is_a_child_of_the_canvas(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The interactive ANGLES selector is parented to the SchematicView canvas."""
        from radiant.gui.viewer.angle_overlay import AngleToggleOverlay

        canvas = SchematicView()
        qtbot.addWidget(canvas)
        overlay = canvas.angle_overlay
        assert isinstance(overlay, AngleToggleOverlay)
        assert overlay.parent() is canvas
        # One checkbox per annotatable angle, sourced from the single catalog.
        for ann in angle_catalog.annotations():
            assert overlay.angle_checkbox(ann.name) is not None

    def test_toggling_overlay_checkbox_reveals_the_arc(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """A checkbox on the overlay calls set_angle_revealed → the canvas reveals that arc."""
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        assert viewer.canvas is not None
        overlay = viewer.canvas.angle_overlay
        overlay.angle_checkbox("relative_azimuth").setChecked(True)
        assert viewer.revealed_angles == frozenset({"relative_azimuth"})
        assert viewer.canvas.revealed_angles == frozenset({"relative_azimuth"})
        overlay.angle_checkbox("relative_azimuth").setChecked(False)
        assert viewer.canvas.revealed_angles == frozenset()

    def test_overlay_anchors_bottom_left_after_resize(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The overlay re-pins to the canvas bottom-left corner when the canvas resizes."""
        canvas = SchematicView()
        qtbot.addWidget(canvas)
        canvas.show()  # resizeEvent only fires once the widget is realised
        canvas.resize(900, 700)
        overlay = canvas.angle_overlay
        geo = overlay.geometry()
        # Left-anchored (small inset) and its bottom clears the canvas bottom by the inset.
        assert geo.left() < canvas.width() / 2
        assert geo.bottom() < canvas.height()
        assert canvas.height() - geo.bottom() < 40  # near the bottom edge, not floating high
        # A second, different size keeps it bottom-left (repositioned, not stale).
        canvas.resize(600, 500)
        geo2 = overlay.geometry()
        assert geo2.left() < canvas.width() / 2
        assert canvas.height() - geo2.bottom() < 40


class TestDimensionPanel:
    """CU-131 + owner request: the side panel exposes ALL per-shape dimension inputs."""

    def _panel(self, qtbot):  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel

        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        panel.set_shape_choices(("none", "sphere", "cylinder", "flat_plate", "box", "cone"))
        return panel

    def test_visible_dimensions_per_shape(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = self._panel(qtbot)
        cases = {
            "sphere": {"source.target.shape_radius_m"},
            "cylinder": {"source.target.shape_radius_m", "source.target.shape_length_m"},
            "flat_plate": {"source.target.shape_length_m", "source.target.shape_width_m"},
            "box": {
                "source.target.shape_length_m",
                "source.target.shape_width_m",
                "source.target.shape_height_m",
            },
            "cone": {"source.target.shape_base_radius_m", "source.target.shape_height_m"},
            "none": set(),
        }
        for shape, expected in cases.items():
            panel.set_shape(shape)
            assert set(panel.visible_dimensions()) == expected

    def test_dimension_edit_emits_request(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = self._panel(qtbot)
        panel.set_shape("sphere")
        captured: list[tuple[str, float]] = []
        panel.dimensionRequested.connect(lambda path, value: captured.append((path, value)))
        panel.dimension_spin("source.target.shape_radius_m").setValue(2.5)
        assert ("source.target.shape_radius_m", 2.5) in captured

    def test_dimension_suffix_is_metres(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = self._panel(qtbot)
        assert panel.dimension_spin("source.target.shape_radius_m").suffix() == " m"
