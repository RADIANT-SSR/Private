"""Tests for the Optics stage instrument (GUI plan Phase PS-2, arch doc §4.4.1 Optics rows).

The Optics stage's contextual center becomes the richest per-stage instrument and the **first
production use** of the tabbed sub-view hook (``StageComposition.subviews``): four tabs —
**Inputs** (editable optics :class:`FieldRow`s + the FINAL-regime outputs readout, Rule 10),
**MTF** (the per-term MTF@Nyquist table + ``mtf()`` overlay + the ``mtf_budget()`` bar),
**PSF + Pupil** (``psf()`` beside the FP-2 ``pupil_amplitude()`` apodization map and
``pupil_phase()`` wavefront-error map in WAVES), and **Throughput** (the FP-3
``optical_throughput()`` τ_opt(λ) + per-element ``coating_spectra()``). Each plot is one call
on the bound ``result.plot.*`` accessor. Every test drives the real widgets on the shipped
example config, offscreen.
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
from radiant.gui.widgets.optics_inputs_form import _OPTICS_FIELDS  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_TAB_TITLES = ["Inputs", "MTF", "PSF + Pupil", "Throughput"]


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _optics_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Optics StagePane on the example config."""
    pane = StagePane("optics", STAGE_COMPOSITIONS["optics"])
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
# Composition (Qt-free) — the tabbed sub-view hook, first production use
# ---------------------------------------------------------------------------


class TestOpticsComposition:
    def test_optics_declares_four_subview_tabs(self) -> None:
        """PS-2: the Optics composition is the first stage to populate ``subviews``."""
        comp = STAGE_COMPOSITIONS["optics"]
        assert [sv.title for sv in comp.subviews] == _TAB_TITLES

    def test_each_tab_binds_the_expected_accessors(self) -> None:
        """Each tab's plots name the verbatim bound ``result.plot.*`` accessors (per §4.4.1)."""
        subviews = {sv.title: sv for sv in STAGE_COMPOSITIONS["optics"].subviews}
        # Inputs tab: the editable optics form + the FINAL-regime outputs readout (Rule 10).
        assert subviews["Inputs"].optics_inputs is True
        assert subviews["Inputs"].outputs is True
        # MTF tab: the relocated MtfPanel (table + mtf() overlay) + the mtf_budget bar.
        assert subviews["MTF"].mtf_panel is True
        assert [p.method for p in subviews["MTF"].plots] == ["mtf_budget"]
        # PSF + Pupil tab: psf + the two FP-2 complex-pupil maps.
        assert [p.method for p in subviews["PSF + Pupil"].plots] == [
            "psf",
            "pupil_amplitude",
            "pupil_phase",
        ]
        # Throughput tab: the two FP-3 accessors.
        assert [p.method for p in subviews["Throughput"].plots] == [
            "optical_throughput",
            "coating_spectra",
        ]


# ---------------------------------------------------------------------------
# The pane renders as tabs, each tab's figures come from the bound accessors
# ---------------------------------------------------------------------------


class TestOpticsPane:
    def test_center_renders_as_tabs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Optics center renders a QTabWidget with the four sub-view titles."""
        pane = _optics_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.has_tabs
        assert pane.tab_titles() == _TAB_TITLES

    def test_every_tab_figure_renders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every diagnostic figure across the tabs draws (budget/psf/pupil/throughput/coating)."""
        pane = _optics_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.plot_canvases  # budget + psf + 2 pupil maps + throughput + coating
        assert all(c.has_figure() for c in pane.plot_canvases)

    def test_mtf_tab_carries_the_per_term_table(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The MTF tab embeds the shared MtfPanel (per-term MTF@Nyquist table + overlay)."""
        pane = _optics_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.mtf_panel is not None and pane.mtf_panel.is_populated()
        assert pane.mtf_panel.term_names()  # discovered terms, not hand-listed

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every optics input is the shared FieldRow (by-construction consistency)."""
        pane = _optics_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.optics_inputs_form
        assert form is not None
        for _label, dotpath in _OPTICS_FIELDS:
            assert isinstance(form.row(dotpath), FieldRow)
        # The value carries its unit (R-UNITS): aperture reads in m.
        assert form.field_value_text("optics.aperture_diameter_m").endswith("m")

    def test_outputs_readout_shows_final_regime_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Outputs readout carries the FINAL regime (Rule 10) + a dimensional output."""
        pane = _optics_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "regime" in keys  # the OpticsStage FINAL classification (Rule 10)
        assert readout.value_text("regime") == "extended"
        # A dimensional optics output carries its unit (R-UNITS).
        assert readout.value_text("A_collect").endswith("m²")


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, the maps refresh
# ---------------------------------------------------------------------------


class TestOpticsEditAndWatch:
    def test_editing_wfe_sets_once_reevaluates_and_maps_refresh(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the WFE → one live sensor.set → debounced re-evaluate → the pupil-phase map
        gains structure (an unaberrated config renders a flat phase map)."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("optics")
        pane = center.pane("optics")
        form = pane.optics_inputs_form
        assert form is not None

        dotpath = "optics.wfe_rms_waves"
        live = window.sensor
        # Unaberrated to start: the shipped example carries wfe_rms_waves = 0 (flat phase map).
        assert float(live.get_input(dotpath)) == pytest.approx(0.0)

        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import optics_inputs_form as oif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("0.25")  # float param → QLineEdit
            self.apply(close=True)
            return 0

        monkeypatch.setattr(oif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001 — exercises the commit path

        # Exactly one set on the live sensor, for the edited parameter.
        assert set_calls.count(dotpath) == 1
        assert window.sensor.get_input(dotpath) == pytest.approx(0.25)
        # The form re-synced to the committed value and every Optics tab re-rendered.
        assert form.field_value_text(dotpath).startswith("0.25")
        assert pane.plot_canvases and all(c.has_figure() for c in pane.plot_canvases)
        # The re-evaluated pupil-phase map now carries non-trivial WFE structure (was flat).
        phase = window.last_result.stage_outputs["optics"]["pupil_phase_waves"]
        assert float(phase.max() - phase.min()) > 0.0

    def test_editing_transmission_reevaluates_throughput(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the scalar throughput → one sensor.set → the throughput/coating tab refreshes."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("optics")
        pane = center.pane("optics")
        form = pane.optics_inputs_form
        assert form is not None

        dotpath = "optics.transmission_scalar"
        from radiant.gui.widgets import optics_inputs_form as oif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("0.55")
            self.apply(close=True)
            return 0

        monkeypatch.setattr(oif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001

        assert window.sensor.get_input(dotpath) == pytest.approx(0.55)
        # The re-assembled system throughput reflects the new scalar τ_opt.
        tau = window.last_result.stage_outputs["optics"]["tau_opt_spectral"]
        assert float(tau.values.max()) == pytest.approx(0.55, abs=1e-9)
        assert pane.plot_canvases and all(c.has_figure() for c in pane.plot_canvases)
