"""GeometryStage contract tests — published outputs, purity, alias behavior."""

from __future__ import annotations

import math
import warnings

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
        assert out["target_range_m"] == pytest.approx(750_000.0, rel=1e-9)

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
        assert ps.get("geometry.target_range_m") == pytest.approx(123_456.0, rel=1e-9)

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
        assert value == pytest.approx(42_000.0, rel=1e-9)

    def test_stage_sees_alias_set_value(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", H)
        with pytest.warns(DeprecationWarning):
            ps.set("source.target.range_m", 900_000.0)
        ps.resolve()
        out = run_stage(ps).stage_outputs["geometry"]
        assert out["target_range_m"] == pytest.approx(900_000.0, rel=1e-9)


class TestValidationSurface:
    def test_missing_sensor_altitude_raises_actionably(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        with pytest.raises(Exception, match="geometry.sensor_altitude_m"):
            ps.resolve()

    def test_horizontal_view_rejected(self) -> None:
        """θ_o = π/2 with the sensor ABOVE the target is the grazing case.

        Since ADR-0011 the schema domain is the closed [0, π], so π/2 is no
        longer a bounds violation — it is rejected one layer in, by the
        altitude/hemisphere invariant (a sensor strictly above the target
        cannot sit on the target's horizon plane) and, failing that, by the
        hard horizon guard.  Both name "horizon".
        """
        ps = make_params(geometry__path_zenith_rad=math.pi / 2.0)
        with pytest.raises(Exception, match="horizon"):
            run_stage(ps)


class TestLevelPath:
    """Equal altitudes (ADR-0011 / guardrail G4).

    The old "collocated — no viewing triangle" carve-out is retired: an
    equal-altitude scene with ANY separation resolves the full horizontal
    triangle through the central-angle form; only coincident endpoints
    (no separation at all) have no path.
    """

    def test_coincident_endpoints_have_no_path(self) -> None:
        """Zero separation is the φ → 0 limit, not a special case."""
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 0.0)
        ps.resolve()
        out = run_stage(ps).stage_outputs["geometry"]
        assert out["slant_range_m"] is None
        assert out["ground_range_m"] is None
        assert out["eta_rad"] is None
        assert out["incidence_angle_rad"] is None
        assert out["theta_o_rad"] == pytest.approx(math.pi / 2.0, abs=1e-15)
        assert out["los_direction"] == "level"
        assert "coincident endpoints" in out["viewing_mode"]

    def test_lab_bench_range_builds_the_horizontal_triangle(self) -> None:
        """A 5 m bench at 0 m: θ_o ≈ π/2, slant = the entered chord, guard clean."""
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 0.0)
        ps.set("geometry.target_range_m", 5.0)
        ps.resolve()
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)  # guard must be silent
            out = run_stage(ps).stage_outputs["geometry"]
        assert out["theta_o_rad"] > math.pi / 2.0  # the chord sags below horizontal
        assert out["theta_o_rad"] == pytest.approx(math.pi / 2.0, abs=1e-6)
        assert out["slant_range_m"] == pytest.approx(5.0, rel=1e-9)
        assert out["ground_range_m"] == pytest.approx(5.0, rel=1e-6)
        assert out["los_direction"] == "level"
        assert "level path" in out["viewing_mode"]

    def test_tower_pair_ground_range_is_clean(self) -> None:
        """Matrix cell E1: two 30 m towers 8 km apart — Δh ≈ 1.3 m, clean."""
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 30.0)
        ps.set("geometry.target_altitude_m", 30.0)
        ps.set("geometry.ground_range_m", 8_000.0)
        ps.resolve()
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            out = run_stage(ps).stage_outputs["geometry"]
        assert math.degrees(out["theta_o_rad"]) == pytest.approx(90.036, abs=1e-3)
        assert out["slant_range_m"] == pytest.approx(8_000.0, rel=1e-4)
        assert out["los_direction"] == "level"


