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
from radiant.gui.viewer.projection import dir_from_az_zen, make_camera  # noqa: E402
from radiant.gui.viewer.scene import palette  # noqa: E402
from radiant.gui.viewer.schematic_view import (  # noqa: E402
    _SENSOR_DIST,
    _SUN_DIST,
    SchematicView,
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
