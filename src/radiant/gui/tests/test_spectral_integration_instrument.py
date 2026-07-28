"""Tests for the Spectral-Integration stage instrument (GUI plan Phase PS-4, arch doc §4.4.1).

The Spectral-Integration stage's contextual center becomes an instrument (a single flat pane):
the editable band + acquisition inputs (``filter_min_um`` / ``filter_max_um`` under a *Filter
bandpass* heading, ``integration_time_s`` under an *Acquisition* heading — the arch-doc §4.4.1
GUI-grouping note, no schema change), the scalar electron-budget Outputs readout, the in-band
signal spectral radiance as the primary plot (``result.plot.spectral_inband``), and the Gap-92
note (per-λ noise is scalar per term, computed once post-integration — Rule 8). Every figure is
one call on the bound ``result.plot.*`` accessor. Every test drives the real widgets on the
shipped example config, offscreen.
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
from radiant.gui.widgets.spectral_integration_inputs_form import (  # noqa: E402
    _FILTER_FIELDS,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_INTEGRATION_TIME = "spectral_integration.integration_time_s"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _spectral_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Spectral-Integration StagePane on the example config."""
    pane = StagePane("spectral_integration", STAGE_COMPOSITIONS["spectral_integration"])
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
# Composition (Qt-free) — a single flat pane, the §4.4.1 sections
# ---------------------------------------------------------------------------


class TestSpectralComposition:
    def test_composition_binds_the_expected_sections(self) -> None:
        """The §4.4.1 Spectral-Integration rows: inputs + outputs + inband plot + Gap-92 note."""
        comp = STAGE_COMPOSITIONS["spectral_integration"]
        assert comp.spectral_inputs is True
        assert comp.outputs is True
        assert [p.method for p in comp.plots] == ["spectral_inband"]
        # The note names the deferral so it reads as intentional, not missing.
        assert comp.note is not None and "Gap 92" in comp.note

    def test_stage_stays_a_flat_pane(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Spectral Integration is a single flat pane (no sub-view tabs) — owner judgment."""
        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert not pane.has_tabs
        assert pane.tab_titles() == []


# ---------------------------------------------------------------------------
# The pane renders: the in-band spectrum, the shared inputs, the scalar outputs
# ---------------------------------------------------------------------------


class TestSpectralPane:
    def test_inband_spectrum_renders_from_the_accessor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The primary plot draws ``result.plot.spectral_inband`` after evaluate."""
        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert len(pane.plot_canvases) == 1
        assert pane.plot_canvases[0].has_figure()

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every spectral input is the shared FieldRow (by-construction consistency)."""
        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.spectral_inputs_form
        assert form is not None
        for _label, dotpath in _FILTER_FIELDS:
            assert isinstance(form.row(dotpath), FieldRow)
        # The band edges carry their unit (R-UNITS): µm.
        assert form.field_value_text(_FILTER_MAX).endswith("um")

    def test_integration_time_is_not_duplicated_here(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Owner walkthrough item 21: integration time is edited on Readout, not here.

        It was mounted on both forms, so the same parameter had two editors. The
        schema is untouched — the parameter keeps its ``spectral_integration.``
        dot-path and its owning stage; only which form surfaces it changed.
        """
        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.spectral_inputs_form
        assert form is not None
        assert _INTEGRATION_TIME not in [dotpath for _label, dotpath in _FILTER_FIELDS]
        with pytest.raises(KeyError):
            form.row(_INTEGRATION_TIME)
        # The schema is untouched: the sensor still exposes the canonical dot-path.
        sensor = Sensor.from_yaml(_EXAMPLE)
        assert sensor.get_input(_INTEGRATION_TIME) is not None

    def test_outputs_readout_shows_scalars_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Outputs readout carries the spectral-integration electron budget with units."""
        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "signal_e" in keys
        assert readout.value_text("signal_e").endswith("e-")
        # e_rate_per_s is electrons/second (owner hard rule: every value has a unit).
        assert "e_rate_per_s" in keys
        assert readout.value_text("e_rate_per_s").endswith("e-/s")

    def test_gap92_note_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A themed note tells the owner the per-λ noise spectrum is deferred (Gap 92)."""
        from PySide6.QtWidgets import QLabel

        pane = _spectral_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        notes = [lbl.text() for lbl in pane.findChildren(QLabel) if lbl.objectName() == "stageNote"]
        assert any("Gap 92" in text for text in notes)


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, the in-band spectrum refreshes
# ---------------------------------------------------------------------------


class TestSpectralEditAndWatch:
    def test_editing_filter_max_sets_once_reevaluates_and_spectrum_refreshes(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the long band edge → one live sensor.set → re-evaluate → the spectrum redraws."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("spectral_integration")
        pane = center.pane("spectral_integration")
        form = pane.spectral_inputs_form
        assert form is not None

        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import spectral_integration_inputs_form as sif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("4.5")  # narrow the band from 5.0 µm to 4.5 µm
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(_FILTER_MAX)  # noqa: SLF001 — exercises the commit path

        assert set_calls.count(_FILTER_MAX) == 1
        assert window.sensor.get_input(_FILTER_MAX) == pytest.approx(4.5, rel=1e-9)
        # The in-band spectrum re-rendered against the re-clipped band.
        assert pane.plot_canvases and all(c.has_figure() for c in pane.plot_canvases)

    def test_editing_integration_time_scales_the_electron_budget(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the integration time → one sensor.set → the signal_e scales with it.

        Driven from the **Readout** form since walkthrough item 21 removed the
        duplicate editor from the Spectral-Integration card; the parameter and its
        effect on the spectral-integration electron budget are unchanged.
        """
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("readout")
        pane = center.pane("readout")
        form = pane.readout_inputs_form
        assert form is not None

        signal_before = window.last_result.stage_outputs["spectral_integration"]["signal_e"]

        from radiant.gui.widgets import readout_inputs_form as sif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("0.010")  # double the 5 ms integration time
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(_INTEGRATION_TIME)  # noqa: SLF001

        assert window.sensor.get_input(_INTEGRATION_TIME) == pytest.approx(0.010, rel=1e-9)
        signal_after = window.last_result.stage_outputs["spectral_integration"]["signal_e"]
        # Signal integrates linearly in t_int (Rule 8): doubling t_int doubles signal_e.
        assert signal_after == pytest.approx(2.0 * signal_before, rel=1e-6)
