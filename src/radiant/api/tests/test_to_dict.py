"""Level 0: ``Sensor.to_dict`` is the inverse of ``from_dict`` (CU-375 F-24)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.mark.level0
def test_from_dict_of_to_dict_reproduces_the_inputs() -> None:
    sensor = Sensor.load(_EXAMPLE).set("detector.qe_value", 0.62)
    data = sensor.to_dict()
    assert data["detector"]["qe_value"] == 0.62
    assert data["_radiant"]["wavelength_points"] == sensor.wavelength_points
    twin = Sensor.from_dict(data, wavelength_points=sensor.wavelength_points)
    assert dict(twin.inputs()) == dict(sensor.inputs())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert twin.evaluate().metrics["snr"] == pytest.approx(
            sensor.evaluate().metrics["snr"], rel=1e-12
        )


@pytest.mark.level0
def test_to_dict_of_a_blank_sensor_is_meta_only() -> None:
    data = Sensor().to_dict()
    assert set(data) == {"_radiant"}
