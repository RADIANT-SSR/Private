"""Tests for pre-chain atmosphere model construction (Rule 6).

Level 0: build_atmosphere_model dispatch and validation.
Level 1: AtmosphereStage consumes the injected model and refuses to
build file-backed models inside run().
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.loaders import FILE_BACKED_MODELS, build_atmosphere_model
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet


def _make_params(model: str) -> ParameterSet:
    from radiant.atmosphere._schema import ALL_PARAMETERS as ATM_PARAMS

    ps = ParameterSet(list(ATM_PARAMS), [])
    ps.set("atmosphere.model", model)
    ps.set("geometry.sensor_altitude_m", 500e3)
    ps.resolve()
    return ps


class TestBuildAtmosphereModel:
    @pytest.mark.level0
    def test_exo(self) -> None:
        model = build_atmosphere_model(_make_params("exo"))
        assert isinstance(model, ExoAtmosphere)

    @pytest.mark.level0
    def test_simple_default(self) -> None:
        model = build_atmosphere_model(_make_params("simple"))
        assert isinstance(model, SimpleAtmosphere)

    @pytest.mark.level0
    def test_tabulated_without_files_raises(self) -> None:
        with pytest.raises(ValueError, match="tabulated_transmittance_file"):
            build_atmosphere_model(_make_params("tabulated"))

    @pytest.mark.level0
    def test_interpolated_without_dir_raises(self) -> None:
        with pytest.raises(ValueError, match="interpolated_data_dir"):
            build_atmosphere_model(_make_params("interpolated"))

    @pytest.mark.level0
    def test_file_backed_registry(self) -> None:
        assert frozenset({"tabulated", "interpolated"}) == FILE_BACKED_MODELS


class TestStageModelInjection:
    @pytest.mark.level1
    def test_file_backed_model_without_injection_raises(self) -> None:
        """Rule 6: the stage must not read files inside run()."""
        wl = np.linspace(3.0, 5.0, 20)
        state = ChainState(wavelength_um=wl)
        with pytest.raises(ValueError, match="Rule 6"):
            AtmosphereStage().run(state, _make_params("tabulated"))

    @pytest.mark.level1
    def test_injected_model_takes_precedence(self) -> None:
        """An injected model is used even when params say 'tabulated'."""

        class _SentinelModel:
            def evaluate(self, wl: object, los: object, params: object) -> object:
                raise _SentinelReached

        class _SentinelReached(Exception):
            pass

        wl = np.linspace(3.0, 5.0, 20)
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("atmosphere_config", "model", _SentinelModel())
        # Missing source descriptors error occurs after model resolution;
        # reaching it proves the injected model bypassed the Rule 6 guard.
        with pytest.raises(ValueError, match="SourceStage"):
            AtmosphereStage().run(state, _make_params("tabulated"))
