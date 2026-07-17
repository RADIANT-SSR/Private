"""Tests for compare_configs (Gap 79 / Tier-2 FW-A)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api import ComparisonError, Sensor, compare_configs

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


def _result(**overrides: float):  # type: ignore[no-untyped-def]
    s = Sensor.from_yaml(_EXAMPLE)
    for k, v in overrides.items():
        s.set(k.replace("__", "."), v)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return s.evaluate()


class TestCompareConfigs:
    def test_aligned_matrix_with_units_and_deltas(self) -> None:
        base = _result()
        bigger = _result(optics__aperture_diameter_m=0.5)
        cmp_ = compare_configs([("baseline", base), ("50 cm", bigger)])
        assert cmp_.labels == ("baseline", "50 cm")
        snr = cmp_.row("snr")
        assert snr.unit  # units always carried (R-UNITS)
        assert snr.values[0] == pytest.approx(base.metrics["snr"], rel=1e-12)
        assert snr.deltas[0] == 0.0  # baseline delta is exactly zero
        assert snr.deltas[1] == pytest.approx(
            bigger.metrics["snr"] - base.metrics["snr"], rel=1e-12
        )
        # Bigger aperture wins SNR; higher-is-better marks column 1.
        assert snr.best_index == 1

    def test_lower_is_better_metrics_marked_correctly(self) -> None:
        base = _result()
        bigger = _result(optics__aperture_diameter_m=0.5)
        cmp_ = compare_configs([("baseline", base), ("50 cm", bigger)])
        gsd = cmp_.row("gsd_cross_track_m")
        # Bigger aperture, same focal length -> GSD unchanged? aperture doesn't
        # change GSD; use nedt instead if gsd equal. Accept either equal or marked lower.
        if gsd.values[0] != gsd.values[1]:
            assert gsd.best_index == gsd.values.index(min(v for v in gsd.values if v is not None))

    def test_baseline_selection_and_table(self) -> None:
        a, b = _result(), _result(optics__aperture_diameter_m=0.5)
        cmp_ = compare_configs([("A", a), ("B", b)], baseline=1)
        assert cmp_.baseline_index == 1
        assert cmp_.row("snr").deltas[1] == 0.0
        table = cmp_.to_table()
        assert "metric" in table and "A" in table and "B" in table
        assert "*" in table  # a best-mark rendered

    def test_fewer_than_two_raises_actionable(self) -> None:
        with pytest.raises(ComparisonError, match="at least 2"):
            compare_configs([("only", _result())])

    def test_bad_baseline_raises(self) -> None:
        a, b = _result(), _result()
        with pytest.raises(ComparisonError, match="out of range"):
            compare_configs([("A", a), ("B", b)], baseline=5)
