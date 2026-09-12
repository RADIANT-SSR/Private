"""Tests for the Calibration stage instrument (Gap 120, plan Phase 3 — §8 list).

The Calibration stage's contextual center: the scheme selector leading a
schema-driven inputs card with scheme-contextual groups, beside the Outputs
readout and the noise-budget plot. Every test drives the real widgets on the
shipped example config, offscreen. The scheme-switch-on-a-real-config test is
the Gap 117 live-review lesson applied from birth.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.calibration_inputs_form import (  # noqa: E402
    CalibrationInputsForm,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_ACTIVE_TWO_POINT = {
    "calibration.scheme": "two_point",
    "calibration.cal_temp_low_K": 290.0,
    "calibration.cal_temp_high_K": 310.0,
    "calibration.nonlinearity_pct": 1.0,
    "detector.prnu_pct": 2.0,
}


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _sensor(**inputs: object) -> Sensor:
    sensor = Sensor.load(_EXAMPLE)
    for name, value in inputs.items():
        sensor.set(name, value)
    return sensor


def _pane(qtbot, sensor: Sensor) -> StagePane:  # type: ignore[no-untyped-def]
    pane = StagePane("calibration", STAGE_COMPOSITIONS["calibration"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


# ---------------------------------------------------------------------------
# Composition (Qt-free)
# ---------------------------------------------------------------------------


class TestComposition:
    def test_calibration_composition_shape(self) -> None:
        comp = STAGE_COMPOSITIONS["calibration"]
        assert comp.calibration_inputs
        assert comp.outputs
        assert [p.method for p in comp.plots] == ["noise_budget"]
        assert "average down" in (comp.note or "")


# ---------------------------------------------------------------------------
# Form: schema coverage + contextual visibility (§8 item 3)
# ---------------------------------------------------------------------------


class TestSchemeVisibility:
    def test_all_twenty_one_parameters_are_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        assert set(form.field_dotpaths()) == {
            "calibration.scheme",
            "calibration.cal_temp_low_K",
            "calibration.cal_temp_mid_K",
            "calibration.cal_temp_high_K",
            "calibration.nonlinearity_pct",
            "calibration.time_since_cal_s",
            "calibration.gain_drift_frac_per_s",
            "calibration.offset_drift_e_per_s",
            "calibration.source_emissivity",
            "calibration.source_uniformity_K",
            "calibration.source_temp_uncertainty_K",
            "calibration.source_emissivity_uncertainty",
            "calibration.band_center_uncertainty_um",
            "calibration.gain_uncertainty_pct",
            "calibration.cal_path",
            "calibration.shutter_after_element",
            "calibration.narcissus_fpn_pct",
            "calibration.cal_point_mode",
            "calibration.cal_flux_low",
            "calibration.cal_flux_mid",
            "calibration.cal_flux_high",
        }

    def test_none_shows_only_the_selector(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(_sensor(), {})
        for dotpath in form.field_dotpaths():
            visible = not form.row(dotpath).isHidden()
            assert visible == (dotpath == "calibration.scheme"), dotpath

    def test_two_point_shows_everything_but_the_mid_point(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(_sensor(**_ACTIVE_TWO_POINT), {})
        hidden_by_default = {
            "calibration.shutter_after_element",  # full_aperture default
            "calibration.narcissus_fpn_pct",
            "calibration.cal_flux_low",  # temperature mode default (item 5)
            "calibration.cal_flux_mid",
            "calibration.cal_flux_high",
        }
        for dotpath in form.field_dotpaths():
            if dotpath == "calibration.cal_temp_mid_K":
                assert form.row(dotpath).isHidden()  # three_point-only (Gap 122 item 2)
                continue
            if dotpath in hidden_by_default:
                assert form.row(dotpath).isHidden(), dotpath
                continue
            assert not form.row(dotpath).isHidden(), dotpath

    def test_three_point_shows_everything(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(
            _sensor(
                **{
                    "calibration.scheme": "three_point",
                    "calibration.cal_temp_low_K": 285.0,
                    "calibration.cal_temp_mid_K": 300.0,
                    "calibration.cal_temp_high_K": 315.0,
                }
            ),
            {},
        )
        hidden_by_default = {
            "calibration.shutter_after_element",  # full_aperture default
            "calibration.narcissus_fpn_pct",
            "calibration.cal_flux_low",  # temperature mode default (item 5)
            "calibration.cal_flux_mid",
            "calibration.cal_flux_high",
        }
        for dotpath in form.field_dotpaths():
            if dotpath in hidden_by_default:
                assert form.row(dotpath).isHidden(), dotpath
                continue
            assert not form.row(dotpath).isHidden(), dotpath

    def test_internal_shutter_reveals_its_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Gap 122 item 4: the shutter rows appear only under internal_shutter."""
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(
            _sensor(
                **_ACTIVE_TWO_POINT,
                **{
                    "calibration.cal_path": "internal_shutter",
                    "calibration.shutter_after_element": 1,
                },
            ),
            {},
        )
        assert not form.row("calibration.cal_path").isHidden()
        assert not form.row("calibration.shutter_after_element").isHidden()
        assert not form.row("calibration.narcissus_fpn_pct").isHidden()

    def test_flux_mode_swaps_the_point_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Gap 122 item 5: flux mode shows flux rows, hides temperature rows
        AND the temperature-anchored bias rows the stage would reject."""
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(
            _sensor(
                **{
                    "calibration.scheme": "two_point",
                    "calibration.cal_point_mode": "flux_fraction",
                    "calibration.cal_flux_low": 0.3,
                    "calibration.cal_flux_high": 0.9,
                }
            ),
            {},
        )
        assert not form.row("calibration.cal_flux_low").isHidden()
        assert not form.row("calibration.cal_flux_high").isHidden()
        assert form.row("calibration.cal_flux_mid").isHidden()  # two_point
        for dotpath in (
            "calibration.cal_temp_low_K",
            "calibration.cal_temp_high_K",
            "calibration.source_uniformity_K",
            "calibration.source_temp_uncertainty_K",
            "calibration.band_center_uncertainty_um",
        ):
            assert form.row(dotpath).isHidden(), dotpath

    def test_one_point_hides_two_point_physics(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(
            _sensor(**{"calibration.scheme": "one_point", "calibration.cal_temp_low_K": 300.0}),
            {},
        )
        assert form.row("calibration.cal_temp_high_K").isHidden()
        assert form.row("calibration.nonlinearity_pct").isHidden()
        assert not form.row("calibration.cal_temp_low_K").isHidden()
        assert not form.row("calibration.time_since_cal_s").isHidden()


# ---------------------------------------------------------------------------
# Scheme switch survives a real config (§8 item 2 — the Gap 117 lesson)
# ---------------------------------------------------------------------------


class TestSchemeSwitchOnRealConfig:
    def test_switch_cycle_never_breaks_and_none_restores(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _sensor()
        baseline = _evaluate(sensor).metrics
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})

        # none -> two_point (with points) -> one_point -> none, evaluating
        # at every step: no crash, no strand.
        for name, value in _ACTIVE_TWO_POINT.items():
            sensor.set(name, value)
        form.refresh()
        active = _evaluate(sensor).metrics
        assert active["snr"] < baseline["snr"]

        sensor.set("calibration.scheme", "one_point")
        form.refresh()
        _evaluate(sensor)  # unused two-point knobs strand nothing (no over-spec)

        sensor.set("calibration.scheme", "none")
        sensor.set("detector.prnu_pct", 0.0)  # restore the example's default
        form.refresh()
        restored = _evaluate(sensor).metrics
        assert restored["snr"] == pytest.approx(baseline["snr"], rel=1e-12)

    def test_incomplete_scheme_raises_the_advisory_type(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.api.calibration_state import is_calibration_config_incomplete

        sensor = _sensor(**{"calibration.scheme": "two_point"})
        with pytest.raises(Exception) as excinfo:
            _evaluate(sensor)
        assert is_calibration_config_incomplete(excinfo.value)


# ---------------------------------------------------------------------------
# Sentinel + display units (§8 item 4)
# ---------------------------------------------------------------------------


class TestSentinelAndUnits:
    def test_unset_cal_temp_renders_as_words(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(_sensor(**{"calibration.scheme": "two_point"}), {})
        assert form.field_value_text("calibration.cal_temp_low_K") == "unset — required"
        assert form.field_value_text("calibration.cal_temp_high_K") == "unset — required"

    def test_time_since_cal_displays_in_hours(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        form = CalibrationInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(_sensor(**{**_ACTIVE_TWO_POINT, "calibration.time_since_cal_s": 24.0}), {})
        text = form.field_value_text("calibration.time_since_cal_s")
        # Entry/display symmetric (display-units hard rule): entered 24 hours,
        # reads back in hours — never the canonical 86 400 s.
        assert "hour" in text
        assert "86" not in text


# ---------------------------------------------------------------------------
# Outputs readout truth (§8 item 5) + default quiet screen (§8 item 6)
# ---------------------------------------------------------------------------


class TestOutputsReadout:
    def test_readout_values_match_api(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _sensor(**_ACTIVE_TWO_POINT)
        pane = _pane(qtbot, sensor)
        outputs = pane.outputs_readout
        assert outputs is not None
        result = _evaluate(sensor)
        cal = result.stage_outputs["calibration"]
        assert cal["sigma_calibration_e"] > 0.0
        # The readout renders this stage's outputs verbatim (units via
        # api.stage_output_units); the sigma row must carry the e- unit.
        text = outputs.value_text("sigma_calibration_e")
        assert text and "e-" in text

    def test_default_screen_is_quiet(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = _sensor()
        pane = _pane(qtbot, sensor)
        form = pane.calibration_inputs_form
        assert form is not None
        assert form.field_value_text("calibration.scheme").startswith("none")
        result = _evaluate(sensor)
        assert result.stage_outputs["calibration"]["enabled"] is False
        assert not any(t.name == "nuc_residual" for t in result.noise_terms)
