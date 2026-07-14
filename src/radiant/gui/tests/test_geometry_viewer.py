"""Tests for the 3D geometry viewer (GUI plan Phase 7 Parts A + B, ADR-0007).

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

Part B (interactions):

* :class:`TestAngleAnnotations` — click-to-reveal angle arcs draw their tube + a value
  label pinned from the stage output (never recomputed); the phase angle is symbol-only.
* :class:`TestFrameSplit` — the target-frame / ground-frame split matches the Phase-5
  ``GeometryReadout`` grouping.
* :class:`TestAngleTruthConsistency` — the **binding** task-4 test: viewer-local angle
  recomputation agrees with ``stage_outputs["geometry"]`` within an explicit tolerance.
* :class:`TestRpyTriad` — the RPY triad renders on demand and its axis endpoints follow
  the ``source.target.shape_{yaw,pitch,roll}_rad`` Euler rotation.
* :class:`TestShapeLibraryRoundTrip` — the schema-driven shape combo and RPY edits round
  trip through ``sensor.set`` and re-render the viewer.
* :class:`TestAnglePanel` — the accordion side panel shares the Phase-5 readout widget
  and emits toggle/shape/orientation intents.

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


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


@pytest.fixture
def offnadir_sphere() -> tuple[Sensor, object]:
    """A sensor viewed off-nadir with a discrete sphere target (fresh, mutable).

    Off-nadir so η > 0 (the off-nadir arc is visible and the consistency check is
    non-trivial), and a concrete shape so the RPY triad + target body render.
    """
    sensor = Sensor.from_yaml(_EXAMPLE)
    sensor.set("geometry.path_zenith_rad", 0.4)
    sensor.set("source.target.shape", "sphere")
    sensor.set("source.target.shape_radius_m", 1.0)
    return sensor, _evaluate(sensor)


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

        def _boom(state, plotter=None, theme=None, **kwargs):  # type: ignore[no-untyped-def]
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


class TestAngleAnnotations:
    """Part B task 1: click-to-reveal angle arcs + their stage-output value labels."""

    def test_reveal_draws_arc_and_value_label(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.scene import angle_annotations

        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        plotter = _offscreen_plotter()
        try:
            build_static_scene(
                vs,
                plotter=plotter,
                revealed_arcs=("off_nadir", "sun_zenith"),
                arc_value_texts={"off_nadir": "0.399 rad", "sun_zenith": "0.5 rad"},
            )
            actors = set(plotter.actors)
            # Both revealed arcs draw a tube; both pin a value label.
            assert "arc_off_nadir" in actors
            assert "arc_sun_zenith" in actors
            for name in ("off_nadir", "sun_zenith"):
                base = angle_annotations.value_label_actor_name(name)
                assert any(a.startswith(base) for a in actors), f"no value label for {name}"
        finally:
            plotter.close()

    def test_static_scene_has_no_arcs_by_default(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """No arc is revealed until requested — the default render is unchanged."""
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        plotter = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=plotter)
            assert not any(a.startswith("arc_") for a in plotter.actors)
        finally:
            plotter.close()

    def test_value_text_equals_stage_output(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The pinned value is the stage output verbatim (with unit), never recomputed."""
        from radiant.gui.param_format import format_value
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        geo = result.stage_outputs["geometry"]
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("off_nadir", True)
        viewer.set_angle_revealed("sun_zenith", True)
        texts = viewer._arc_value_texts()  # noqa: SLF001 — test inspects the formatting
        assert texts["off_nadir"] == format_value(geo["eta_rad"], "rad")
        assert texts["sun_zenith"] == format_value(geo["theta_s_rad"], "rad")

    def test_phase_angle_has_no_fabricated_value(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """The phase angle is symbol-only — the viewer pins no computed value for it."""
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("phase_angle", True)
        assert "phase_angle" not in viewer._arc_value_texts()  # noqa: SLF001

    def test_toggle_updates_revealed_state(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.viewer_widget import GeometryViewer

        sensor, result = offnadir_sphere
        viewer = GeometryViewer()
        qtbot.addWidget(viewer)
        viewer.show_result(result, sensor)
        viewer.set_angle_revealed("sun_zenith", True)
        assert viewer.revealed_angles == frozenset({"sun_zenith"})
        viewer.set_angle_revealed("sun_zenith", False)
        assert viewer.revealed_angles == frozenset()


class TestFrameSplit:
    """Part B task 1: target-frame vs ground-frame split matches the Phase-5 readout."""

    def test_annotation_frames(self) -> None:
        from radiant.gui.viewer.scene import angle_annotations as aa

        frames = {a.name: a.frame for a in aa.annotations()}
        # η is a ground/platform-frame angle; θ_s and the phase angle are target-frame.
        assert frames["off_nadir"] == aa.FRAME_GROUND
        assert frames["sun_zenith"] == aa.FRAME_TARGET
        assert frames["phase_angle"] == aa.FRAME_TARGET

    def test_stage_keys_are_target_or_ground_frame_readout_keys(self) -> None:
        """Every stage-backed annotation key is grouped the same way the readout groups it."""
        from radiant.gui.viewer.scene import angle_annotations as aa
        from radiant.gui.widgets import geometry_readout as gr

        target_keys: set[str] = set()
        ground_keys: set[str] = set()
        for title, keys in gr._GROUPS:  # noqa: SLF001 — reading the readout's own grouping
            if title == gr._TARGET_FRAME:
                target_keys = set(keys)
            elif title == gr._GROUND_FRAME:
                ground_keys = set(keys)
        for ann in aa.annotations():
            if ann.stage_key is None:
                continue
            if ann.frame == aa.FRAME_TARGET:
                assert ann.stage_key in target_keys
            else:
                assert ann.stage_key in ground_keys


class TestAngleTruthConsistency:
    """Part B task 4 (binding): viewer-local angle recomputation == stage output.

    The scene draws each arc from the ported ``geometry.js`` direction math (used only for
    camera / projection / picking). This test asserts that recomputing the angle from that
    same scene math agrees with ``stage_outputs["geometry"]`` — the stage is the single
    source of angle truth. Divergence beyond the explicit tolerance is a red build.
    """

    def test_recomputation_matches_stage_within_tolerance(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.viewer.scene import angle_truth

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
        # Guard the fixture actually exercised a non-trivial off-nadir angle.
        assert float(geo["eta_rad"]) > 0.1

    def test_tolerance_is_explicit_and_tight(self) -> None:
        from radiant.gui.viewer.scene import angle_truth

        assert angle_truth.ANGLE_CONSISTENCY_ABS_TOL_RAD == 1e-9


class TestRpyTriad:
    """Part B task 3: the RPY triad renders and reflects shape_yaw/pitch/roll."""

    def test_triad_renders_only_when_requested(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        sensor, result = offnadir_sphere
        vs = ViewerState.from_chain_result(result, sensor)
        without = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=without, show_triad=False)
            assert "body_axis_x" not in without.actors
        finally:
            without.close()
        with_triad = _offscreen_plotter()
        try:
            build_static_scene(vs, plotter=with_triad, show_triad=True)
            for axis in ("body_axis_x", "body_axis_y", "body_axis_z"):
                assert axis in with_triad.actors
        finally:
            with_triad.close()

    def test_triad_endpoints_follow_euler(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        """A yaw of π/2 rotates the body +X (roll) axis onto the scene +Y direction."""
        import numpy as np

        from radiant.gui.viewer.scene.frames import body_axes

        sensor, _result = offnadir_sphere
        sensor.set("source.target.shape_yaw_rad", np.pi / 2)
        result = _evaluate(sensor)
        vs = ViewerState.from_chain_result(result, sensor)
        ends = body_axes.axis_endpoints(vs)
        # +X body axis direction after yaw=π/2 should point along scene +Y.
        centroid = np.array(vs_centroid(vs))
        x_dir = np.asarray(ends["body_axis_x"]) - centroid
        x_dir = x_dir / np.linalg.norm(x_dir)
        assert x_dir[1] == pytest.approx(1.0, abs=1e-9)
        assert x_dir[0] == pytest.approx(0.0, abs=1e-9)

    def test_triad_reflects_orientation_change(self, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        import numpy as np

        from radiant.gui.viewer.scene.frames import body_axes

        sensor, result = offnadir_sphere
        vs0 = ViewerState.from_chain_result(result, sensor)
        centroid = np.array(vs_centroid(vs0))
        x0 = np.asarray(body_axes.axis_endpoints(vs0)["body_axis_x"]) - centroid
        sensor.set("source.target.shape_pitch_rad", 0.5)
        vs1 = ViewerState.from_chain_result(_evaluate(sensor), sensor)
        x1 = np.asarray(body_axes.axis_endpoints(vs1)["body_axis_x"]) - centroid
        assert not np.allclose(x0, x1)


def vs_centroid(vs) -> tuple[float, float, float]:  # type: ignore[no-untyped-def]
    from radiant.gui.viewer.scene.target._pose import target_centroid_scene

    return target_centroid_scene(vs)


class TestShapeLibraryRoundTrip:
    """Part B task 2: shape switch goes through sensor.set and re-renders."""

    def test_shape_combo_is_schema_driven(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The shape list comes from the schema enum_values, never a hardcoded list (Gap 70)."""
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane.bind_sensor(sensor, {})
        combo = pane.geometry_panel.shape_combo
        items = {combo.itemText(i) for i in range(combo.count())}
        assert items == set(sensor.parameter_defs()["source.target.shape"].enum_values)

    def test_shape_switch_sets_param_and_rerenders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("source.target.shape_radius_m", 1.0)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))

        edited: list[str] = []
        pane.parameterEdited.connect(edited.append)
        pane.geometry_panel.shape_combo.setCurrentText("sphere")

        # One sensor.set (round-trip) + a scheduled re-evaluate signal.
        assert sensor.get("source.target.shape") == "sphere"
        assert "source.target.shape" in edited
        # The viewer previewed the new shape from the updated params + last result.
        vs = ViewerState.from_chain_result(pane._last_result, sensor)  # noqa: SLF001
        assert vs.target_shape == "sphere"
        assert pane.geometry_viewer.is_available

    def test_rpy_edit_sets_param(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.stage_views import STAGE_COMPOSITIONS
        from radiant.gui.widgets.stage_center import StagePane

        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("source.target.shape", "sphere")
        sensor.set("source.target.shape_radius_m", 1.0)
        pane.bind_sensor(sensor, {})
        pane.populate(_evaluate(sensor))

        edited: list[str] = []
        pane.parameterEdited.connect(edited.append)
        pane.geometry_panel.rpy_spin("source.target.shape_yaw_rad").setValue(0.5)
        assert sensor.get("source.target.shape_yaw_rad") == pytest.approx(0.5, abs=1e-9)
        assert "source.target.shape_yaw_rad" in edited


class TestAnglePanel:
    """The accordion side panel shares the Phase-5 readout and drives the viewer."""

    def test_shares_geometry_readout_widget(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel
        from radiant.gui.widgets.geometry_readout import GeometryReadout

        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        assert isinstance(panel.readout, GeometryReadout)

    def test_toggle_emits_angle_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel

        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        seen: list[tuple[str, bool]] = []
        panel.angleToggled.connect(lambda name, on: seen.append((name, on)))
        panel.angle_checkbox("sun_zenith").setChecked(True)
        assert ("sun_zenith", True) in seen

    def test_triad_checkbox_emits(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel

        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        seen: list[bool] = []
        panel.triadToggled.connect(seen.append)
        panel.triad_checkbox.setChecked(True)
        assert seen == [True]

    def test_readout_populates_frame_groups(self, qtbot, offnadir_sphere) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.geometry_angle_panel import GeometryAnglePanel

        sensor, result = offnadir_sphere
        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        panel.populate_readout(result.stage_outputs["geometry"])
        titles = panel.readout.group_titles()
        assert "Target-frame angles" in titles
        assert "Ground / platform frame" in titles
