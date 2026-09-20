"""Level 0: the filter band edges are checked before any stage runs (CU-373 F-21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.errors import SpectralBandError
from radiant.api.sensor import Sensor

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.mark.level0
def test_inverted_band_raises_a_structured_band_error() -> None:
    sensor = Sensor.load(_EXAMPLE)
    sensor.set("spectral_integration.filter_min_um", 8.0)  # max is 5.0
    with pytest.raises(SpectralBandError) as info:
        sensor.evaluate()
    exc = info.value
    assert "filter_min_um (8 µm)" in exc.what and "filter_max_um (5 µm)" in exc.what
    assert exc.context == {"filter_min_um": 8.0, "filter_max_um": 5.0}
    assert "strictly ascending" not in str(exc)
    assert "emissivity" not in str(exc)


@pytest.mark.level0
def test_empty_band_raises_too() -> None:
    sensor = Sensor.load(_EXAMPLE)
    sensor.set("spectral_integration.filter_min_um", 5.0)
    with pytest.raises(SpectralBandError):
        sensor.evaluate()


@pytest.mark.level0
def test_band_error_is_a_value_error_for_back_compat() -> None:
    with pytest.raises(ValueError, match="filter_min_um"):
        raise SpectralBandError(what="filter_min_um x", why="y", action="z")
