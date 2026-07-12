"""Registry ↔ chain reconciliation (Gap 71 / CU-078).

Every metric key a real chain run produces must have a MetricSpec (with
a non-empty unit), and ChainResult.metric_records() must render the full
unit-labelled table. This is the drift tripwire: adding a with_metric()
call to PerformanceStage without a registry entry fails here.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor
from radiant.io.results import ChainResult
from radiant.performance.registry import METRIC_SPECS

_EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def result() -> ChainResult:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NIIRS extrapolation warning, unrelated
        return Sensor.from_yaml(_EXAMPLE).evaluate()


@pytest.mark.level2
class TestReconciliation:
    def test_every_computed_metric_has_a_spec(self, result: ChainResult) -> None:
        unregistered = set(result.metrics) - set(METRIC_SPECS)
        assert not unregistered, (
            f"Metrics computed without a registry entry (CU-078 drift): "
            f"{sorted(unregistered)}. Add a MetricSpec with unit + description "
            "in radiant/performance/registry.py."
        )

    def test_metric_records_cover_all_metrics_with_units(self, result: ChainResult) -> None:
        records = result.metric_records()
        assert {r.name for r in records} == set(result.metrics)
        for r in records:
            assert r.unit, f"metric '{r.name}' rendered without a unit"
            assert r.value == pytest.approx(result.metrics[r.name], rel=0.0, abs=0.0)

    def test_can_compute_true_for_every_computed_metric(self, result: ChainResult) -> None:
        """The computability oracle must not contradict reality."""
        from radiant.performance.registry import can_compute

        for name in result.metrics:
            assert can_compute(name, result.state), (
                f"can_compute('{name}') is False for a state where the chain "
                "actually computed it — spec dependencies are wrong."
            )
