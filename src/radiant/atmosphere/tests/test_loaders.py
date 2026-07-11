"""Tests for pre-chain atmosphere model construction (Rule 6).

Level 0: build_atmosphere_model dispatch and validation.
Level 1: AtmosphereStage consumes the injected model and refuses to
build file-backed models inside run().
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.loaders import (
    FILE_BACKED_MODELS,
    build_atmosphere_model,
    model_requires_prebuild,
)
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet


def _make_params(model: str, **extra: object) -> ParameterSet:
    from radiant.atmosphere._schema import ALL_PARAMETERS as ATM_PARAMS

    ps = ParameterSet(list(ATM_PARAMS), [])
    ps.set("atmosphere.model", model)
    ps.set("geometry.sensor_altitude_m", 500e3)
    for dotpath, value in extra.items():
        ps.set(dotpath.replace("__", "."), value)
    ps.resolve()
    return ps


def _write_named_header_tape7(path: Path, n_points: int = 20) -> None:
    """Minimal tape7 with a named column header (no CU-066 fallback warning)."""
    nu = np.linspace(5000, 2000, n_points)
    header = (
        "   FREQ   TOT TRANS   PTH THRML   THRML SCT   SURF EMIS   "
        "SOL SCAT   SNGL SCAT   GRND RFLT   DRCT RFLT   TOTAL RAD"
    )
    lines = [header]
    for i in range(n_points):
        lines.append(
            f"{nu[i]:12.2f}{0.75:12.6f}{1.0e-6:12.4e}{0.0:12.4e}{0.0:12.4e}"
            f"{2.0e-6:12.4e}{0.0:12.4e}{0.0:12.4e}{0.0:12.4e}{3.0e-6:12.4e}"
        )
    path.write_text("\n".join(lines))


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

    @pytest.mark.level0
    def test_modtran_without_tape7_path_has_no_import(self) -> None:
        model = build_atmosphere_model(_make_params("modtran"))
        assert model._tape7_import is None  # type: ignore[attr-defined]

    @pytest.mark.level0
    def test_modtran_tape7_path_builds_import(self, tmp_path: Path) -> None:
        tape7 = tmp_path / "run.tp7"
        _write_named_header_tape7(tape7)
        model = build_atmosphere_model(
            _make_params("modtran", atmosphere__modtran__tape7_path=str(tape7))
        )
        imp = model._tape7_import  # type: ignore[attr-defined]
        assert imp is not None
        assert imp.source_path == str(tape7)
        assert imp.wavelength_um[0] < imp.wavelength_um[-1]  # ascending µm

    @pytest.mark.level0
    def test_modtran_tape7_path_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="tape7_path"):
            build_atmosphere_model(
                _make_params(
                    "modtran",
                    atmosphere__modtran__tape7_path=str(tmp_path / "missing.tp7"),
                )
            )

    @pytest.mark.level0
    def test_modtran_tape7_sun_path_builds_both_imports(self, tmp_path: Path) -> None:
        main = tmp_path / "up.tp7"
        sun = tmp_path / "sun.tp7"
        _write_named_header_tape7(main)
        _write_named_header_tape7(sun)
        model = build_atmosphere_model(
            _make_params(
                "modtran",
                atmosphere__modtran__tape7_path=str(main),
                atmosphere__modtran__tape7_sun_path=str(sun),
            )
        )
        assert model._tape7_import is not None  # type: ignore[attr-defined]
        assert model._tape7_sun_import is not None  # type: ignore[attr-defined]
        assert model._tape7_sun_import.source_path == str(sun)  # type: ignore[attr-defined]

    @pytest.mark.level0
    def test_modtran_sun_path_without_main_raises(self, tmp_path: Path) -> None:
        sun = tmp_path / "sun.tp7"
        _write_named_header_tape7(sun)
        with pytest.raises(ValueError, match="tape7_sun_path"):
            build_atmosphere_model(
                _make_params("modtran", atmosphere__modtran__tape7_sun_path=str(sun))
            )

    @pytest.mark.level0
    def test_modtran_sun_path_missing_file_raises(self, tmp_path: Path) -> None:
        main = tmp_path / "up.tp7"
        _write_named_header_tape7(main)
        with pytest.raises(FileNotFoundError, match="tape7_sun_path"):
            build_atmosphere_model(
                _make_params(
                    "modtran",
                    atmosphere__modtran__tape7_path=str(main),
                    atmosphere__modtran__tape7_sun_path=str(tmp_path / "missing.tp7"),
                )
            )

    @pytest.mark.level0
    def test_model_requires_prebuild(self, tmp_path: Path) -> None:
        assert model_requires_prebuild(_make_params("tabulated"))
        assert model_requires_prebuild(_make_params("interpolated"))
        assert not model_requires_prebuild(_make_params("simple"))
        assert not model_requires_prebuild(_make_params("exo"))
        assert not model_requires_prebuild(_make_params("modtran"))
        tape7 = tmp_path / "run.tp7"
        _write_named_header_tape7(tape7)
        assert model_requires_prebuild(
            _make_params("modtran", atmosphere__modtran__tape7_path=str(tape7))
        )


class TestStageModelInjection:
    @pytest.mark.level1
    def test_file_backed_model_without_injection_raises(self) -> None:
        """Rule 6: the stage must not read files inside run()."""
        wl = np.linspace(3.0, 5.0, 20)
        state = ChainState(wavelength_um=wl)
        with pytest.raises(ValueError, match="Rule 6"):
            AtmosphereStage().run(state, _make_params("tabulated"))

    @pytest.mark.level1
    def test_modtran_with_tape7_path_without_injection_raises(self, tmp_path: Path) -> None:
        """Rule 6: modtran-with-tape7_path is file-backed — no inline build."""
        tape7 = tmp_path / "run.tp7"
        _write_named_header_tape7(tape7)
        wl = np.linspace(3.0, 5.0, 20)
        state = ChainState(wavelength_um=wl)
        with pytest.raises(ValueError, match="Rule 6"):
            AtmosphereStage().run(
                state,
                _make_params("modtran", atmosphere__modtran__tape7_path=str(tape7)),
            )

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
