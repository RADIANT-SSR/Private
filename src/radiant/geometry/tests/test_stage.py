"""GeometryStage contract tests — published outputs, purity, alias behavior."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet, Provenance
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.stage import GeometryStage

H = 600_000.0


def make_params(**inputs: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", H)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def run_stage(params: ParameterSet) -> ChainState:
    state = ChainState(wavelength_um=np.linspace(3.0, 5.0, 8))
    return GeometryStage().run(state, params)


class TestPublishedContract:
    def test_all_contract_keys_present(self) -> None:
        out = run_stage(make_params()).stage_outputs["geometry"]
        for key in (
            "los_geometry",
            "theta_o_rad",
            "eta_rad",
            "slant_range_m",
            "ground_range_m",
            "incidence_angle_rad",
            "target_range_m",
            "h_sensor_m",
            "h_target_m",
            "theta_s_rad",
            "delta_phi_rad",
            "solar_illumination",
            "ground_speed_m_s",
            "orbital_period_s",
            "viewing_mode",
            "solar_mode",
            "kinematics_mode",
        ):
            assert key in out, f"missing stage output: {key}"

    def test_los_matches_scalar_outputs(self) -> None:
        out = run_stage(
            make_params(
                geometry__path_zenith_rad=0.4,
                geometry__target_altitude_m=1000.0,
                geometry__solar_zenith_rad=0.7,
                geometry__solar_azimuth_rad=1.1,
            )
        ).stage_outputs["geometry"]
        los = out["los_geometry"]
        assert isinstance(los, LineOfSightGeometry)
        assert los.theta_o == pytest.approx(out["theta_o_rad"], rel=1e-12)
        assert los.h_tgt == pytest.approx(out["h_target_m"], rel=1e-12)
        assert los.theta_s == pytest.approx(out["theta_s_rad"], rel=1e-12)
        assert los.delta_phi == pytest.approx(out["delta_phi_rad"], rel=1e-12)

    def test_incidence_equals_theta_o(self) -> None:
        out = run_stage(make_params(geometry__path_zenith_rad=0.8)).stage_outputs["geometry"]
        assert out["incidence_angle_rad"] == pytest.approx(out["theta_o_rad"], rel=1e-12)

    def test_target_range_sentinel_maps_to_none(self) -> None:
        out = run_stage(make_params()).stage_outputs["geometry"]
        assert out["target_range_m"] is None

    def test_target_range_user_value_passes_through(self) -> None:
        out = run_stage(make_params(geometry__target_range_m=750_000.0)).stage_outputs["geometry"]
        assert out["target_range_m"] == pytest.approx(750_000.0)

    def test_night_mode_none_solar(self) -> None:
        out = run_stage(make_params(geometry__solar_illumination="night")).stage_outputs["geometry"]
        assert out["theta_s_rad"] is None
        assert out["delta_phi_rad"] is None
        assert out["los_geometry"].theta_s is None


class TestStagePurity:
    def test_input_state_not_mutated(self) -> None:
        state = ChainState(wavelength_um=np.linspace(3.0, 5.0, 8))
        GeometryStage().run(state, make_params())
        assert "geometry" not in state.stage_outputs

    def test_no_frames_no_noise_no_mtf(self) -> None:
        result = run_stage(make_params())
        assert len(result.frames) == 0
        assert len(result.noise_terms) == 0
        assert len(result.mtf_terms) == 0

    def test_deterministic(self) -> None:
        p = make_params(geometry__path_zenith_rad=0.5)
        a = run_stage(p).stage_outputs["geometry"]
        b = run_stage(p).stage_outputs["geometry"]
        assert a["slant_range_m"] == b["slant_range_m"]
        assert a["theta_o_rad"] == b["theta_o_rad"]

    def test_stage_name(self) -> None:
        assert GeometryStage().name == "geometry"


class TestDeprecatedAlias:
    """source.target.range_m must warn and redirect to geometry.target_range_m."""

    def test_set_via_alias_warns_and_redirects(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", H)
        with pytest.warns(DeprecationWarning, match="geometry.target_range_m"):
            ps.set("source.target.range_m", 123_456.0)
        ps.resolve()
        assert ps.get("geometry.target_range_m") == pytest.approx(123_456.0)

    def test_alias_preserves_user_provenance(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", H)
        with pytest.warns(DeprecationWarning):
            ps.set("source.target.range_m", 5000.0)
        ps.resolve()
        rv = ps.get_resolved("geometry.target_range_m")
        assert rv.provenance is Provenance.USER_SET

    def test_get_via_alias_warns_and_returns_canonical(self) -> None:
        ps = make_params(geometry__target_range_m=42_000.0)
        with pytest.warns(DeprecationWarning):
            value = ps.get("source.target.range_m")
        assert value == pytest.approx(42_000.0)

    def test_stage_sees_alias_set_value(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", H)
        with pytest.warns(DeprecationWarning):
            ps.set("source.target.range_m", 900_000.0)
        ps.resolve()
        out = run_stage(ps).stage_outputs["geometry"]
        assert out["target_range_m"] == pytest.approx(900_000.0)


class TestValidationSurface:
    def test_missing_sensor_altitude_raises_actionably(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        with pytest.raises(Exception, match="geometry.sensor_altitude_m"):
            ps.resolve()

    def test_horizontal_view_rejected(self) -> None:
        with pytest.raises(Exception, match="bounds|π/2|horizon"):
            make_params(geometry__path_zenith_rad=math.pi / 2.0)
