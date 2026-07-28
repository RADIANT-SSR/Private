"""Level-1 tests: AtmosphereStage turbulence wiring and the Rule-6 loader (Gap 110).

Zero drift is the headline assertion: with ``atmosphere.cn2_profile`` at its
``"direct"`` default, the stage publishes exactly the outputs it published
before Gap 110 — the same ``r0_m`` value, and no new keys.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.loaders import build_cn2_profile
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainState
from radiant.core.descriptors import T1Thermal
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

WL = np.linspace(0.45, 0.55, 21)  # band centre 0.50 µm


def _state(h_sensor: float = 8000.0, h_tgt: float = 0.0, theta_o: float = 0.0) -> ChainState:
    state = ChainState(wavelength_um=WL)
    epsilon = SpectralData(
        name="target.epsilon",
        wavelength_um=WL,
        values=np.full_like(WL, 0.95),
        unit="",
        source="test",
    )
    target = T1Thermal(
        T_t=300.0,
        epsilon=epsilon,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=h_tgt,
    )
    los = LineOfSightGeometry(h_tgt=h_tgt, h_sensor=h_sensor, theta_o=theta_o)
    state = state.with_stage_output("source", "target", target)
    state = state.with_stage_output("source", "background", None)
    return state.with_stage_output("source", "los_geometry", los)


def _params(**overrides: object) -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", 8000.0)
    ps.set("atmosphere.model", "simple")
    for dotpath, value in overrides.items():
        ps.set(dotpath.replace("__", "."), value)
    ps.resolve()
    return ps


class TestZeroDrift:
    @pytest.mark.level1
    def test_default_publishes_no_turbulence_outputs(self) -> None:
        out = AtmosphereStage().run(_state(), _params())
        atm = out.stage_outputs["atmosphere"]
        assert "r0_m" not in atm
        assert "r0_resolution" not in atm

    @pytest.mark.level1
    def test_direct_r0_is_published_verbatim_and_adds_no_keys(self) -> None:
        out = AtmosphereStage().run(_state(), _params(atmosphere__r0_m=0.0731))
        atm = out.stage_outputs["atmosphere"]
        assert atm["r0_m"] == 0.0731
        assert "r0_resolution" not in atm


class TestProfileWiring:
    @pytest.mark.level1
    def test_profile_publishes_r0_and_the_resolution_record(self) -> None:
        # Airborne sensor at 8 km looking DOWN at the ground: the turbulence
        # column is 0-8 km, which is where the HV surface layer lives.
        out = AtmosphereStage().run(_state(), _params(atmosphere__cn2_profile="hufnagel_valley"))
        atm = out.stage_outputs["atmosphere"]
        assert 0.0 < atm["r0_m"] < 1.0
        record = atm["r0_resolution"]
        assert record.mode == "profile"
        assert record.reference_wavelength_um == pytest.approx(0.50, rel=1e-12)
        assert record.path is not None

    @pytest.mark.level1
    def test_uplooking_ground_sensor_sees_worse_seeing_than_an_airborne_one(self) -> None:
        ground = AtmosphereStage().run(
            _state(h_sensor=0.0, h_tgt=800.0e3, theta_o=math.pi),
            _params(atmosphere__cn2_profile="hufnagel_valley", geometry__sensor_altitude_m=0.0),
        )
        airborne = AtmosphereStage().run(
            _state(h_sensor=10_000.0, h_tgt=800.0e3, theta_o=math.pi),
            _params(
                atmosphere__cn2_profile="hufnagel_valley",
                geometry__sensor_altitude_m=10_000.0,
            ),
        )
        assert (
            airborne.stage_outputs["atmosphere"]["r0_m"]
            > ground.stage_outputs["atmosphere"]["r0_m"]
        )

    @pytest.mark.level1
    def test_space_sensor_omits_the_turbulence_term_entirely(self) -> None:
        """The retired ScopeError case: no refusal, no term — just nothing."""
        out = AtmosphereStage().run(
            _state(h_sensor=500.0e3, h_tgt=35_786.0e3, theta_o=math.pi),
            _params(
                atmosphere__cn2_profile="hufnagel_valley",
                atmosphere__model="exo",
                geometry__sensor_altitude_m=500.0e3,
            ),
        )
        atm = out.stage_outputs["atmosphere"]
        assert "r0_m" not in atm
        assert atm["r0_resolution"].mode == "off"
        assert atm["r0_resolution"].path.negligible is True


class TestLoader:
    @pytest.mark.level0
    def test_direct_selector_loads_nothing(self, tmp_path: Path) -> None:
        assert build_cn2_profile(_params()) is None

    @pytest.mark.level0
    def test_hufnagel_valley_selector_loads_nothing(self) -> None:
        assert build_cn2_profile(_params(atmosphere__cn2_profile="hufnagel_valley")) is None

    @pytest.mark.level0
    def test_csv_round_trip(self, tmp_path: Path) -> None:
        csv = tmp_path / "cn2.csv"
        csv.write_text(
            "# altitude_m,cn2_m^-2/3\n"
            "altitude_m,cn2\n"
            "0.0, 1.7e-14\n"
            "\n"
            "1000.0, 1.4e-16   # jet stream below\n"
            "10000.0, 1.7e-17\n",
            encoding="utf-8",
        )
        profile = build_cn2_profile(
            _params(
                atmosphere__cn2_profile="tabulated",
                atmosphere__cn2_tabulated_file=str(csv),
            )
        )
        assert isinstance(profile, TabulatedCn2Profile)
        np.testing.assert_allclose(profile.altitude_m, [0.0, 1000.0, 10000.0], rtol=0)
        np.testing.assert_allclose(profile.cn2_m23, [1.7e-14, 1.4e-16, 1.7e-17], rtol=0)
        assert profile.label == "cn2.csv"

    @pytest.mark.level0
    def test_missing_file_parameter_is_actionable(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="cn2_tabulated_file is empty"):
            build_cn2_profile(_params(atmosphere__cn2_profile="tabulated"))

    @pytest.mark.level0
    def test_missing_file_on_disk_is_actionable(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="file not found"):
            build_cn2_profile(
                _params(
                    atmosphere__cn2_profile="tabulated",
                    atmosphere__cn2_tabulated_file=str(tmp_path / "nope.csv"),
                )
            )

    @pytest.mark.level0
    def test_one_column_row_is_actionable(self, tmp_path: Path) -> None:
        csv = tmp_path / "bad.csv"
        csv.write_text("0.0\n1000.0\n", encoding="utf-8")
        with pytest.raises(AtmosphereValidationError, match="two comma-separated columns"):
            build_cn2_profile(
                _params(
                    atmosphere__cn2_profile="tabulated",
                    atmosphere__cn2_tabulated_file=str(csv),
                )
            )

    @pytest.mark.level0
    def test_non_numeric_body_row_is_actionable(self, tmp_path: Path) -> None:
        csv = tmp_path / "bad.csv"
        csv.write_text("0.0,1e-14\nfoo,bar\n", encoding="utf-8")
        with pytest.raises(AtmosphereValidationError, match="not a numeric"):
            build_cn2_profile(
                _params(
                    atmosphere__cn2_profile="tabulated",
                    atmosphere__cn2_tabulated_file=str(csv),
                )
            )

    @pytest.mark.level0
    def test_empty_file_is_actionable(self, tmp_path: Path) -> None:
        csv = tmp_path / "empty.csv"
        csv.write_text("# nothing here\n", encoding="utf-8")
        with pytest.raises(AtmosphereValidationError, match="no numeric rows"):
            build_cn2_profile(
                _params(
                    atmosphere__cn2_profile="tabulated",
                    atmosphere__cn2_tabulated_file=str(csv),
                )
            )
