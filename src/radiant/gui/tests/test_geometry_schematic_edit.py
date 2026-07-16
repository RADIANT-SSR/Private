"""Tests for the three Schematic-tab geometry changes (owner feedback 2026-07-14).

Item 1 — the redundant derived-angles table is removed from the Schematic tab's side panel
(it stays on the Inputs tab); the angle-arc reveal toggles remain.
Item 2 — geometry is **settable** from the Schematic tab: the side panel embeds the Phase-5
:class:`GeometryModeForm`, wired through the same edit → one ``sensor.set`` → debounced
re-evaluate → schematic re-render path as the Inputs tab; the two forms stay in sync.
Item 3 — selecting a target shape seeds its required dimensions to nominal non-zero values
(only where still at the ``0.0`` sentinel), so the re-evaluate succeeds (CU-125).

All drive the real widgets on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtWidgets import QTabWidget, QToolBox  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.param_format import format_value  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.geometry_angle_panel import (  # noqa: E402
    _SHAPE_DIMENSIONS,
    NOMINAL_SHAPE_DIMENSIONS,
    GeometryAnglePanel,
)
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm  # noqa: E402
from radiant.gui.widgets.geometry_readout import GeometryReadout  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_ALL_SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _geometry_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Geometry StagePane on the example config."""
    pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


def _load_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    window.resize(1280, 860)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


# ---------------------------------------------------------------------------
# Item 1 — the derived-angles table is gone from the Schematic side panel; the
# angle-arc selector moved out of the accordion onto the plot (2026-07-14 relayout)
# ---------------------------------------------------------------------------