class TestUpLooking:
    """ADR-0011: the sensor may sit below the target (Gap 107)."""

    def test_leo_to_geo_default_is_target_at_zenith(self) -> None:
        """Phase 1 quick win — the LEO→GEO scene resolves with no angle entry."""
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 500_000.0)
        ps.set("geometry.target_altitude_m", 35_786_000.0)
        ps.resolve()
        out = run_stage(ps).stage_outputs["geometry"]
        assert out["theta_o_rad"] == pytest.approx(math.pi, abs=1e-12)
        assert out["slant_range_m"] == pytest.approx(35_286_000.0, rel=1e-12)
        assert out["ground_range_m"] == pytest.approx(0.0, abs=1e-12)
        assert out["los_direction"] == "up"
        assert out["los_geometry"].is_uplooking

    def test_slant_theta_o_is_obtuse(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 0.0)
        ps.set("geometry.target_altitude_m", 10_000.0)
        ps.set("geometry.path_zenith_rad", 0.5)  # ζ at the ground sensor
        ps.resolve()
        out = run_stage(ps).stage_outputs["geometry"]
        assert out["theta_o_rad"] > math.pi / 2.0
        assert out["los_direction"] == "up"
        assert out["incidence_angle_rad"] == pytest.approx(out["theta_o_rad"], rel=1e-12)


class TestHorizonGuardAtTheStage:
    """Plan §8.3 addendum — the guard now judges every scene the stage builds."""

    def _level(self, h_m: float, arc_m: float) -> ParameterSet:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", h_m)
        ps.set("geometry.target_altitude_m", h_m)
        ps.set("geometry.ground_range_m", arc_m)
        ps.resolve()
        return ps

    def test_long_level_arm_warns(self) -> None:
        """200 km at 5 km altitude: Δh ≈ 780 m — inside the warn shoulder."""
        with pytest.warns(UserWarning, match="near-horizontal"):
            out = run_stage(self._level(5_000.0, 200_000.0)).stage_outputs["geometry"]
        assert out["los_direction"] == "level"

    def test_deep_level_transit_raises(self) -> None:
        """500 km at 5 km altitude: Δh ≈ 4.9 km — a limb-like transit."""
        with pytest.raises(Exception, match="tangent"):
            run_stage(self._level(5_000.0, 500_000.0))

    def test_near_horizon_down_looking_now_warns(self) -> None:
        """Documented consequence of the guard: θ_o in (88°, 90°) was silent
        before ADR-0011 (the schema stopped at 89.5°) and now warns."""
        with pytest.warns(UserWarning, match="near-horizontal"):
            run_stage(make_params(geometry__path_zenith_rad=math.radians(89.0)))

    def test_normal_off_nadir_stays_silent(self) -> None:
        """Every shipped scenario lives here (≤ ~75°): no new warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            run_stage(make_params(geometry__path_zenith_rad=math.radians(75.0)))


class TestSensorEndpointCarried:
    """GF-3: h_sensor is on the contract object for every scene."""

    def test_los_carries_h_sensor(self) -> None:
        out = run_stage(make_params(geometry__path_zenith_rad=0.4)).stage_outputs["geometry"]
        los = out["los_geometry"]
        assert los.h_sensor == pytest.approx(H, rel=1e-12)
        assert los.los_direction == "down"
        assert out["los_direction"] == "down"

    def test_los_round_trip_keeps_h_sensor(self) -> None:
        los = run_stage(make_params()).stage_outputs["geometry"]["los_geometry"]
        assert LineOfSightGeometry.from_dict(los.to_dict()) == los


class TestRangeConsistency:
    """CU-093: user range vs angle-implied slant range."""

    def test_agreeing_range_and_angle_accepted(self) -> None:
        from radiant.core.viewing_triangle import slant_range_from_theta_o_m

        slant = slant_range_from_theta_o_m(0.5, H)
        out = run_stage(
            make_params(
                geometry__path_zenith_rad=0.5,
                geometry__target_range_m=slant,
            )
        ).stage_outputs["geometry"]
        assert out["target_range_m"] == pytest.approx(slant, rel=1e-12)

    def test_contradicting_range_and_angle_raises(self) -> None:
        from radiant.geometry.errors import GeometrySpecificationError

        with pytest.raises(GeometrySpecificationError, match="disagrees"):
            run_stage(
                make_params(
                    geometry__path_zenith_rad=0.5,
                    geometry__target_range_m=100_000.0,  # far from ~700 km slant
                )
            )

    def test_range_only_mismatch_warns_not_raises(self) -> None:
        with pytest.warns(UserWarning, match="CU-093"):
            out = run_stage(make_params(geometry__target_range_m=100_000.0)).stage_outputs[
                "geometry"
            ]
        assert out["target_range_m"] == pytest.approx(100_000.0, rel=1e-9)

    def test_range_matching_nadir_slant_is_silent(self) -> None:
        import warnings as _w

        with _w.catch_warnings():
            _w.simplefilter("error", UserWarning)
            out = run_stage(
                make_params(geometry__target_range_m=H)  # == nadir slant
            ).stage_outputs["geometry"]
        assert out["target_range_m"] == pytest.approx(H, rel=1e-9)
