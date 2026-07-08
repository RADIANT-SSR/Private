"""Level 0 tests for radiant.api.batch — cartesian batch runner (scenario 4.1).

The runner is exercised with a stub sensor factory — no chain runs. The
contract under test: cartesian ordering, override application, per-cell
error capture (Rule 17: failures are recorded rows, never silently
dropped), and the pivot helper.
"""

from __future__ import annotations

import pytest

from radiant.api.batch import BatchResult, BatchRunner, BatchRunnerError
from radiant.core.exceptions import RadiantError


class FakeSensor:
    """Records set() calls; stands in for radiant.api.Sensor."""

    def __init__(self, base_config: dict[str, object]) -> None:
        self.base_config = base_config
        self.overrides: dict[str, object] = {}

    def set(self, dotpath: str, value: object) -> FakeSensor:
        self.overrides[dotpath] = value
        return self


def fake_factory(base_config: dict[str, object]) -> FakeSensor:
    return FakeSensor(base_config)


BASE = {"optics": {"aperture_diameter_m": 0.3}}

AXES = [
    (
        "target",
        {
            "tank": {"source.target.temperature": 310.0},
            "truck": {"source.target.temperature": 300.0},
        },
    ),
    (
        "atmosphere",
        {"clear": {"atmosphere.visibility_km": 50.0}, "haze": {"atmosphere.visibility_km": 10.0}},
    ),
]


class TestCartesianProduct:
    def test_row_count_and_order(self) -> None:
        runner = BatchRunner(BASE, AXES, sensor_factory=fake_factory)
        result = runner.run(lambda sensor, labels: {"snr": 1.0})
        assert len(result.rows) == 4
        # Last axis varies fastest (row-major over the axis order).
        order = [(r["target"], r["atmosphere"]) for r in result.rows]
        assert order == [("tank", "clear"), ("tank", "haze"), ("truck", "clear"), ("truck", "haze")]

    def test_overrides_applied_per_cell(self) -> None:
        seen: list[dict[str, object]] = []

        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            seen.append(dict(sensor.overrides))
            return {}

        BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)
        assert seen[0] == {"source.target.temperature": 310.0, "atmosphere.visibility_km": 50.0}
        assert seen[3] == {"source.target.temperature": 300.0, "atmosphere.visibility_km": 10.0}

    def test_labels_passed_to_evaluate(self) -> None:
        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            return {"tag": hash(labels["target"] + labels["atmosphere"]) * 0.0}

        result = BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)
        assert result.rows[0]["target"] == "tank"
        assert result.rows[0]["atmosphere"] == "clear"


class TestErrorCapture:
    def test_radiant_error_recorded_not_raised(self) -> None:
        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            if labels["target"] == "truck":
                raise RadiantError("chain rejected the cell")
            return {"snr": 7.0}

        result = BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)
        ok_rows = [r for r in result.rows if r.get("error") is None]
        err_rows = [r for r in result.rows if r.get("error") is not None]
        assert len(ok_rows) == 2 and len(err_rows) == 2
        assert "chain rejected" in err_rows[0]["error"]
        assert result.n_failed == 2

    def test_non_radiant_error_propagates(self) -> None:
        """Programming errors must not be swallowed (Rule 17)."""

        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            raise TypeError("bug in evaluate")

        with pytest.raises(TypeError, match="bug in evaluate"):
            BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)


class TestValidation:
    def test_empty_axes_raises(self) -> None:
        with pytest.raises(BatchRunnerError, match="at least one axis"):
            BatchRunner(BASE, [], sensor_factory=fake_factory)

    def test_empty_axis_labels_raises(self) -> None:
        with pytest.raises(BatchRunnerError, match="no labels"):
            BatchRunner(BASE, [("target", {})], sensor_factory=fake_factory)

    def test_duplicate_axis_name_raises(self) -> None:
        axes: list[tuple[str, dict[str, dict[str, object]]]] = [
            ("a", {"x": {}}),
            ("a", {"y": {}}),
        ]
        with pytest.raises(BatchRunnerError, match="duplicate"):
            BatchRunner(BASE, axes, sensor_factory=fake_factory)

    def test_reserved_column_name_raises(self) -> None:
        with pytest.raises(BatchRunnerError, match="reserved"):
            BatchRunner(BASE, [("error", {"x": {}})], sensor_factory=fake_factory)


class TestPivot:
    def test_pivot_table(self) -> None:
        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            return {"snr": 10.0 if labels["atmosphere"] == "clear" else 3.0}

        result = BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)
        table = result.pivot("snr", rows="target", cols="atmosphere")
        assert table["tank"]["clear"] == pytest.approx(10.0, rel=1e-12)
        assert table["truck"]["haze"] == pytest.approx(3.0, rel=1e-12)

    def test_pivot_error_cells_are_none(self) -> None:
        def evaluate(sensor: FakeSensor, labels: dict[str, str]) -> dict[str, float]:
            if labels["target"] == "tank":
                raise RadiantError("nope")
            return {"snr": 5.0}

        result = BatchRunner(BASE, AXES, sensor_factory=fake_factory).run(evaluate)
        table = result.pivot("snr", rows="target", cols="atmosphere")
        assert table["tank"]["clear"] is None
        assert table["truck"]["clear"] == pytest.approx(5.0, rel=1e-12)


class TestBatchResult:
    def test_result_is_immutable_dataclass(self) -> None:
        result = BatchResult(axes=(("a", ("x",)),), rows=({"a": "x", "error": None},))
        with pytest.raises(AttributeError):
            result.rows = ()  # type: ignore[misc]
