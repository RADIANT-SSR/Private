"""Pinning tests for GUI polish batch A (CU-363, CU-367, and the Findings-Log lines it works).

Each test reproduces one item's symptom on the real widgets, offscreen, and asserts the
fixed behaviour; every one failed on the pre-fix code. Items: the detector sub-view
overflowing its viewport at the default layout (CU-363), the point-intensity sentinel
shown as physics (CU-367), overlapping leader pills and unclamped marker names, the
stacked atmosphere axes' labels, the undo history's silent bottom (F-33), the eight
disabled menu actions with no reason (F-36), the editor preview on an unresolvable
configuration (F-50), Run ▸ Validate Only never wired, no Cancel on the evaluate loop,
"Changed only" hiding preset-supplied values, the legacy alias bullet on the scene-class
card, the two geometry forms holding pending door choices apart, and the explain echo's
stray space.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QScrollArea  # noqa: E402

from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.inspect import ResultPlotNamespace  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.viewer.schematic_view import SchematicView  # noqa: E402
from radiant.gui.viewer.viewer_state import ViewerState  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402
from radiant.gui.widgets.scene_class_panel import off_metric_labels  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_IRST = (
    _REPO
    / "scenarios/10_direction_general/10.2_air_to_air_level_irst/inputs"
    / "10.2_air_to_air_level_irst.gui.yaml"
)
_WAIT_MS = 15000


def _evaluate(sensor: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _load_window(qtbot, path: Path = _EXAMPLE) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow(Sensor.load(path))
    qtbot.addWidget(window)
    window.resize(1440, 900)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestCU363DetectorFormFitsItsViewport:
    def test_default_layout_has_no_horizontal_overflow(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """1440×900, Detector ▸ Inputs: the sub-view used to be 664 px wide in a 622 px
        viewport, clipping the value boxes behind a horizontal scrollbar."""
        window = _load_window(qtbot)
        window.show()
        window.central_canvas.select_stage("detector")
        qtbot.wait(50)
        pane = window.central_canvas.stage_center.pane("detector")
        areas = [
            a for a in pane.findChildren(QScrollArea) if a.objectName() == "stageSubViewScroll"
        ]
        assert areas, "the Detector sub-views scroll vertically only"
        form = pane.detector_inputs_form
        assert form is not None
        row = form.row("detector.pixel_pitch_x_um")
        assert row.value_text() == "18 µm"
        # The value box sits inside its form, and the form inside its viewport, so no
        # digit is cut off behind a scrollbar.
        assert row.value_button.geometry().right() <= form.width()
        scroll = form.parentWidget()
        while scroll is not None and not isinstance(scroll, QScrollArea):
            scroll = scroll.parentWidget()
        assert scroll is not None
        assert scroll.horizontalScrollBar().maximum() == 0
        assert form.width() <= scroll.viewport().width()


class TestCU363ValueBoxNeverClipsItsText:
    def test_minimum_width_follows_the_text(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A geometry card value such as "705000 m" used to render "'05000 m" at a
        narrow dock width; the box now asks for at least its text width."""
        from radiant.gui.widgets.field_row import VALUE_BOX_MAX, FieldRow

        row = FieldRow("geometry.sensor_altitude_m", "sensor_altitude_m", lambda _d: None)
        qtbot.addWidget(row)
        from radiant.gui.widgets.field_row import VALUE_BOX_MIN

        long_text = "1234567.890123 km"  # wider than the shared floor
        row.set_value_text(long_text)
        needed = row.value_button.fontMetrics().horizontalAdvance(long_text)
        assert needed > VALUE_BOX_MIN
        assert needed <= row.value_button.minimumWidth() <= VALUE_BOX_MAX
        row.set_value_text("—")
        assert row.value_button.minimumWidth() == VALUE_BOX_MIN  # back to the floor


class TestCU367PointIntensityTarget:
    @pytest.fixture(scope="class")
    def irst(self):  # type: ignore[no-untyped-def]
        config_set = ConfigurationSet.load(_IRST)
        sensor = config_set.base
        return sensor, _evaluate(sensor)

    def test_source_plot_shows_intensity_not_sentinel_radiance(self, irst) -> None:  # type: ignore[no-untyped-def]
        sensor, result = irst
        fig = ResultPlotNamespace(result).spectral_source_emission()
        ax = fig.axes[0]
        assert "W/sr/µm" in ax.get_ylabel()
        assert "Intensity" in ax.get_ylabel()
        ymax = max(line.get_ydata().max() for line in ax.get_lines())
        assert ymax < 1e9  # not I / 1e-12 m²

    def test_schematic_labels_the_target_as_a_point(self, qtbot, irst) -> None:  # type: ignore[no-untyped-def]
        sensor, result = irst
        state = ViewerState.from_chain_result(result, sensor)
        assert state.intensity_target
        view = SchematicView()
        qtbot.addWidget(view)
        view.set_state(state)
        scene = view._scene  # noqa: SLF001 — the built scene
        assert scene is not None
        assert scene.target_area_label == "point (intensity input)"
        assert "1e-12" not in (scene.target_area_label or "")


