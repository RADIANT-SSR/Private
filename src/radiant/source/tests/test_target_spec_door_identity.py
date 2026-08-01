"""Build-identity pins for the target-spec doors (CU-293).

CU-293 moved the last inlined door-exclusivity guards out of
:mod:`radiant.source._inferrer` into :mod:`radiant.source.target_spec` and
added the missing S11-vs-S12 guard.  Every one of those edits is a *refusal*
change: a cleanly specified single-surface target must still build the exact
same descriptor, byte for byte.

These tests pin that.  Each canonical spec below drives
:func:`radiant.source._inferrer.infer_descriptors` and asserts on the
descriptor variant plus a SHA-256 of the raw ``float64`` bytes of the spectral
array the door produced.  The digests were captured on the pre-CU-293 tree, so
a change to any door's *construction* path — not just its guards — fails here.

Rule 18: written and run against the pre-change tree first (all four digests
reproduced), then the guards were moved.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import (
    T1Thermal,
    T6TabulatedAtSource,
    T7IntensityAtSource,
)
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors

_WL_MWIR = np.linspace(3.0, 5.0, 21)


def _digest(sd: SpectralData) -> str:
    """SHA-256 over the raw float64 bytes of a SpectralData's values."""
    return hashlib.sha256(np.asarray(sd.values, dtype=np.float64).tobytes()).hexdigest()


def _base_params() -> ParameterSet:
    """A minimal MWIR terrestrial-target set with every target door left unset."""
    params = build_parameter_set()
    params.set("optics.aperture_diameter_m", 0.15)  # m
    params.set("optics.focal_length_m", 0.60)  # m
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)  # m
    params.set("geometry.target_range_m", 20_000.0)  # m
    params.set("spectral_integration.filter_min_um", 3.0)  # µm
    params.set("spectral_integration.filter_max_um", 5.0)  # µm
    params.set("spectral_integration.integration_time_s", 1e-3)  # s
    params.set("detector.pixel_pitch_x_um", 5.5)  # µm
    params.set("detector.pixel_pitch_y_um", 5.5)  # µm
    params.set("detector.qe_value", 0.8)
    params.set("source.target_location", "terrestrial")
    return params


def _resolved(params: ParameterSet) -> ParameterSet:
    """``infer_descriptors`` reads resolved values, so resolve before building."""
    params.resolve()
    return params


@pytest.mark.level1
class TestSingleSurfaceDoorsBuildIdentically:
    """Each door, specified cleanly, still builds the pre-CU-293 descriptor."""

    def test_s11_scalar_brightness_temperature(self) -> None:
        params = _base_params()
        params.set("source.scene_type", "extended")
        params.set("source.target.brightness_temperature_K", 320.0)  # K
        target, _bg, _los = infer_descriptors(_resolved(params), _WL_MWIR)
        assert isinstance(target, T1Thermal)
        assert target.T_t == pytest.approx(320.0, rel=1e-15)  # K
        assert target.epsilon is not None
        assert _digest(target.epsilon) == (
            "5493ebe614439118bbb8c5c03747c72e3c5dd4a398ed9794eca9d35684c7eb3d"
        )

    def test_s12_radiance_temperature(self) -> None:
        params = _base_params()
        params.set("source.scene_type", "extended")
        params.set("source.target.radiance_temperature_K", 300.0)  # K
        params.set("source.target.radiance_temperature_band_lo_um", 3.0)  # µm
        params.set("source.target.radiance_temperature_band_hi_um", 5.0)  # µm
        target, _bg, _los = infer_descriptors(_resolved(params), _WL_MWIR)
        assert isinstance(target, T1Thermal)
        assert target.T_t == pytest.approx(300.0, rel=1e-15)  # K
        assert target.epsilon is not None
        assert _digest(target.epsilon) == (
            "5493ebe614439118bbb8c5c03747c72e3c5dd4a398ed9794eca9d35684c7eb3d"
        )

    def test_s8_user_radiance_path(self, tmp_path: Path) -> None:
        csv = tmp_path / "L_source.csv"
        csv.write_text(
            "wavelength_um,L_W_per_m2_per_sr_per_um\n3.0,4.0\n5.0,6.0\n",
            encoding="utf-8",
        )
        params = _base_params()
        params.set("source.scene_type", "extended")
        params.set("source.target.user_radiance_path", str(csv))
        target, _bg, _los = infer_descriptors(_resolved(params), _WL_MWIR)
        assert isinstance(target, T6TabulatedAtSource)
        assert target.L_t_source is not None
        assert _digest(target.L_t_source) == (
            "c7964915ee6575ae9099a252d472b233a0ddf90c2ecf3a7cf57b14d1d3a9217d"
        )

    def test_s10b_point_intensity_blackbody(self) -> None:
        params = _base_params()
        params.set("source.scene_type", "point_source")
        params.set("source.target.point_intensity_temperature_K", 500.0)  # K
        params.set("source.target.point_intensity_area_m2", 0.36)  # m²
        params.set("source.target.point_intensity_emissivity", 0.9)
        target, _bg, _los = infer_descriptors(_resolved(params), _WL_MWIR)
        assert isinstance(target, T7IntensityAtSource)
        assert target.I_t_source is not None
        assert _digest(target.I_t_source) == (
            "010546f6584b6c074d0e1fc6c6abe686d8c57bf2314f7fbabea28ce4b1ecaf02"
        )
