"""Tests for the 3D geometry viewer (GUI plan Phase 7 Part A, ADR-0007).

Category D coverage:

* :class:`TestViewerStateMapping` — the ``ViewerState`` adapter binds ``stage_outputs``
  and the source/optics/detector params by the ADR-0007 §2 rebind table.
* :class:`TestStaticSceneRender` — the lifted scene library renders **offscreen**
  (``pyvista.Plotter(off_screen=True)``) bound to a real evaluated geometry.
* :class:`TestNotToScale` — the not-to-scale invariant (ADR-0007 §4): glyphs sit at
  schematic display distances via the leader helpers, never at true metric range, and
  positions do not scale with raw altitude.
* :class:`TestGeometryViewerWidget` — the embedded widget renders headless (static-image
  backend) and shows the actionable panel when the render is forced to fail.
* :class:`TestSceneImportsNoPhysicsStage` — the lifted scene lib imports no physics stage
  (gui → api + core, import-linter contract).
* :class:`TestGeometryPaneIntegration` — the Geometry stage center tabs "Inputs | 3D View"
  and the viewer renders after a full-chain evaluate.

The whole module runs under the ``offscreen`` Qt platform (see ``conftest.py``); the
scene renders through ``pyvista``'s confirmed-working offscreen path, never an embedded
live ``QtInteractor`` (which segfaults on the offscreen platform).
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

pv = pytest.importorskip("pyvista", reason="3D viewer tests require the 'gui' extra (pyvista)")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.viewer.scene import build_static_scene  # noqa: E402
from radiant.gui.viewer.scene._directions import observer_direction_scene  # noqa: E402
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m  # noqa: E402
from radiant.gui.viewer.scene._layout import SCENE_OBSERVER_DISTANCE_M  # noqa: E402
from radiant.gui.viewer.viewer_state import ViewerState  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def evaluated() -> tuple[Sensor, object]:
    """The mwir_leo_minimal sensor and one evaluated result (shared, read-only)."""
    sensor = Sensor.from_yaml(_EXAMPLE)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = sensor.evaluate()
    return sensor, result


def _offscreen_plotter() -> pv.Plotter:
    return pv.Plotter(off_screen=True, window_size=[640, 480])


class TestViewerStateMapping:
    """The ADR-0007 §2 rebind: ViewerState fields ← stage_outputs + params."""

    def test_geometry_outputs_map_by_field(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        geo = result.stage_outputs["geometry"]
        vs = ViewerState.from_chain_result(result, sensor)

        assert vs.observer_altitude_m == geo["h_sensor_m"]
        assert vs.observer_look_angle_rad == geo["eta_rad"]
        assert vs.target_altitude_m == geo["h_target_m"]
        assert vs.solar_zenith_rad == geo["theta_s_rad"]
        assert vs.relative_azimuth_rad == geo["delta_phi_rad"]

    def test_regime_from_optics(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """The final regime comes from stage_outputs['optics'] (Rule 10)."""
        _sensor, result = evaluated
        regime = result.stage_outputs["optics"]["regime"]
        vs = ViewerState.from_chain_result(result, _sensor)
        assert vs.regime_override == regime.value  # enum → literal

    def test_shape_and_sampling_from_params(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.target_shape == "none"  # mwir example declares no discrete shape
        assert vs.focal_length_m == sensor.get("optics.focal_length_m")
        # get() returns canonical metres despite the ``_um`` input-unit name.
        assert vs.pixel_pitch_m == sensor.get("detector.pixel_pitch_x_um")

    def test_attitude_defaults_to_identity(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """Platform attitude has no stage owner (CU-122) → defaults to zero (Part B)."""
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        assert vs.observer_yaw_rad == 0.0
        assert vs.observer_pitch_rad == 0.0
        assert vs.observer_roll_rad == 0.0


class TestStaticSceneRender:
    """The lifted scene library renders offscreen bound to a real evaluation."""

    def test_renders_actors_and_image(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        plotter = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=plotter)
            actors = set(plotter.actors)
            # Ground, both glyphs, and the deconflicted leader labels are present.
            assert "ground_cap" in actors
            assert "glyph_observer" in actors
            assert "glyph_sun" in actors
            assert any(name.startswith("lbl_") for name in actors)
            # extended regime → the pixel-cell overlay stands in for the target body.
            assert "extended_pixel_cell" in actors
            img = plotter.screenshot(return_img=True)
            assert img.shape[0] > 0 and img.shape[1] > 0
        finally:
            plotter.close()

    def test_viewport_background_follows_theme(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """Theme integration: the viewport background is the light theme's bg token."""
        from radiant.gui.themes.tokens import LIGHT

        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        plotter = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=plotter, theme=LIGHT)
            bg = plotter.background_color
            assert bg.hex_rgb.lower() == LIGHT.bg.lower()
        finally:
            plotter.close()


