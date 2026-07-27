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
    from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

    ps = ParameterSet(list(GEO_PARAMS + ATM_PARAMS), [])
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
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_flux_csv(path: Path, n_freq: int = 6) -> None:
    """Minimal MODTRAN 6 flux CSV (one 0 km level: UP/DOWN/SOLAR triple)."""
    nu = np.linspace(5000.0, 2000.0, n_freq)
    lines = [
        "case index 0 = {",
        f"num freq, {n_freq}",
        "num column, 3",
        "Freq, UP, DOWN, SOLAR",
        "[cm-1], 0 KM, 0 KM, 0 KM",
    ]
    for f in nu:
        lines.append(f"{f:g}, 1.0e-4, 2.0e-4, 3.0e-4")
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")


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
    def test_interpolated_without_dir_defaults_to_shipped_fan(self) -> None:
        """Unset data dir + default axes → the shipped us_standard_zenith_fan
        family loads (owner request 2026-07-18: interpolated works out of the box)."""
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "us_standard_zenith_fan").exists():
            pytest.skip("shipped atmosphere library not present")
        model = build_atmosphere_model(_make_params("interpolated"))
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.axes == ["path_zenith_rad"]

    @pytest.mark.level0
    def test_interpolated_without_dir_defaults_to_shipped_ladders(self) -> None:
        """Unset data dir + the sensor×target axes → the midlat_summer_ladders family."""
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "midlat_summer_ladders").exists():
            pytest.skip("shipped atmosphere library not present")
        model = build_atmosphere_model(
            _make_params(
                "interpolated",
                atmosphere__interpolation_axes="sensor_altitude_m,target_altitude_m",
            )
        )
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.axes == ["sensor_altitude_m", "target_altitude_m"]

    def test_interpolated_without_dir_defaults_to_sensor_ladder(self) -> None:
        """Unset data dir + the sensor-altitude axis → the boost-expansion
        midlat_summer_sensor_ladder family (plan §4.7)."""
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "midlat_summer_sensor_ladder").exists():
            pytest.skip("shipped sensor-ladder family not present")
        model = build_atmosphere_model(
            _make_params("interpolated", atmosphere__interpolation_axes="sensor_altitude_m")
        )
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.axes == ["sensor_altitude_m"]

    def test_interpolated_without_dir_defaults_to_boost_offnadir(self) -> None:
        """Unset data dir + the sensor×target×zenith axes → the
        midlat_summer_boost_offnadir family (plan §4.7)."""
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "midlat_summer_boost_offnadir").exists():
            pytest.skip("shipped off-nadir family not present")
        model = build_atmosphere_model(
            _make_params(
                "interpolated",
                atmosphere__interpolation_axes=(
                    "sensor_altitude_m,target_altitude_m,path_zenith_rad"
                ),
            )
        )
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.axes == ["sensor_altitude_m", "target_altitude_m", "path_zenith_rad"]

    @pytest.mark.level0
    def test_interpolated_without_dir_and_uncovered_axes_raises(self) -> None:
        """No shipped family covers the axes → the actionable error still fires."""
        with pytest.raises(ValueError, match="interpolated_data_dir"):
            build_atmosphere_model(
                _make_params("interpolated", atmosphere__interpolation_axes="solar_zenith_rad")
            )


