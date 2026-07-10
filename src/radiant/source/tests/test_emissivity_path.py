"""Tests for source.target.emissivity_path — spectral thermal ε(λ) (Gap 47).

Setting emissivity_path builds the thermal descriptor with a spectral ε(λ)
(ε(λ)·B(λ,T)) instead of a grey scalar. It is mutually exclusive with the
scalar-ε / reflective / radiance / brightness-temperature surfaces, and the
default (no path) is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.parameters import ParameterBoundsError
from radiant.source._inferrer import _load_emissivity_on_grid


def _write_eps(path: Path, pairs: list[tuple[float, float]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("wavelength_um,emissivity\n")
        for wl, e in pairs:
            fh.write(f"{wl},{e}\n")


def _populate_required(p: object) -> None:
    """Minimum fields to satisfy ParameterSet.resolve() (mirrors inferrer tests)."""
    p.set("optics.aperture_diameter_m", 0.15)
    p.set("optics.focal_length_m", 0.60)
    p.set("atmosphere.model", "simple")
    p.set("geometry.sensor_altitude_m", 500.0)
    p.set("spectral_integration.filter_min_um", 8.0)
    p.set("spectral_integration.filter_max_um", 12.0)
    p.set("spectral_integration.integration_time_s", 1e-3)
    p.set("detector.pixel_pitch_x_um", 25.0)
    p.set("detector.pixel_pitch_y_um", 25.0)
    p.set("detector.qe_value", 0.7)
    p.set("source.target.temperature", 300.0)


def _params(**overrides: object):
    p = build_parameter_set()
    _populate_required(p)
    for k, v in overrides.items():
        p.set(k.replace("__", "."), v)
    p.resolve()
    return p


class TestLoadEmissivity:
    def test_none_when_unset(self) -> None:
        assert _load_emissivity_on_grid(_params(), np.linspace(8.0, 12.0, 50)) is None

    def test_spectral_curve_loaded_and_resampled(self, tmp_path: Path) -> None:
        csv = tmp_path / "eps.csv"
        _write_eps(csv, [(7.0, 0.60), (10.0, 0.80), (13.0, 0.95)])
        grid = np.linspace(8.0, 12.0, 60)
        eps = _load_emissivity_on_grid(_params(**{"source.target.emissivity_path": str(csv)}), grid)
        assert eps is not None
        assert eps.values.shape == grid.shape
        # genuinely spectral (monotone ramp), all in [0, 1]
        assert not np.allclose(eps.values, eps.values[0])
        assert eps.values.min() >= 0.0 and eps.values.max() <= 1.0
        assert eps.values[-1] > eps.values[0]

    def test_out_of_range_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "bad.csv"
        _write_eps(csv, [(8.0, 0.5), (12.0, 1.4)])  # ε > 1
        with pytest.raises(ParameterBoundsError, match="emissivity"):
            _load_emissivity_on_grid(
                _params(**{"source.target.emissivity_path": str(csv)}),
                np.linspace(8.0, 12.0, 40),
            )


class TestMutualExclusivity:
    @pytest.mark.parametrize(
        "conflict",
        [
            "source.target.reflectance_path",
            "source.target.brightness_temperature_K",
            "source.target.user_radiance_path",
        ],
    )
    def test_conflicts_raise(self, tmp_path: Path, conflict: str) -> None:
        csv = tmp_path / "eps.csv"
        _write_eps(csv, [(8.0, 0.8), (12.0, 0.9)])
        val: object = 300.0 if conflict.endswith("_K") else str(csv)
        p = build_parameter_set()
        _populate_required(p)
        p.set("source.target.emissivity_path", str(csv))
        p.set(conflict, val)
        p.resolve()
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            _load_emissivity_on_grid(p, np.linspace(8.0, 12.0, 40))

    def test_scalar_emissivity_conflict(self, tmp_path: Path) -> None:
        csv = tmp_path / "eps.csv"
        _write_eps(csv, [(8.0, 0.8), (12.0, 0.9)])
        p = build_parameter_set()
        _populate_required(p)
        p.set("source.target.emissivity_path", str(csv))
        p.set("source.target.emissivity", 0.9)
        p.resolve()
        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            _load_emissivity_on_grid(p, np.linspace(8.0, 12.0, 40))
