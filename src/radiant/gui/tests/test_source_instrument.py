"""Tests for the Source stage instrument (GUI plan Phase PS-1, arch doc §4.4.1 Source rows).

The Source stage's contextual center becomes a real instrument, matching the Geometry-screen
standard: pre-atmosphere target + background **emission** spectra
(``result.plot.spectral_source_emission``, FP-1), editable schema-driven radiometric inputs
(the shared :class:`FieldRow`), the shared target shape/size/orientation editor
(:class:`TargetShapePanel` — the same widget the Geometry Schematic tab mounts), and an
Outputs readout carrying the tentative regime with units. Every test drives the real widgets
on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.field_row import FieldRow  # noqa: E402
from radiant.gui.widgets.source_inputs_form import _RADIOMETRY_FIELDS  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402
from radiant.gui.widgets.target_shape_panel import (  # noqa: E402
    NOMINAL_SHAPE_DIMENSIONS,
    TargetShapePanel,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_ALL_SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _source_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Source StagePane on the example config."""
    pane = StagePane("source", STAGE_COMPOSITIONS["source"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


def _load_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    window.resize(1440, 900)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


# ---------------------------------------------------------------------------
# Composition (Qt-free)
# ---------------------------------------------------------------------------


class TestSourceComposition:
    def test_emission_is_the_primary_plot(self) -> None:
        """The Source composition leads with the FP-1 pre-atmosphere emission accessor."""
        comp = STAGE_COMPOSITIONS["source"]
        methods = [p.method for p in comp.plots]
        assert methods[0] == "spectral_source_emission"
        # The at-aperture radiance is kept as a secondary plot (owner: keep it available).
        assert "spectral_source" in methods

    def test_source_declares_inputs_shape_and_outputs(self) -> None:
        """The instrument sections are declared: radiometric inputs, shape, outputs."""
        comp = STAGE_COMPOSITIONS["source"]
        assert comp.source_inputs is True
        assert comp.target_shape is True
        assert comp.outputs is True


# ---------------------------------------------------------------------------
# The pane composition (plots + inputs + shape + outputs)
# ---------------------------------------------------------------------------


class TestSourcePane:
    def test_emission_figure_renders_after_evaluate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Source center draws the emission-spectrum figure (target arm) after evaluate."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.plot_canvases  # at least the emission section
        assert pane.plot_canvases[0].has_figure()

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every radiometric input is the shared FieldRow (by-construction consistency)."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.source_inputs_form
        assert form is not None
        for _label, dotpath in _RADIOMETRY_FIELDS:
            assert isinstance(form.row(dotpath), FieldRow)
        # The value carries its unit (R-UNITS): temperature reads in K.
        assert form.field_value_text("source.target.temperature").endswith("K")

    def test_shape_panel_is_present_and_shared(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Source stage mounts the shared TargetShapePanel; its dim/RPY rows are FieldRows."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        panel = pane.target_shape_panel
        assert isinstance(panel, TargetShapePanel)
        # Shape choices come from the schema enum (never hardcoded, Gap 70).
        assert panel.shape_combo.count() > 1
        assert isinstance(panel.dimension_row("geometry.target.shape_radius_m"), FieldRow)
        assert isinstance(panel.rpy_row("geometry.target.shape_yaw_rad"), FieldRow)
        # No 3D scene on the Source stage → no triad toggle.
        assert not panel.triad_checkbox.isVisible()

    def test_outputs_readout_shows_regime_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Outputs readout carries the tentative regime + a dimensional output with unit."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "regime_tentative" in keys
        # The enum renders by its value string, not its repr.
        assert readout.value_text("regime_tentative") == "extended"
        # A dimensional source output carries its unit (R-UNITS).
        assert readout.value_text("angular_extent_rad").endswith("rad")


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, refresh
# ---------------------------------------------------------------------------


class TestSourceEditAndWatch:
    def test_editing_target_temperature_sets_once_and_reevaluates(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """A radiometric-input edit → one live sensor.set → debounced re-evaluate → refresh."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("source")
        pane = center.pane("source")
        form = pane.source_inputs_form
        assert form is not None

        dotpath = "source.target.temperature"
        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import source_inputs_form as sif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("321.0")  # float param → QLineEdit
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001 — exercises the commit path

        # Exactly one set on the live sensor, for the edited parameter.
        assert set_calls.count(dotpath) == 1
        assert window.sensor.get_input(dotpath) == pytest.approx(321.0)
        # The form re-synced to the committed value and the emission figure re-rendered.
        assert form.field_value_text(dotpath) == "321 K"
        assert pane.plot_canvases[0].has_figure()

    def test_selecting_shape_seeds_nominal_and_reevaluates_clean(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Picking a shape on the Source stage seeds nominal dims (CU-125) and evaluates clean."""
        for shape in _ALL_SHAPES:
            sensor = Sensor.from_yaml(_EXAMPLE)
            pane = _source_pane(qtbot, sensor)
            panel = pane.target_shape_panel
            assert panel is not None
            edited: list[str] = []
            pane.parameterEdited.connect(edited.append)
            panel.shape_combo.setCurrentText(shape)  # emits shapeRequested → pane seeds dims
            for dotpath, nominal in NOMINAL_SHAPE_DIMENSIONS[shape].items():
                assert float(sensor.get(dotpath)) == pytest.approx(nominal)
            assert edited == ["geometry.target.shape"]
            # The subsequent physics re-evaluate succeeds (no ParameterBoundsError).
            assert _evaluate(sensor) is not None
