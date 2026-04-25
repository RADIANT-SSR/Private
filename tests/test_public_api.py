"""Public API surface tests — verifies CU-NEW-02 / ADR-C decisions hold."""

from __future__ import annotations

import pytest


@pytest.mark.level0
def test_top_level_sensor_import() -> None:
    """`from radiant import Sensor` resolves to the same class as the api path.

    Per ADR-C (docs/adr/ADR-C-public-api-surface.md), `Sensor` must be
    re-exported at the top-level `radiant` package so that
    `RADIANT_Scripting_API.md` examples written as `from radiant import Sensor`
    run verbatim.
    """
    from radiant import Sensor as TopLevelSensor
    from radiant.api.sensor import Sensor as ApiSensor

    assert TopLevelSensor is ApiSensor


@pytest.mark.level0
def test_top_level_all_exports_match_adr() -> None:
    """`radiant.__all__` matches the ADR-C decision: Sensor + __version__ only.

    SensorConfig, ScenarioConfig, BatchRunner are explicitly out per ADR-C.
    """
    import radiant

    assert set(radiant.__all__) == {"Sensor", "__version__"}


@pytest.mark.level1
def test_top_level_sensor_instantiates_and_evaluates() -> None:
    """End-to-end: import via top level, load minimal YAML, evaluate one frame.

    Exercises the doc example pattern — `Sensor.from_yaml(...).evaluate()` —
    using the top-level import path users will reach for first.
    """
    from radiant import Sensor

    s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
    result = s.evaluate()

    assert result is not None
    assert hasattr(result, "metrics")