class TestSchematicLabels:
    def test_pills_never_overlap_each_other(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The level IRST scene draws h_s, h_t, Δh and the target pill at fixed offsets."""
        sensor = ConfigurationSet.load(_IRST).base
        result = _evaluate(sensor)
        view = SchematicView()
        qtbot.addWidget(view)
        view.set_state(ViewerState.from_chain_result(result, sensor))
        view.setMinimumSize(1, 1)
        view.resize(220, 160)  # small enough that offset pills would collide
        view.grab()
        rects = view.pill_rects
        assert len(rects) >= 2
        for i, a in enumerate(rects):
            for b in rects[i + 1 :]:
                assert not a.intersects(b), f"pills overlap: {a} / {b}"
        bounds = QRectF(0.0, 0.0, 220.0, 160.0)
        assert all(bounds.contains(r) for r in rects)


class TestAtmosphereAxisLabels:
    def test_stacked_axes_carry_two_line_labels(self) -> None:
        result = _evaluate(Sensor.load(_EXAMPLE))
        fig = ResultPlotNamespace(result).spectral_atmosphere()
        labels = [ax.get_ylabel() for ax in fig.axes]
        assert any("\n" in label and "L_path" in label for label in labels)
        assert any("\n" in label and "τ_atm" in label for label in labels)


class TestF33UndoBottomIsAnnounced:
    def test_filling_the_history_says_so(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot)
        for i in range(20):
            window.sensor.set("geometry.sensor_altitude_m", 500000.0 + i)
            window.parameter_panel.parameterEdited.emit("geometry.sensor_altitude_m")
        assert window._undo_stack.count() == 20  # noqa: SLF001
        assert "undo history keeps the last 20 edits" in window.statusBar().currentMessage()


class TestF36DisabledActionsExplainThemselves:
    def test_every_never_wired_action_carries_a_reason(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        for key in (
            "edit.find",
            "view.font_larger",
            "view.font_smaller",
            "tools.preferences",
            "help.docs",
            "help.examples",
            "help.about",
        ):
            action = window.action(key)
            assert not action.isEnabled()
            assert action.statusTip().startswith("Not in this build"), key


class TestF50EditorPreviewOnAnUnresolvableConfiguration:
    def test_preview_shows_the_unit_conversion_while_typing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        window._on_blank_config()  # noqa: SLF001
        panel = window.parameter_panel
        dialog = ParameterEditorDialog(
            window.sensor,
            "geometry.sensor_altitude_m",
            panel._after_dialog_commit,
            panel,  # noqa: SLF001
        )
        qtbot.addWidget(dialog)
        dialog.unit_combo.setCurrentText("km")
        dialog.value_editor.setText("500")
        assert dialog._preview_label.text() == "= 500000 m"  # noqa: SLF001


class TestValidateOnlyIsWired:
    def test_complete_configuration_reports_valid(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot)
        action = window.action("run.validate")
        assert action.isEnabled()
        action.trigger()
        assert window.statusBar().currentMessage().startswith("Configuration valid")

    def test_incomplete_configuration_routes_as_an_advisory(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets import actionable_error_dialog as aed

        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: 0)
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        window._on_blank_config()  # noqa: SLF001
        window.action("run.validate").trigger()
        assert "incomplete" in window.statusBar().currentMessage().lower()
        assert window.right_rail.messages.has_error()


class TestCancelOnTheEvaluateLoop:
    def test_cancel_button_shows_while_running_and_stops_the_pass(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        cancel = window.right_rail.cancel_button
        # The load schedules a run; while it is in flight the Cancel is offered.
        qtbot.waitUntil(lambda: window._worker is not None, timeout=_WAIT_MS)  # noqa: SLF001
        assert cancel.isVisibleTo(window.right_rail)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            cancel.click()
        assert not cancel.isVisibleTo(window.right_rail)


class TestChangedOnlyIncludesPresetValues:
    def test_preset_provenance_counts_as_changed(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot)
        window.sensor.set("detector.pixel_pitch_x_um", 15.0, source="preset:test")
        panel = window.parameter_panel
        panel.populate(window.sensor)
        panel._changed_only.setChecked(True)  # noqa: SLF001
        item = panel._items["detector.pixel_pitch_x_um"]  # noqa: SLF001
        assert not item.isHidden()


class TestSceneClassCardHidesTheLegacyAlias:
    def test_air_to_air_lists_each_metric_once(self) -> None:
        labels = off_metric_labels("air_to_air")
        assert labels
        assert not any("legacy key" in label for label in labels)
        assert len(labels) == len(set(labels))


class TestGeometryFormsSharePendingChoice:
    def test_choice_on_one_tab_shows_on_the_other(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _load_window(qtbot)
        pane = window.central_canvas.stage_center.pane("geometry")
        inputs_form = pane.geometry_form
        assert inputs_form is not None
        forms = pane._geometry_forms  # noqa: SLF001
        assert len(forms) == 2
        inputs_form.choose_mode("solar", "S3")
        assert forms[1].active_mode("solar") == "S3"


class TestExplainEchoHasNoStraySpace:
    def test_dimensionless_parameter_echo(self) -> None:
        sensor = Sensor.load(_EXAMPLE)
        text = sensor.explain("optics.f_number")
        first = text.splitlines()[0]
        assert "  (" not in first and " )" not in first
        assert first.startswith("optics.f_number = ")
