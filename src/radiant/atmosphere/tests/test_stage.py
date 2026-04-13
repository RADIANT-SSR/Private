"""Tests for AtmosphereStage wrapper."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame


def _make_state(wl: np.ndarray) -> ChainState:
    """Create a ChainState with a dummy at_target frame."""
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 1.0  # 1 W/m²/sr/µm
    frame = RadiometricFrame(
        name="at_target", wavelength_um=wl, spectral_radiance=L,
    )
    return state.with_frame(frame)


def _make_params(
    sensor_alt_m: float = 8000.0,
    model: str = "simple",
) -> ParameterSet:
    ps = ParameterSet(list(ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", sensor_alt_m)
    ps.set("atmosphere.model", model)
    ps.resolve()
    return ps


class TestAtmosphereStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 100)

    def test_produces_at_aperture_frame(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_aperture" in out.frames
        L = out.frames["at_aperture"].spectral_radiance
        assert L is not None
        assert L.shape == wl.shape

    def test_tau_stashed(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = AtmosphereStage().run(state, _make_params())
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        assert tau.shape == wl.shape
        assert np.all(tau >= 0.0)
        assert np.all(tau <= 1.0)

    def test_L_path_stashed(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = AtmosphereStage().run(state, _make_params())
        lp = out.stage_outputs["atmosphere"]["L_path"]
        assert lp.shape == wl.shape
        assert np.all(np.isfinite(lp))

    def test_L_atm_down_stashed(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = AtmosphereStage().run(state, _make_params())
        ld = out.stage_outputs["atmosphere"]["L_atm_down"]
        assert ld.shape == wl.shape
        assert np.all(ld >= 0.0)

    def test_exo_model(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = AtmosphereStage().run(state, _make_params(model="exo"))
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        np.testing.assert_allclose(tau, 1.0, atol=1e-15)
        L = out.frames["at_aperture"].spectral_radiance
        L_in = state.frames["at_target"].spectral_radiance
        assert L is not None and L_in is not None
        np.testing.assert_allclose(L, L_in, atol=1e-15)

    def test_name(self) -> None:
        assert AtmosphereStage().name == "atmosphere"
