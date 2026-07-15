"""Tests for the Detector stage instrument (GUI plan Phase PS-3, arch doc §4.4.1 Detector rows).

The Detector stage's contextual center becomes a tabbed instrument (the §4.4 sub-view hook, as
Optics): three tabs — **Inputs** (editable detector :class:`FieldRow`s + the scalar outputs
readout), **Noise** (the ratified framework **pie** ``result.plot.noise_pie`` as the primary
chart above the per-term table + click-to-explain, the bar suppressed), and **Detector + PSF**
(the Qt-drawn pixel illustration beside ``result.plot.psf_pixel_grid`` — the PSF with the
detector pixel grid overlaid). Every figure is one call on the bound ``result.plot.*`` accessor.
Every test drives the real widgets on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.detector_inputs_form import _DETECTOR_FIELDS  # noqa: E402
from radiant.gui.widgets.field_row import FieldRow  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_TAB_TITLES = ["Inputs", "Noise", "Detector + PSF"]


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _detector_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Detector StagePane on the example config."""
    pane = StagePane("detector", STAGE_COMPOSITIONS["detector"])
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
# Composition (Qt-free) — the tabbed sub-view hook
# ---------------------------------------------------------------------------


class TestDetectorComposition:
    def test_detector_declares_three_subview_tabs(self) -> None:
        comp = STAGE_COMPOSITIONS["detector"]
        assert [sv.title for sv in comp.subviews] == _TAB_TITLES

    def test_each_tab_binds_the_expected_content(self) -> None:
        """Each tab's sections/accessors match the §4.4.1 Detector rows."""
        subviews = {sv.title: sv for sv in STAGE_COMPOSITIONS["detector"].subviews}
        # Inputs: the editable detector form + the scalar outputs readout.
        assert subviews["Inputs"].detector_inputs is True
        assert subviews["Inputs"].outputs is True
        # Noise: the per-term panel (bar suppressed) + the framework pie as the primary chart.
        assert subviews["Noise"].noise_panel is True
        assert subviews["Noise"].noise_panel_chart is False
        assert [p.method for p in subviews["Noise"].plots] == ["noise_pie"]
        # Detector + PSF: the Qt illustration + the PSF-with-pixel-grid accessor.
        assert subviews["Detector + PSF"].detector_illustration is True
        assert [p.method for p in subviews["Detector + PSF"].plots] == ["psf_pixel_grid"]


# ---------------------------------------------------------------------------
# The pane renders as tabs; every section populates from the API surface
# ---------------------------------------------------------------------------


class TestDetectorPane:
    def test_center_renders_as_tabs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _detector_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.has_tabs
        assert pane.tab_titles() == _TAB_TITLES

    def test_noise_pie_and_psf_grid_figures_render(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Both plot sections (noise pie + PSF-with-grid) draw from their bound accessors."""
        pane = _detector_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert len(pane.plot_canvases) == 2
        assert all(c.has_figure() for c in pane.plot_canvases)

    def test_noise_table_present_with_units_and_bar_suppressed(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        """The per-term table + click-to-explain are shown; the redundant bar is suppressed."""
        pane = _detector_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        panel = pane.noise_panel
        assert panel is not None and panel.is_populated()
        assert panel.term_names()  # discovered terms, not hand-listed
        # e- RMS unit on the σ column (owner hard rule).
        assert any("e- RMS" in panel.table.item(r, 1).text() for r in range(panel.table.rowCount()))
        # The bar chart is suppressed (the pie is the primary chart on this view).
        assert not panel.canvas.has_figure()
        # Click-to-explain still works.
        panel.select_term(0)
        assert panel.explain.toPlainText().strip()

    def test_illustration_reflects_pixel_pitch(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The pixel schematic is drawn from the live pixel pitch + fill factor (µm)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _detector_pane(qtbot, sensor)
        illustration = pane.detector_illustration
        assert illustration is not None
        px, py, ff = illustration.pixel_geometry
        assert px == pytest.approx(float(sensor.get_input("detector.pixel_pitch_x_um")))
        assert py == pytest.approx(float(sensor.get_input("detector.pixel_pitch_y_um")))
        assert ff == pytest.approx(float(sensor.get_input("detector.fill_factor")))

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every detector input is the shared FieldRow (by-construction consistency)."""
        pane = _detector_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.detector_inputs_form
        assert form is not None
        for _label, dotpath in _DETECTOR_FIELDS:
            assert isinstance(form.row(dotpath), FieldRow)
        # The pixel pitch carries its unit (R-UNITS): reads in µm.
        assert form.field_value_text("detector.pixel_pitch_x_um").endswith("um")

    def test_outputs_readout_shows_detector_scalars_with_units(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        pane = _detector_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "signal_e" in keys and "dark_e" in keys
        assert readout.value_text("signal_e").endswith("e-")


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, the pie / illustration refresh
# ---------------------------------------------------------------------------


class TestDetectorEditAndWatch:
    def test_editing_dark_rate_sets_once_reevaluates_and_pie_refreshes(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the dark rate → one live sensor.set → re-evaluate → the noise pie redraws."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("detector")
        pane = center.pane("detector")
        form = pane.detector_inputs_form
        assert form is not None

        dotpath = "detector.dark_rate_e_per_s"
        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import detector_inputs_form as dif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("5000")  # raise the dark rate substantially
            self.apply(close=True)
            return 0

        monkeypatch.setattr(dif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001 — exercises the commit path

        assert set_calls.count(dotpath) == 1
        assert window.sensor.get_input(dotpath) == pytest.approx(5000.0)
        # The re-evaluated dark shot noise rose (√(dark_e) grew with the dark rate).
        dark_shot = {nt.name: nt.value_e for nt in window.last_result.noise_terms}["dark_shot"]
        assert dark_shot > 0.7071  # was √0.5 at the default 100 e-/s
        # Every Detector plot re-rendered (the pie now carries a larger dark_shot share).
        assert pane.plot_canvases and all(c.has_figure() for c in pane.plot_canvases)

    def test_editing_pixel_pitch_redraws_illustration(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the cross-track pixel pitch → one sensor.set → the illustration redraws."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("detector")
        pane = center.pane("detector")
        form = pane.detector_inputs_form
        assert form is not None

        dotpath = "detector.pixel_pitch_x_um"
        from radiant.gui.widgets import detector_inputs_form as dif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("30")
            self.apply(close=True)
            return 0

        monkeypatch.setattr(dif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001

        assert window.sensor.get_input(dotpath) == pytest.approx(30.0)
        # The pixel schematic re-read the new cross-track pitch.
        assert pane.detector_illustration is not None
        assert pane.detector_illustration.pixel_geometry[0] == pytest.approx(30.0)
