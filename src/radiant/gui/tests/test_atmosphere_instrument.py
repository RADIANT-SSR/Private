"""Tests for the Atmosphere stage instrument (GUI Capability Expansion plan GS-2).

The Atmosphere stage gains its first editable Inputs card (audit A-1…A-4 closed): the
``atmosphere.model`` selector with only the active backend's parameter group visible
(simple / MODTRAN / tabulated / interpolated / exo-note), turbulence r₀, the scalar
Outputs readout, and the propagation story told before/after (source emission → τ &
L_path → radiance at aperture). Every field is a schema-driven :class:`FieldRow`; every
figure is one call on the bound ``result.plot.*`` accessor. Tests drive the real widgets
on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.atmosphere_inputs_form import (  # noqa: E402
    _INTERPOLATED_FIELDS,
    _MODTRAN_FIELDS,
    _SIMPLE_FIELDS,
    _TABULATED_FIELDS,
    AtmosphereInputsForm,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_MODEL = "atmosphere.model"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _pane(qtbot, sensor: Sensor) -> StagePane:  # type: ignore[no-untyped-def]
    pane = StagePane("atmosphere", STAGE_COMPOSITIONS["atmosphere"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


class TestComposition:
    def test_atmosphere_declares_inputs_outputs_and_three_plots(self) -> None:
        spec = STAGE_COMPOSITIONS["atmosphere"]
        assert spec.atmosphere_inputs
        assert spec.outputs
        methods = [p.method for p in spec.plots]
        # The before/after propagation story: τ&L_path, pre-atmosphere emission,
        # at-aperture radiance — in that reading order.
        assert methods == ["spectral_atmosphere", "spectral_source_emission", "spectral_source"]


class TestForm:
    def test_pane_mounts_bound_form_with_schema_fields(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _pane(qtbot, sensor)
        form = pane.atmosphere_inputs_form
        assert form is not None
        paths = form.field_dotpaths()
        assert _MODEL in paths
        for _, dotpath in _SIMPLE_FIELDS + _MODTRAN_FIELDS:
            assert dotpath in paths
        # Values render with the schema (model shows its enum string).
        assert "simple" in form.row(_MODEL).value_text()

    def test_only_active_model_group_visible(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _pane(qtbot, sensor)
        pane.show()
        form = pane.atmosphere_inputs_form
        assert form is not None
        # Example config runs the simple model: its group shows, the others hide.
        assert form.group_visible("simple")
        assert not form.group_visible("modtran")
        assert not form.group_visible("tabulated")
        assert not form.group_visible("interpolated")

    def test_model_edit_swaps_visible_group(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _pane(qtbot, sensor)
        pane.show()
        form = pane.atmosphere_inputs_form
        assert form is not None
        # One API call — the same call the editor dialog commits — then refresh.
        sensor.set(_MODEL, "exo")
        form.refresh()
        assert not form.group_visible("simple")
        assert form._exo_note.isVisible()
        sensor.set(_MODEL, "tabulated")
        form.refresh()
        assert form.group_visible("tabulated")
        assert not form._exo_note.isVisible()

    def test_unbound_form_blanks_and_shows_all_groups(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = AtmosphereInputsForm()
        qtbot.addWidget(form)
        form.show()
        form.bind_sensor(None, {})
        assert form.row(_MODEL).value_text() == "—"
        for key in ("simple", "modtran", "tabulated", "interpolated"):
            assert form.group_visible(key)

    def test_parameter_edited_signal_relays(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _pane(qtbot, sensor)
        form = pane.atmosphere_inputs_form
        assert form is not None
        with qtbot.waitSignal(pane.parameterEdited, timeout=1000) as blocker:
            form.parameterEdited.emit("atmosphere.visibility_km")
        assert blocker.args == ["atmosphere.visibility_km"]


class TestEditAndWatch:
    def test_visibility_edit_changes_atmosphere_outputs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The GS-2 checkpoint physics: hazier air → lower band-mean transmittance."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        clear = _evaluate(sensor.clone())
        sensor.set("atmosphere.visibility_km", 5.0)
        hazy = _evaluate(sensor)
        tau_clear = float(clear.stage_outputs["atmosphere"]["tau_atm"].mean())
        tau_hazy = float(hazy.stage_outputs["atmosphere"]["tau_atm"].mean())
        assert tau_hazy < tau_clear

    def test_exo_model_gives_unity_transmittance(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set(_MODEL, "exo")
        result = _evaluate(sensor)
        tau = float(result.stage_outputs["atmosphere"]["tau_atm"].mean())
        assert tau == pytest.approx(1.0, abs=1e-12)


class TestFieldManifest:
    def test_tabulated_and_interpolated_fields_exist_in_schema(self) -> None:
        """Every manifest dot-path is a real schema parameter (never transcribed wrong)."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        defs = sensor.parameter_defs()
        for _, dotpath in _TABULATED_FIELDS + _INTERPOLATED_FIELDS:
            assert dotpath in defs, f"unknown parameter in manifest: {dotpath}"