class TestNotToScale:
    """ADR-0007 §4: altitude via leader labels, geometry never rescaled."""

    def _state(self, altitude_m: float) -> ViewerState:
        base = ViewerState.default()
        return ViewerState(**{**base.__dict__, "observer_altitude_m": altitude_m})

    def test_glyph_distance_is_schematic_not_metric(self) -> None:
        """The sensor glyph sits at a schematic display distance, not the true altitude."""
        vs = self._state(600_000.0)  # 600 km
        dist = schematic_display_distance_m(vs, SCENE_OBSERVER_DISTANCE_M)
        # A few tens of scene-metres — orders of magnitude below the 600 km altitude.
        assert dist < 1_000.0
        assert dist < vs.observer_altitude_m / 100.0

    def test_placement_ignores_raw_altitude(self) -> None:
        """Positions do not scale with raw sensor altitude (no fake proportionality)."""
        low = self._state(8_000.0)
        high = self._state(600_000.0)
        # Same look angle → identical glyph direction and schematic distance regardless
        # of the 75× difference in true altitude.
        assert (observer_direction_scene(low) == observer_direction_scene(high)).all()
        assert schematic_display_distance_m(
            low, SCENE_OBSERVER_DISTANCE_M
        ) == schematic_display_distance_m(high, SCENE_OBSERVER_DISTANCE_M)

    def test_altitude_annotated_by_leader_label(self, evaluated) -> None:  # type: ignore[no-untyped-def]
        """The altitude is shown via a leader label (the not-to-scale annotation path)."""
        sensor, result = evaluated
        vs = ViewerState.from_chain_result(result, sensor)
        plotter = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=plotter)
            # The sensor glyph carries a leader-label triple (text + leader + dot).
            assert "lbl_observer_text" in plotter.actors
            assert "lbl_observer_leader" in plotter.actors
        finally:
            plotter.close()


class TestGeometryViewerWidget:
    """The embedded widget: headless static-image backend + degradation panel."""

    def test_image_backend_renders_headless(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.resize(720, 520)
        # Offscreen platform → no live interactor; the static-image backend is used.
        assert viewer.mode == "image"
        assert viewer.is_available and not viewer.is_degraded
        viewer.show_result(result, sensor)
        pixmap = viewer._image_label.pixmap()  # noqa: SLF001 — test inspects the render
        assert pixmap is not None and not pixmap.isNull()

    def test_degradation_panel_on_render_failure(self, qtbot, evaluated) -> None:  # type: ignore[no-untyped-def]
        """When the render is forced to fail, the actionable panel replaces the viewport."""
        from radiant.gui.viewer import viewer_widget
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = evaluated
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)

        def _boom(state, plotter=None, theme=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("no OpenGL context")

        # Break the scene render the interactor/image backend depends on.
        monkey = pytest.MonkeyPatch()
        monkey.setattr(viewer_widget, "build_static_scene", _boom)
        try:
            viewer.show_result(result, sensor)
        finally:
            monkey.undo()

        assert viewer.is_degraded
        assert viewer.mode == "unavailable"
        assert "no OpenGL context" in (viewer.unavailable_reason or "")
        # An actionable panel (objectName "viewerUnavailable") replaced the viewport.
        from PySide6.QtWidgets import QLabel

        panels = [w for w in viewer.findChildren(QLabel) if w.objectName() == "viewerUnavailable"]
        assert panels, "degradation panel not shown"
        assert "3D viewer unavailable" in panels[0].text()


class TestSceneImportsNoPhysicsStage:
    """The lifted scene library must not import any physics stage (gui → api + core)."""

    def test_no_physics_stage_import(self) -> None:
        scene_root = Path(__file__).resolve().parents[1] / "viewer"
        stage_re = re.compile(
            r"^\s*(?:from|import)\s+radiant\.(geometry|source|atmosphere|optics|platform"
            r"|spectral_integration|detector|readout|performance)\b",
            re.MULTILINE,
        )
        offenders: dict[str, list[str]] = {}
        for path in scene_root.rglob("*.py"):
            hits = stage_re.findall(path.read_text(encoding="utf-8"))
            if hits:
                offenders[str(path)] = hits
        assert not offenders, f"physics-stage imports in the viewer: {offenders}"


class TestGeometryPaneIntegration:
    """Category D: the Geometry center tabs Inputs | 3D View and renders on evaluate."""

    def test_geometry_pane_tabs_and_viewer(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        assert pane.has_tabs
        assert pane.tab_titles() == ["Inputs", "3D View"]
        assert pane.geometry_form is not None
        assert pane.geometry_readout is not None
        assert pane.geometry_viewer is not None

        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sensor.evaluate()
        pane.populate(result)
        # The viewer produced a static render bound to the evaluation.
        viewer = pane.geometry_viewer
        assert viewer is not None and viewer.is_available
        assert not viewer._image_label.pixmap().isNull()  # noqa: SLF001
