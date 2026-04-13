"""Tests for DetectorStage — electron counts and raw noise budget.

DetectorStage no longer emits NoiseTerm objects. It stores all
per-pixel electron counts and the raw NoiseBudget in
``stage_outputs["detector"]``. ReadoutStage is the sole NoiseTerm emitter.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.detector.noise import NoiseBudget
from radiant.detector.stage import DetectorStage
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS


def _make_state(
    wl: np.ndarray,
    signal_e: float = 10000.0,
    background_e: float = 0.0,
    nearfield_e: float = 0.0,
    stray_e: float = 0.0,
) -> ChainState:
    """Build a ChainState with spectral_integration outputs pre-loaded."""
    state = ChainState(wavelength_um=wl)
    frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=signal_e,
        in_band_unit="e-",
    )
    state = state.with_frame(frame)
    state = state.with_stage_output("spectral_integration", "signal_e", signal_e)
    state = state.with_stage_output("spectral_integration", "background_e", background_e)
    state = state.with_stage_output("spectral_integration", "nearfield_e", nearfield_e)
    return state.with_stage_output("spectral_integration", "stray_e", stray_e)


def _make_params(
    dark_rate: float = 100.0,
    t_int: float = 0.005,
    glow_rate: float = 0.0,
) -> ParameterSet:
    schema = list(DET_PARAMS) + list(SI_PARAMS) + list(RO_PARAMS)
    ps = ParameterSet(schema)
    ps.set("detector.qe_value", 0.7)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.dark_rate_e_per_s", dark_rate)
    ps.set("detector.glow_e_per_s", glow_rate)
    ps.set("spectral_integration.integration_time_s", t_int)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    ps.resolve()
    return ps


class TestDetectorStage:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    def test_no_noise_terms_emitted(self, wl: np.ndarray) -> None:
        """DetectorStage must NOT emit NoiseTerm objects (ReadoutStage does)."""
        state = _make_state(wl, signal_e=10000.0)
        out = DetectorStage().run(state, _make_params())
        assert len(out.noise_terms) == 0

    def test_stage_outputs_signal_e(self, wl: np.ndarray) -> None:
        signal = 10000.0
        out = DetectorStage().run(
            _make_state(wl, signal_e=signal),
            _make_params(),
        )
        assert out.stage_outputs["detector"]["signal_e"] == pytest.approx(
            signal,
            rel=1e-10,
        )

    def test_stage_outputs_dark_e(self, wl: np.ndarray) -> None:
        dark_rate = 100.0
        t_int = 0.005
        dark_e_expected = dark_rate * t_int
        out = DetectorStage().run(
            _make_state(wl),
            _make_params(dark_rate=dark_rate, t_int=t_int),
        )
        assert out.stage_outputs["detector"]["dark_e"] == pytest.approx(
            dark_e_expected,
            rel=1e-10,
        )

    def test_stage_outputs_glow_e(self, wl: np.ndarray) -> None:
        glow_rate = 50.0
        t_int = 0.01
        out = DetectorStage().run(
            _make_state(wl),
            _make_params(glow_rate=glow_rate, t_int=t_int),
        )
        assert out.stage_outputs["detector"]["glow_e"] == pytest.approx(
            glow_rate * t_int,
            rel=1e-10,
        )

    def test_noise_budget_raw_present(self, wl: np.ndarray) -> None:
        out = DetectorStage().run(_make_state(wl), _make_params())
        budget = out.stage_outputs["detector"]["noise_budget_raw"]
        assert isinstance(budget, NoiseBudget)
        assert len(budget.terms) == 16

    def test_noise_budget_signal_shot(self, wl: np.ndarray) -> None:
        signal = 10000.0
        out = DetectorStage().run(
            _make_state(wl, signal_e=signal),
            _make_params(),
        )
        budget: NoiseBudget = out.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["signal_shot"] == pytest.approx(
            math.sqrt(signal),
            rel=1e-10,
        )

    def test_noise_budget_dark_shot(self, wl: np.ndarray) -> None:
        dark_rate = 100.0
        t_int = 0.005
        dark_e = dark_rate * t_int
        out = DetectorStage().run(
            _make_state(wl),
            _make_params(dark_rate=dark_rate, t_int=t_int),
        )
        budget: NoiseBudget = out.stage_outputs["detector"]["noise_budget_raw"]
        assert budget.terms["dark_shot"] == pytest.approx(
            math.sqrt(dark_e),
            rel=1e-10,
        )

    def test_nearfield_and_stray_passthrough(self, wl: np.ndarray) -> None:
        nf, stray = 500.0, 200.0
        state = _make_state(wl, nearfield_e=nf, stray_e=stray)
        out = DetectorStage().run(state, _make_params())
        assert out.stage_outputs["detector"]["nearfield_e"] == pytest.approx(
            nf,
            rel=1e-10,
        )
        assert out.stage_outputs["detector"]["stray_e"] == pytest.approx(
            stray,
            rel=1e-10,
        )

    def test_name(self) -> None:
        assert DetectorStage().name == "detector"
