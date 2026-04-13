"""Tests for OpticsStage wrapper."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.optics.stage import OpticsStage

from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS


def _make_state(wl: np.ndarray) -> ChainState:
    state = ChainState(wavelength_um=wl)
    L = np.ones_like(wl) * 2.0  # W/m²/sr/µm
    frame = RadiometricFrame(
        name="at_aperture", wavelength_um=wl, spectral_radiance=L,
    )
    return state.with_frame(frame)


def _make_params(
    D: float = 0.30,
    f: float = 1.20,
    tau: float = 0.70,
    pitch: float = 18.0,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.aperture_diameter_m", D)
    ps.set("optics.focal_length_m", f)
    ps.set("optics.transmission_scalar", tau)
    ps.set("detector.pixel_pitch_x_um", pitch)
    ps.set("detector.pixel_pitch_y_um", pitch)
    ps.set("detector.qe_value", 0.7)
    ps.resolve()
    return ps


class TestOpticsStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def test_produces_post_optics_frame(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        out = OpticsStage().run(state, _make_params())
        assert "post_optics" in out.frames

    def test_throughput_applied(self, wl: np.ndarray) -> None:
        state = _make_state(wl)
        tau = 0.70
        out = OpticsStage().run(state, _make_params(tau=tau))
        L_in = state.frames["at_aperture"].spectral_radiance
        L_out = out.frames["post_optics"].spectral_radiance
        assert L_in is not None and L_out is not None
        np.testing.assert_allclose(L_out, L_in * tau, rtol=1e-12)

    def test_A_collect(self, wl: np.ndarray) -> None:
        D = 0.30
        out = OpticsStage().run(_make_state(wl), _make_params(D=D))
        A = out.stage_outputs["optics"]["A_collect"]
        expected = math.pi / 4.0 * D ** 2
        assert A == pytest.approx(expected, rel=1e-10)

    def test_Omega_pixel(self, wl: np.ndarray) -> None:
        pitch_m = 18e-6  # input is µm, schema converts to m
        f = 1.20
        out = OpticsStage().run(_make_state(wl), _make_params(f=f, pitch=18.0))
        omega = out.stage_outputs["optics"]["Omega_pixel"]
        expected = (pitch_m ** 2) / (f ** 2)
        assert omega == pytest.approx(expected, rel=1e-10)

    def test_EE_box_stubbed(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        assert out.stage_outputs["optics"]["EE_box"] == 1.0

    def test_regime_stubbed_extended(self, wl: np.ndarray) -> None:
        out = OpticsStage().run(_make_state(wl), _make_params())
        assert out.stage_outputs["optics"]["regime"] == RadiometricRegime.EXTENDED

    def test_name(self) -> None:
        assert OpticsStage().name == "optics"