class TestDirectionAwareFamilyDispatch:
    """GF-10: the shipped-family key is (LOS direction, axes), not axes alone."""

    @pytest.mark.level0
    def test_uplooking_scene_resolves_the_uplooking_ladder(self) -> None:
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "midlat_summer_uplooking_ladder").exists():
            pytest.skip("shipped up-looking family not present")
        model = build_atmosphere_model(
            _make_params(
                "interpolated",
                atmosphere__interpolation_axes="target_altitude_m",
                geometry__sensor_altitude_m=0.0,
                geometry__target_altitude_m=10_000.0,
            )
        )
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.family_direction == "up"
        assert model.axes == ["target_altitude_m"]
        assert model.coordinate_bounds()["target_altitude_m"] == (0.0, 20_000.0)

    @pytest.mark.level0
    def test_downlooking_scene_with_the_uplooking_axes_is_refused(self) -> None:
        """The axes string alone must not reach the up-looking family."""
        with pytest.raises(ValueError, match="down-looking scene"):
            build_atmosphere_model(
                _make_params(
                    "interpolated",
                    atmosphere__interpolation_axes="target_altitude_m",
                    geometry__sensor_altitude_m=500e3,
                    geometry__target_altitude_m=0.0,
                )
            )

    @pytest.mark.level0
    def test_uplooking_scene_with_an_unshipped_axes_names_what_is_shipped(self) -> None:
        with pytest.raises(ValueError) as exc:
            build_atmosphere_model(
                _make_params(
                    "interpolated",
                    atmosphere__interpolation_axes="path_zenith_rad",
                    geometry__sensor_altitude_m=0.0,
                    geometry__target_altitude_m=10_000.0,
                )
            )
        message = str(exc.value)
        assert "up-looking scene" in message
        # Every shipped (direction, axes) row is named, both directions.
        assert "down-looking axes='path_zenith_rad' → us_standard_zenith_fan" in message
        assert "up-looking axes='target_altitude_m' → midlat_summer_uplooking_ladder" in message

    @pytest.mark.level0
    def test_level_scene_has_no_shipped_family(self) -> None:
        """Constant-altitude paths are served by the simple backend's level arm."""
        with pytest.raises(ValueError, match="level-looking scene"):
            build_atmosphere_model(
                _make_params(
                    "interpolated",
                    atmosphere__interpolation_axes="target_altitude_m",
                    geometry__sensor_altitude_m=5_000.0,
                    geometry__target_altitude_m=5_000.0,
                )
            )

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("h_sensor", "h_tgt"),
        [
            (500e3, 0.0),
            (10_000.0, 3_000.0),
            (0.0, 1.0),
            (0.0, 20_000.0),
            (5_000.0, 5_000.0),
            (0.0, 0.0),
        ],
    )
    def test_direction_matches_line_of_sight_geometry(self, h_sensor: float, h_tgt: float) -> None:
        """Pin the loader's pre-chain direction rule to the LOS authority.

        ``_scene_los_direction`` must reproduce
        ``LineOfSightGeometry.los_direction`` exactly — the rule is evaluated
        in two places (pre-chain from params, in-chain from the LOS) and this
        test is what stops the two copies drifting.
        """
        import math

        from radiant.atmosphere.loaders import _scene_los_direction
        from radiant.core.los_geometry import LineOfSightGeometry

        params = _make_params(
            "simple",
            geometry__sensor_altitude_m=h_sensor,
            geometry__target_altitude_m=h_tgt,
        )
        # theta_o is irrelevant to the direction derivation, but must satisfy
        # the LOS invariant h_sensor > h_tgt ⟺ theta_o < π/2.
        if h_sensor > h_tgt:
            theta_o = 0.0
        elif h_sensor < h_tgt:
            theta_o = math.pi
        else:
            theta_o = math.pi / 2.0
        los = LineOfSightGeometry(theta_o=theta_o, h_tgt=h_tgt, h_sensor=h_sensor)
        assert _scene_los_direction(params) == los.los_direction

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
    def test_modtran_tape7_up_path_builds_both_imports(self, tmp_path: Path) -> None:
        full = tmp_path / "full.tp7"
        up = tmp_path / "up.tp7"
        _write_named_header_tape7(full)
        _write_named_header_tape7(up)
        model = build_atmosphere_model(
            _make_params(
                "modtran",
                atmosphere__modtran__tape7_path=str(full),
                atmosphere__modtran__tape7_up_path=str(up),
            )
        )
        assert model._tape7_import is not None  # type: ignore[attr-defined]
        assert model._tape7_up_import is not None  # type: ignore[attr-defined]
        assert model._tape7_up_import.source_path == str(up)  # type: ignore[attr-defined]

    @pytest.mark.level0
    def test_modtran_up_path_without_main_raises(self, tmp_path: Path) -> None:
        up = tmp_path / "up.tp7"
        _write_named_header_tape7(up)
        with pytest.raises(ValueError, match="tape7_up_path"):
            build_atmosphere_model(
                _make_params("modtran", atmosphere__modtran__tape7_up_path=str(up))
            )

    @pytest.mark.level0
    def test_modtran_up_path_missing_file_raises(self, tmp_path: Path) -> None:
        full = tmp_path / "full.tp7"
        _write_named_header_tape7(full)
        with pytest.raises(FileNotFoundError, match="tape7_up_path"):
            build_atmosphere_model(
                _make_params(
                    "modtran",
                    atmosphere__modtran__tape7_path=str(full),
                    atmosphere__modtran__tape7_up_path=str(tmp_path / "missing.tp7"),
                )
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
    def test_modtran_flux_path_builds_import(self, tmp_path: Path) -> None:
        tape7 = tmp_path / "run.tp7"
        flux = tmp_path / "run_flux.csv"
        _write_named_header_tape7(tape7)
        _write_flux_csv(flux)
        model = build_atmosphere_model(
            _make_params(
                "modtran",
                atmosphere__modtran__tape7_path=str(tape7),
                atmosphere__modtran__flux_path=str(flux),
            )
        )
        imp = model._flux_import  # type: ignore[attr-defined]
        assert imp is not None
        assert imp.source_path == str(flux)
        assert imp.wavelength_um[0] < imp.wavelength_um[-1]  # ascending µm

    @pytest.mark.level0
    def test_modtran_flux_path_without_main_raises(self, tmp_path: Path) -> None:
        flux = tmp_path / "run_flux.csv"
        _write_flux_csv(flux)
        with pytest.raises(ValueError, match="flux_path"):
            build_atmosphere_model(
                _make_params("modtran", atmosphere__modtran__flux_path=str(flux))
            )

    @pytest.mark.level0
    def test_modtran_flux_path_missing_file_raises(self, tmp_path: Path) -> None:
        tape7 = tmp_path / "run.tp7"
        _write_named_header_tape7(tape7)
        with pytest.raises(FileNotFoundError, match="flux_path"):
            build_atmosphere_model(
                _make_params(
                    "modtran",
                    atmosphere__modtran__tape7_path=str(tape7),
                    atmosphere__modtran__flux_path=str(tmp_path / "missing.csv"),
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


class TestInterpolatedRootDirDescent:
    """Owner bug 2026-07-18 (second report): picking the library ROOT
    (data/atmospheres/) instead of a family folder must not dead-end."""

    @pytest.mark.level0
    def test_library_root_descends_into_axes_matching_family(self) -> None:
        from radiant.atmosphere.interpolated import InterpolatedAtmosphere
        from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

        if not (_SHIPPED_ATMOSPHERES_DIR / "us_standard_zenith_fan").exists():
            pytest.skip("shipped atmosphere library not present")
        model = build_atmosphere_model(
            _make_params(
                "interpolated",
                atmosphere__interpolated_data_dir=str(_SHIPPED_ATMOSPHERES_DIR),
            )
        )
        assert isinstance(model, InterpolatedAtmosphere)
        assert model.axes == ["path_zenith_rad"]

    @pytest.mark.level0
    def test_runless_dir_error_names_family_subfolders(self, tmp_path: Path) -> None:
        (tmp_path / "some_family").mkdir()
        (tmp_path / "some_family" / "a.npz").write_bytes(b"")
        with pytest.raises(ValueError, match="some_family"):
            build_atmosphere_model(
                _make_params(
                    "interpolated",
                    atmosphere__interpolated_data_dir=str(tmp_path),
                    atmosphere__interpolation_axes="solar_zenith_rad",
                )
            )
