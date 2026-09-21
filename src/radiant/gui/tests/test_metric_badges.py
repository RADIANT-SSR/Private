"""CU-371 II-009: a metric badge says *why* a metric was not computed.

``badge_display`` used to answer three different absences with one sentence,
"n/a — not computed for this run": a metric group the analyst switched off, a
metric the scene-class relevance map turned off by default, and a metric the run
computed nothing for because it is not defined for the regime. The performance
stage now publishes its selection (``stage_outputs["performance"]["metric_selection"]``)
and the badge reads it. Each test here failed on the pre-fix code.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.metric_groups import GROUP_PARAMS  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.metric_format import (  # noqa: E402
    NOT_AVAILABLE,
    badge_display,
    not_computed_reason,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(sensor: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


@pytest.fixture(scope="module")
def example_result():  # type: ignore[no-untyped-def]
    return _evaluate(Sensor.load(_EXAMPLE))


class TestThreeStates:
    def test_group_switched_off_names_the_group(self) -> None:
        sensor = Sensor.load(_EXAMPLE)
        sensor.set(GROUP_PARAMS["interpretability"], False)
        result = _evaluate(sensor)
        value, reason = badge_display(result, "niirs")
        assert value == NOT_AVAILABLE
        assert reason == "not computed — the Interpretability metric group is off"

    def test_scene_class_suppression_says_how_to_override(self, example_result) -> None:  # type: ignore[no-untyped-def]
        """The example is an air-to-ground scene: target-plane sample distances are off
        by default there (relevance map), and selecting the group overrides that."""
        selection = example_result.stage_outputs["performance"]["metric_selection"]
        assert "target_plane_sample_distance_x_m" in selection.suppressed
        value, reason = badge_display(example_result, "target_plane_sample_distance_x_m")
        assert value == NOT_AVAILABLE
        assert reason == (
            "not computed — off by default for this scene class; select the "
            "Sampling / geometry group to compute it"
        )

    def test_group_ran_but_metric_not_defined_for_the_regime(self, example_result) -> None:  # type: ignore[no-untyped-def]
        """Detection range is a point-source metric; on an extended scene the
        radiometric group ran and simply did not produce it."""
        selection = example_result.stage_outputs["performance"]["metric_selection"]
        assert "radiometric" in selection.enabled_groups
        value, reason = badge_display(example_result, "detection_range_m")
        assert value == NOT_AVAILABLE
        assert reason == "not computed — not defined for this regime"

    def test_declined_reason_still_wins(self, example_result) -> None:  # type: ignore[no-untyped-def]
        """A metric the run declined with a reason keeps that reason (CU-375 F-27)."""
        _value, reason = badge_display(example_result, "niirs")
        assert reason is not None and "GIQE-5" in reason


class TestWithoutTheRecord:
    def test_legacy_result_reads_the_generic_wording(self) -> None:
        class _Legacy:
            stage_outputs = {"performance": {}}

            @staticmethod
            def metric_records() -> tuple[object, ...]:
                return ()

        assert not_computed_reason(_Legacy(), "niirs") == "not computed for this run"  # type: ignore[arg-type]
        assert badge_display(_Legacy(), "niirs") == (NOT_AVAILABLE, "not computed for this run")  # type: ignore[arg-type]
