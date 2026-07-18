"""Tests for detector.qe_material — bundled QE curves from config (Gap 69, detector half)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api import Sensor
from radiant.core.parameters import ParameterBoundsError

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


def _eval(sensor: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


class TestQeMaterial:
    def test_library_curve_changes_results(self) -> None:
        base = _eval(Sensor.from_yaml(_EXAMPLE))
        s = Sensor.from_yaml(_EXAMPLE).set("detector.qe_material", "hgcdte_mwir")
        assert _eval(s).metrics["snr"] != base.metrics["snr"]

    def test_unknown_material_rejected_with_vocabulary(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE).set("detector.qe_material", "unobtainium")
        with pytest.raises(ParameterBoundsError, match="hgcdte_mwir"):
            _eval(s)

    def test_material_waives_scalar_qe_requirement(self) -> None:
        """Gap 69 ergonomics: qe_material alone satisfies the QE requirement
        (required_unless now accepts the comma list of alternatives)."""
        s = Sensor.from_yaml(_EXAMPLE)
        s.reset("detector.qe_value").set("detector.qe_material", "hgcdte_mwir")
        assert _eval(s).metrics["snr"] > 0

    def test_qe_table_path_wins_over_material(self, tmp_path: Path) -> None:
        csv = tmp_path / "flat.csv"
        csv.write_text("wavelength_um,qe\n3.0,0.5\n5.5,0.5\n", encoding="utf-8")
        s = Sensor.from_yaml(_EXAMPLE)
        s.set("detector.qe_table_path", str(csv))
        s.set("detector.qe_material", "hgcdte_mwir")
        with_both = _eval(s)
        s2 = Sensor.from_yaml(_EXAMPLE).set("detector.qe_table_path", str(csv))
        path_only = _eval(s2)
        assert with_both.metrics["snr"] == pytest.approx(path_only.metrics["snr"], rel=1e-12)

    def test_round_trips_through_save(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE).set("detector.qe_material", "hgcdte_mwir")
        first = _eval(s).metrics["snr"]
        path = tmp_path / "mat.yaml"
        s.save(path)
        assert _eval(Sensor.load(path)).metrics["snr"] == pytest.approx(first, rel=1e-12)
