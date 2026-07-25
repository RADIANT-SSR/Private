"""Tests for the Performance metric-group selection card (Gap 96, GUI side).

The Performance stage mounts a :class:`PerformanceMetricsForm`: five checkboxes bound to the
``performance.metrics.*`` group flags. Each toggle is one ``sensor.set`` + ``parameterEdited``
(one GUI action ↔ one API call), so the host re-evaluates and the Metrics readout re-renders
with the reduced set. These tests drive the real widgets offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.metric_groups import GROUP_PARAMS, METRIC_GROUPS  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _performance_pane(qtbot, sensor: Sensor) -> StagePane:
    pane = StagePane("performance", STAGE_COMPOSITIONS["performance"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


class TestComposition:
    def test_performance_declares_metric_selection(self) -> None:
        """The selection row sits on the (flat) Performance pane above the metric cards."""
        assert STAGE_COMPOSITIONS["performance"].metric_selection is True


class TestMetricSelectionForm:
    def test_form_present_with_five_group_checkboxes(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.metric_selection_form
        assert form is not None
        assert set(form.group_dotpaths()) == set(GROUP_PARAMS.values())

    def test_defaults_all_checked(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = _performance_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        form = pane.metric_selection_form
        assert form is not None
        for dotpath in form.group_dotpaths():
            assert form.is_checked(dotpath) is True

    def test_toggle_flips_config_and_emits(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Unchecking a group is exactly one sensor.set + one parameterEdited."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _performance_pane(qtbot, sensor)
        form = pane.metric_selection_form
        assert form is not None

        dotpath = GROUP_PARAMS["saturation"]
        with qtbot.waitSignal(form.parameterEdited, timeout=1000) as blocker:
            form.checkbox(dotpath).setChecked(False)

        assert blocker.args == [dotpath]
        assert sensor.get_input(dotpath) is False  # the flip reached the API

    def test_toggle_then_reevaluate_reduces_surfaced_metrics(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """After turning Saturation off and re-evaluating, its metrics are gone."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        pane = _performance_pane(qtbot, sensor)
        form = pane.metric_selection_form
        assert form is not None
        readout = pane.metric_cards
        assert readout is not None

        # Baseline: a saturation metric is shown.
        assert "well_margin_dB" in readout.rendered_keys()

        form.checkbox(GROUP_PARAMS["saturation"]).setChecked(False)
        pane.populate(_evaluate(sensor))  # host would do this on parameterEdited

        keys = set(readout.rendered_keys())
        assert keys.isdisjoint(METRIC_GROUPS["saturation"])
        assert "snr" in keys  # other groups untouched

    def test_bind_reflects_sensor_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A flag already off in the sensor renders as an unchecked box on bind."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set(GROUP_PARAMS["sampling"], False)
        pane = _performance_pane(qtbot, sensor)
        form = pane.metric_selection_form
        assert form is not None
        assert form.is_checked(GROUP_PARAMS["sampling"]) is False
        assert form.is_checked(GROUP_PARAMS["radiometric"]) is True