class TestDerivedReadoutRemovedFromSchematic:
    def test_side_panel_has_no_derived_readout_and_no_angle_toggles(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Schematic panel drops the GeometryReadout table and the angle-arc toggles.

        The derived-angles readout stays on the Inputs tab; the angle-arc reveal selector
        moved onto the plot as a bottom-left overlay (owner feedback 2026-07-14).
        """
        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        # The derived-angles table (and its accessor) are gone.
        assert not panel.findChildren(GeometryReadout)
        assert not hasattr(panel, "readout")
        # The angle-arc reveal toggles are gone from the accordion (they live on the plot).
        assert not hasattr(panel, "angle_checkbox")
        assert not hasattr(panel, "angleToggled")

    def test_accordion_has_exactly_the_two_geometry_and_shape_pages(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The right-column accordion now holds only Geometry inputs + Target shape — no Angles."""
        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        toolbox = panel.findChild(QToolBox)
        assert toolbox is not None
        titles = [toolbox.itemText(i) for i in range(toolbox.count())]
        assert titles == ["Geometry inputs", "Target shape & orientation"]

    def test_geometry_pane_keeps_one_readout_on_the_inputs_tab_only(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Exactly one GeometryReadout survives — the Inputs tab's — none in the side panel."""
        pane = _geometry_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readouts = pane.findChildren(GeometryReadout)
        assert len(readouts) == 1
        assert pane.geometry_readout is readouts[0]
        assert pane.geometry_panel is not None
        assert not pane.geometry_panel.findChildren(GeometryReadout)


# ---------------------------------------------------------------------------
# Item 2 — geometry is settable from the Schematic tab (edit-and-watch)
# ---------------------------------------------------------------------------


class TestSchematicTabIsEditable:
    def test_side_panel_embeds_a_geometry_mode_form(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Schematic side panel mounts the reusable Phase-5 GeometryModeForm."""
        panel = GeometryAnglePanel()
        qtbot.addWidget(panel)
        assert isinstance(panel.geometry_form, GeometryModeForm)

    def test_geometry_pane_registers_both_forms_bound_to_one_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Inputs-tab + Schematic-tab forms both exist and read the same live sensor."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _geometry_pane(qtbot, sensor)
        forms = pane.findChildren(GeometryModeForm)
        assert len(forms) == 2  # Inputs tab + Schematic side panel
        inputs_form = pane.geometry_form
        schematic_form = pane.geometry_panel.geometry_form  # type: ignore[union-attr]
        assert inputs_form is not schematic_form
        # Both render the bound sensor's value (same live sensor).
        alt = "geometry.sensor_altitude_m"
        assert inputs_form.field_value_text(alt) == schematic_form.field_value_text(alt)
        assert schematic_form.field_value_text(alt).endswith("m")

    def test_edit_on_schematic_form_sets_once_reevaluates_and_moves_scene(
        self, qtbot, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """A Schematic-tab form edit → one sensor.set → re-evaluate → the schematic redraws.

        The two geometry forms stay in sync after the clean re-run (both show the new value).
        """
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("geometry")
        pane = center.pane("geometry")
        tabs = pane.findChild(QTabWidget)
        assert tabs is not None
        tabs.setCurrentIndex(1)  # Schematic
        for _ in range(4):
            qtbot.wait(1)

        canvas = pane.geometry_viewer.canvas  # type: ignore[union-attr]
        assert canvas is not None
        before = canvas.grab().toImage()

        dotpath = "geometry.path_zenith_rad"
        # Count only the sets on the LIVE sensor (the dialog validates on a clone first).
        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        schematic_form = pane.geometry_panel.geometry_form  # type: ignore[union-attr]
        # Drive the form's own edit path non-modally: fill the editor + commit (one sensor.set).
        from radiant.gui.widgets import geometry_mode_form as gmf

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("0.45")  # float param → QLineEdit
            self.apply(close=True)
            return 0

        monkeypatch.setattr(gmf.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            schematic_form._open_editor(dotpath)  # noqa: SLF001 — exercises the commit path

        # Exactly one set on the live sensor, for the edited parameter.
        assert set_calls.count(dotpath) == 1
        assert window.sensor.get_input(dotpath) == pytest.approx(0.45)

        # The schematic visibly redrew from the new geometry.
        after = canvas.grab().toImage()
        assert before != after

        # Both tabs' forms reflect the new value after the clean re-run (in sync).
        expected = format_value(0.45, window.sensor.parameter_def(dotpath).input_unit)
        assert pane.geometry_form.field_value_text(dotpath) == expected  # type: ignore[union-attr]
        assert schematic_form.field_value_text(dotpath) == expected


# ---------------------------------------------------------------------------
# Item 3 — selecting a shape seeds nominal dimensions (CU-125)
# ---------------------------------------------------------------------------


class TestNominalShapeDimensions:
    def test_nominal_map_covers_every_shape_required_dims(self) -> None:
        """Every non-``none`` shape's nominal keys are exactly its required-dim subset, > 0."""
        for shape, required in _SHAPE_DIMENSIONS.items():
            if shape == "none":
                assert shape not in NOMINAL_SHAPE_DIMENSIONS
                continue
            assert set(NOMINAL_SHAPE_DIMENSIONS[shape]) == set(required)
            assert all(v > 0.0 for v in NOMINAL_SHAPE_DIMENSIONS[shape].values())

    def test_selecting_shape_seeds_nominal_and_reevaluates_clean(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Picking a shape with unset dims seeds them to nominal and evaluates without error."""
        for shape in _ALL_SHAPES:
            sensor = Sensor.from_yaml(_EXAMPLE)
            pane = _geometry_pane(qtbot, sensor)
            panel = pane.geometry_panel
            assert panel is not None
            panel.shape_combo.setCurrentText(shape)  # emits shapeRequested → pane seeds dims
            for dotpath, nominal in NOMINAL_SHAPE_DIMENSIONS[shape].items():
                assert float(sensor.get(dotpath)) == pytest.approx(nominal)
            # The subsequent physics re-evaluate succeeds (no ParameterBoundsError / zero-error).
            assert _evaluate(sensor) is not None

    def test_user_set_dimension_is_never_overwritten(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A dim the user already set to a non-zero value survives a later shape pick."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("geometry.target.shape_radius_m", 3.0)
        pane = _geometry_pane(qtbot, sensor)
        pane.geometry_panel.shape_combo.setCurrentText("sphere")  # type: ignore[union-attr]
        assert float(sensor.get("geometry.target.shape_radius_m")) == pytest.approx(3.0)
        assert _evaluate(sensor) is not None


# ---------------------------------------------------------------------------
# The target dimension + RPY fields match the geometry fields by construction: clicking
# one opens the shared ParameterEditorDialog → one sensor.set (owner feedback 2026-07-14)
# ---------------------------------------------------------------------------


class TestTargetFieldEditing:
    def _edit_via_dialog(self, qtbot, monkeypatch, dotpath, text):  # type: ignore[no-untyped-def]
        """Click *dotpath*'s value field, fill the shared editor with *text*, and commit.

        Returns ``(sensor, pane, set_calls, edited)`` — the live-sensor set calls counted and
        the pane's parameterEdited emissions, so the caller asserts exactly one set + one
        re-evaluate for the edited parameter.
        """
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _geometry_pane(qtbot, sensor)
        panel = pane.geometry_panel
        assert panel is not None
        panel.shape_combo.setCurrentText("cylinder")  # seed nominal dims (radius, length)

        # Count only the sets on the LIVE sensor (the dialog validates on a clone first).
        set_calls: list[str] = []
        orig_set = type(sensor).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is sensor and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(sensor), "set", counting_set)

        from radiant.gui.widgets import stage_center as sc

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText(text)  # float param → QLineEdit
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sc.ParameterEditorDialog, "exec", fake_exec)

        edited: list[str] = []
        pane.parameterEdited.connect(edited.append)
        # Click the value button → editRequested → the pane opens the dialog → one sensor.set.
        row = panel.dimension_row(dotpath) if dotpath.endswith("_m") else panel.rpy_row(dotpath)
        row.value_button.click()
        return sensor, pane, set_calls, edited

    def test_dimension_edit_sets_once_and_reevaluates(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        dotpath = "geometry.target.shape_radius_m"
        sensor, _pane, set_calls, edited = self._edit_via_dialog(
            qtbot, monkeypatch, dotpath, "1.75"
        )
        assert set_calls.count(dotpath) == 1
        assert float(sensor.get_input(dotpath)) == pytest.approx(1.75)
        assert edited == [dotpath]

    def test_rpy_edit_sets_once_and_reevaluates(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        dotpath = "geometry.target.shape_yaw_rad"
        sensor, _pane, set_calls, edited = self._edit_via_dialog(qtbot, monkeypatch, dotpath, "0.3")
        assert set_calls.count(dotpath) == 1
        assert float(sensor.get_input(dotpath)) == pytest.approx(0.3)
        assert edited == [dotpath]

    def test_panel_field_reflects_committed_value(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """After a commit the panel's field text re-syncs to the new value + unit (pure view)."""
        dotpath = "geometry.target.shape_radius_m"
        _sensor, pane, _set_calls, _edited = self._edit_via_dialog(
            qtbot, monkeypatch, dotpath, "1.75"
        )
        text = pane.geometry_panel.dimension_row(dotpath).value_text()  # type: ignore[union-attr]
        assert text == format_value(1.75, "m")
