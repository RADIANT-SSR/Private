"""Tests for AtmosphereStage wrapper (Stage 4 Option C)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.descriptors import T1Thermal
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData


def _make_state_with_descriptors(
    wl: np.ndarray,
    target_T: float = 300.0,
    target_eps: float = 0.95,
) -> ChainState:
    """Create a ChainState with Option C descriptors published under ``source``.

    Stage 4 no longer reads an ``at_target`` frame — AtmosphereStage now
    consumes the ``TargetDescriptor`` / ``BackgroundDescriptor`` /
    ``LineOfSightGeometry`` triple that SourceStage publishes.
    """
    state = ChainState(wavelength_um=wl)
    epsilon = SpectralData(
        name="target.epsilon",
        wavelength_um=wl,
        values=np.full_like(wl, target_eps),
        unit="",
        source="test",
    )
    target = T1Thermal(
        T_t=target_T,
        epsilon=epsilon,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )
    los = LineOfSightGeometry(
        h_tgt=0.0,
        theta_o=0.0,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )
    state = state.with_stage_output("source", "target", target)
    state = state.with_stage_output("source", "background", None)
    state = state.with_stage_output("source", "los_geometry", los)
    return state


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
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_aperture" in out.frames
        L = out.frames["at_aperture"].spectral_radiance
        assert L is not None
        assert L.shape == wl.shape

    def test_produces_at_aperture_target_frame(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        assert "at_aperture_target" in out.frames
        L = out.frames["at_aperture_target"].spectral_radiance
        assert L is not None
        assert L.shape == wl.shape
        # Canonical at_aperture and at_aperture_target share the target
        # arm's L(λ) by construction (Stage 4 alias).
        np.testing.assert_array_equal(
            out.frames["at_aperture"].spectral_radiance,
            L,
        )

    def test_tau_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        assert tau.shape == wl.shape
        assert np.all(tau >= 0.0)
        assert np.all(tau <= 1.0)

    def test_L_path_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        lp = out.stage_outputs["atmosphere"]["L_path"]
        assert lp.shape == wl.shape
        assert np.all(np.isfinite(lp))

    def test_atm_quantities_stashed(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params())
        atm_q = out.stage_outputs["atmosphere"]["atm_quantities"]
        assert atm_q.tau_up.shape == wl.shape
        assert atm_q.L_path_up.shape == wl.shape
        assert atm_q.L_path_full.shape == wl.shape

    def test_exo_model(self, wl: np.ndarray) -> None:
        state = _make_state_with_descriptors(wl)
        out = AtmosphereStage().run(state, _make_params(model="exo"))
        tau = out.stage_outputs["atmosphere"]["tau_atm"]
        np.testing.assert_allclose(tau, 1.0, atol=1e-15)
        L = out.frames["at_aperture"].spectral_radiance
        assert L is not None
        # For exo, τ ≡ 1 and L_path ≡ 0, so the at_aperture frame is
        # identically ε·B(T_t).
        assert np.all(L >= 0.0)

    def test_name(self) -> None:
        assert AtmosphereStage().name == "atmosphere"

    def test_requires_target_descriptor(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)  # no descriptors
        with pytest.raises(ValueError, match="TargetDescriptor"):
            AtmosphereStage().run(state, _make_params())
