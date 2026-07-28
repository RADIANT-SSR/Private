"""Tests for the Platform + Readout stage instruments (GUI plan Phase PS-5, arch doc §4.4.1).

Both stages are v1-minimal (owner-ratified): a single flat pane with editable schema-driven
:class:`FieldRow` inputs beside the scalar Outputs readout (values with units), a themed
"v1-minimal" note, and — for Readout only — the scalar noise budget (read noise + quantization
live in this stage; §4.7 relocates the Noise Budget detail tab to the Detector/Readout views).
Platform carries no dedicated MTF (owner ratified: the smear/jitter MTF terms stay in the
Optics/Performance overlays). Every figure is one call on the bound ``result.plot.*`` accessor;
every test drives the real widgets on the shipped example config, offscreen.
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
from radiant.gui.widgets.platform_inputs_form import (  # noqa: E402
    _JITTER_FIELDS,
    _MOTION_FIELDS,
)
from radiant.gui.widgets.readout_inputs_form import (  # noqa: E402
    _ACQUISITION_FIELDS,
    _ADC_FIELDS,
    _BINNING_FIELDS,
    _COADD_FIELDS,
    _NOISE_FIELDS,
    _TDI_FIELDS,
    _WELL_FIELDS,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000

_GAIN = "readout.gain_e_per_dn"
_READ_NOISE = "readout.read_noise_e_rms"
_JITTER_RMS = "platform.jitter_rms_urad"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _pane(qtbot, namespace: str, sensor: Sensor) -> StagePane:
    """A bound, populated StagePane for *namespace* on the example config."""
    pane = StagePane(namespace, STAGE_COMPOSITIONS[namespace])
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
# Composition (Qt-free) — single flat panes, v1-minimal sections
# ---------------------------------------------------------------------------


class TestComposition:
    def test_platform_inputs_tab_is_unchanged_v1_minimal(self) -> None:
        """The Inputs tab keeps the v1-minimal content: inputs + outputs + the note.

        Owner walkthrough item 15 made Platform tabbed, so these fields moved from
        the composition onto its first sub-view. The owner-ratified "no dedicated
        MTF here" decision is unchanged — the new tab shows the PSF kernels this
        stage convolves in, not an MTF view.
        """
        comp = STAGE_COMPOSITIONS["platform"]
        inputs = {sv.title: sv for sv in comp.subviews}["Inputs"]
        assert inputs.platform_inputs is True
        assert inputs.outputs is True
        assert inputs.plots == ()
        assert inputs.note is not None and "v1-minimal" in inputs.note

    def test_platform_psf_degradation_tab_shows_kernels_and_result(self) -> None:
        """Item 15: the kernels this stage applies, beside the PSF they produced."""
        comp = STAGE_COMPOSITIONS["platform"]
        assert [sv.title for sv in comp.subviews] == ["Inputs", "PSF degradation"]
        psf_tab = {sv.title: sv for sv in comp.subviews}["PSF degradation"]
        assert [p.method for p in psf_tab.plots] == ["psf_kernels", "psf"]

    def test_readout_binds_inputs_outputs_noise_budget_and_note(self) -> None:
        """Readout: editable inputs + outputs + the scalar noise budget + a v1-minimal note."""
        comp = STAGE_COMPOSITIONS["readout"]
        assert comp.readout_inputs is True
        assert comp.outputs is True
        assert [p.method for p in comp.plots] == ["noise_budget"]
        assert comp.note is not None and "v1-minimal" in comp.note
        assert comp.subviews == ()


# ---------------------------------------------------------------------------
# The panes render: shared inputs, scalar outputs with units, the note
# ---------------------------------------------------------------------------


class TestPlatformPane:
    def test_renders_as_tabs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Item 15 turned Platform into a two-tab composite (was a single flat pane)."""
        pane = _pane(qtbot, "platform", Sensor.from_yaml(_EXAMPLE))
        assert pane.has_tabs
        assert pane.tab_titles() == ["Inputs", "PSF degradation"]

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every platform input is the shared FieldRow (by-construction consistency)."""
        pane = _pane(qtbot, "platform", Sensor.from_yaml(_EXAMPLE))
        form = pane.platform_inputs_form
        assert form is not None
        for _label, dotpath in (*_JITTER_FIELDS, *_MOTION_FIELDS):
            assert isinstance(form.row(dotpath), FieldRow)
        # Jitter reads in µrad, ground velocity in m/s (R-UNITS: every value carries its unit).
        assert form.field_value_text(_JITTER_RMS).endswith("urad")
        assert form.field_value_text("platform.ground_velocity_m_s").endswith("m/s")

    def test_outputs_readout_shows_platform_scalars_with_units(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        pane = _pane(qtbot, "platform", Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "smear_width_m" in keys
        assert readout.value_text("smear_width_m").endswith("m")
        # EE_box is a dimensionless fraction — rendered as a bare number.
        assert "EE_box" in keys

    def test_v1_minimal_note_present(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtWidgets import QLabel

        pane = _pane(qtbot, "platform", Sensor.from_yaml(_EXAMPLE))
        notes = [lbl.text() for lbl in pane.findChildren(QLabel) if lbl.objectName() == "stageNote"]
        assert any("v1-minimal" in text for text in notes)


class TestReadoutPane:
    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every readout input is the shared FieldRow (by-construction consistency)."""
        pane = _pane(qtbot, "readout", Sensor.from_yaml(_EXAMPLE))
        form = pane.readout_inputs_form
        assert form is not None
        for _label, dotpath in (
            *_NOISE_FIELDS,
            *_ADC_FIELDS,
            *_WELL_FIELDS,
            *_TDI_FIELDS,
            *_COADD_FIELDS,
            *_BINNING_FIELDS,
            *_ACQUISITION_FIELDS,
        ):
            assert isinstance(form.row(dotpath), FieldRow)
        # The read noise + gain + well are dimensionless-in-schema scalars (e- RMS / e-/DN / e-
        # carried by the value, no input_unit suffix), so they render as bare numbers here.
        assert form.field_value_text(_GAIN)  # non-empty value text

    def test_acquisition_fields_render_schema_values(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        """Gap 102: TDI / co-add / binning / frame-period rows show live schema values.

        The enum row (tdi_mode) renders its schema string; the frame period (seconds,
        R3.4 frame-timing contract) carries its unit suffix (R-UNITS hard rule); the
        integer counts render non-empty. Values come from the live schema defaults of
        the example config (n_tdi=1, tdi_mode default, frame_period_s=0.0 = unset).
        """
        pane = _pane(qtbot, "readout", Sensor.from_yaml(_EXAMPLE))
        form = pane.readout_inputs_form
        assert form is not None
        assert form.field_value_text("readout.n_tdi")  # non-empty integer text
        assert form.field_value_text("readout.tdi_mode")  # enum string, non-empty
        assert form.field_value_text("readout.n_coadds")
        assert form.field_value_text("readout.binning_x_onchip")
        # Frame period is schema unit seconds — the row text must carry the unit.
        assert form.field_value_text("readout.frame_period_s").endswith("s")

    def test_noise_budget_plot_renders(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The scalar noise budget draws from ``result.plot.noise_budget`` after evaluate."""
        pane = _pane(qtbot, "readout", Sensor.from_yaml(_EXAMPLE))
        assert len(pane.plot_canvases) == 1
        assert pane.plot_canvases[0].has_figure()

    def test_outputs_readout_shows_readout_scalars_with_units(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        pane = _pane(qtbot, "readout", Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "signal_dn_final" in keys and "sigma_total_e" in keys
        assert readout.value_text("signal_dn_final").endswith("DN")
        assert readout.value_text("sigma_total_e").endswith("e-")
        # Gap 102: frame-timing outputs (R3.4) surface with units for edit-and-watch.
        assert "frame_rate_hz" in keys and "duty_cycle" in keys
        assert readout.value_text("frame_rate_hz").endswith("Hz")


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, the Outputs readout refreshes
# ---------------------------------------------------------------------------


class TestReadoutEditAndWatch:
    def test_editing_read_noise_sets_once_reevaluates_and_outputs_refresh(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Editing the read noise → one live sensor.set → re-evaluate → total noise rises."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("readout")
        pane = center.pane("readout")
        form = pane.readout_inputs_form
        assert form is not None

        sigma_before = window.last_result.stage_outputs["readout"]["sigma_total_e"]

        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import readout_inputs_form as rif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("50")  # raise read noise from 5 to 50 e- RMS
            self.apply(close=True)
            return 0

        monkeypatch.setattr(rif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(_READ_NOISE)  # noqa: SLF001 — exercises the commit path

        assert set_calls.count(_READ_NOISE) == 1
        assert window.sensor.get_input(_READ_NOISE) == pytest.approx(50.0, rel=1e-9)
        # Read noise adds in quadrature to the total: raising it raises sigma_total_e.
        sigma_after = window.last_result.stage_outputs["readout"]["sigma_total_e"]
        assert sigma_after > sigma_before
        # The Outputs readout re-read the new total-noise value (still carries its unit).
        assert pane.outputs_readout is not None
        assert pane.outputs_readout.value_text("sigma_total_e").endswith("e-")
