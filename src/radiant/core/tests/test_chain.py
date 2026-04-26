"""Tests for radiant.core.chain — Stage, ChainState, ChainRunner.

All tests are Level 1: module-level state-machine and ChainRunner orchestration
contracts (compose ChainState with RadiometricFrame, NoiseTerm, and dummy stages).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainRunner, ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import NoiseTerm, RadiometricFrame

# ---------------------------------------------------------------------------
# ChainState
# ---------------------------------------------------------------------------


class TestChainState:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.0, 5.0, 50)

    @pytest.mark.level1
    def test_initial_state(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        assert len(state.frames) == 0
        assert len(state.stage_outputs) == 0
        assert len(state.noise_terms) == 0
        assert state.history == ()

    @pytest.mark.level1
    def test_mutation_of_frames_raises_typeerror(self, wl: np.ndarray) -> None:
        """Design decision 1: direct mutation must raise TypeError."""
        state = ChainState(wavelength_um=wl)
        with pytest.raises(TypeError):
            state.frames["hack"] = "nope"  # type: ignore[index]

    @pytest.mark.level1
    def test_mutation_of_stage_outputs_raises(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("source", "key", "val")
        with pytest.raises(TypeError):
            state.stage_outputs["source"]["new"] = "nope"  # type: ignore[index]

    @pytest.mark.level1
    def test_mutation_of_metrics_raises(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        with pytest.raises(TypeError):
            state.metrics["hack"] = 42.0  # type: ignore[index]

    @pytest.mark.level1
    def test_mutation_of_mtf_terms_raises(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        with pytest.raises(TypeError):
            state.mtf_terms["hack"] = np.ones(10)  # type: ignore[index]

    @pytest.mark.level1
    def test_with_frame(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        frame = RadiometricFrame(
            name="at_target",
            wavelength_um=wl,
            spectral_radiance=np.ones_like(wl),
        )
        new = state.with_frame(frame)
        assert "at_target" in new.frames
        assert "at_target" not in state.frames  # original unchanged

    @pytest.mark.level1
    def test_with_stage_output(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        new = state.with_stage_output("source", "regime", "extended")
        assert new.stage_outputs["source"]["regime"] == "extended"

    @pytest.mark.level1
    def test_with_noise(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        nt = NoiseTerm(
            name="shot",
            value_e=10.0,
            origin_frame="pe",
            physical_basis="Poisson",
        )
        new = state.with_noise(nt)
        assert len(new.noise_terms) == 1
        assert new.noise_terms[0].name == "shot"

    @pytest.mark.level1
    def test_with_history(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        new = state.with_history("source").with_history("atmosphere")
        assert new.history == ("source", "atmosphere")

    @pytest.mark.level1
    def test_with_metric(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        new = state.with_metric("snr", 47.3)
        assert new.metrics["snr"] == pytest.approx(47.3, rel=1e-12)


# ---------------------------------------------------------------------------
# ChainRunner
# ---------------------------------------------------------------------------


class _DummyStage:
    """Minimal stage that writes a frame and a stage output."""

    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    @property
    def name(self) -> str:
        return self._name

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        frame = RadiometricFrame(
            name=f"frame_{self._name}",
            wavelength_um=state.wavelength_um,
            spectral_radiance=np.ones_like(state.wavelength_um),
        )
        return state.with_frame(frame).with_stage_output(self._name, "done", True)


class TestChainRunner:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.0, 5.0, 10)

    @pytest.fixture()
    def empty_params(self) -> ParameterSet:
        ps = ParameterSet([])
        ps.resolve()
        return ps

    @pytest.mark.level1
    def test_duplicate_names_raises(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            ChainRunner([_DummyStage("a"), _DummyStage("a")])

    @pytest.mark.level1
    def test_runs_stages_in_order(
        self,
        wl: np.ndarray,
        empty_params: ParameterSet,
    ) -> None:
        runner = ChainRunner([_DummyStage("first"), _DummyStage("second")])
        state = runner.run(empty_params, wl)
        assert state.history == ("first", "second")
        assert "frame_first" in state.frames
        assert "frame_second" in state.frames

    @pytest.mark.level1
    def test_auto_records_history(
        self,
        wl: np.ndarray,
        empty_params: ParameterSet,
    ) -> None:
        runner = ChainRunner([_DummyStage("x")])
        state = runner.run(empty_params, wl)
        assert state.history[-1] == "x"

    @pytest.mark.level1
    def test_stage_names_property(self) -> None:
        runner = ChainRunner([_DummyStage("a"), _DummyStage("b")])
        assert runner.stage_names == ("a", "b")
