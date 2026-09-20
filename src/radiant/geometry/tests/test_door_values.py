"""Level 0 tests for :mod:`radiant.geometry.door_values` (CU-377 F-48 / F-05).

Each door's value is the number the operator would have typed at that door to
land on the geometry the active door produced — proved as a **round trip**:
resolve through door A, read door B's value, resolve through door B alone, and
the canonical θ_o (or θ_s, ground speed, LOS rate) agrees to numerical
precision. Analytic anchors: a nadir view (θ_o = 0) has zero off-boresight
angle, zero ground range and a 90° elevation; a level 2 m bench has a 2 m
chord and a path zenith of 90° + φ/2.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.parameters import ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.door_values import door_values
from radiant.geometry.mode_manifest import all_mode_params
from radiant.geometry.modes import (
    resolve_kinematics,
    resolve_los_rate,
    resolve_solar,
    resolve_viewing,
)

H_LEO = 500_000.0


def make_params(**inputs: object) -> ParameterSet:
    """Geometry-only ParameterSet with the sensor altitude anchored."""
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", H_LEO)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _theta_o_via(dotpath: str, value: float, **anchors: object) -> float:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", anchors.pop("h_sensor", H_LEO))
    for name, v in anchors.items():
        ps.set(name.replace("__", "."), v)
    ps.set(dotpath, value)
    ps.resolve()
    return resolve_viewing(ps).theta_o_rad


class TestShape:
    def test_every_mode_parameter_has_an_entry(self) -> None:
        ps = make_params()
        values = door_values(ps)
        assert set(values) == set(all_mode_params())

    def test_unresolvable_set_gives_all_none(self) -> None:
        ps = ParameterSet(list(ALL_PARAMETERS))  # no altitude anchor → cannot resolve
        values = door_values(ps)
        assert set(values) == set(all_mode_params())
        assert all(v is None for v in values.values())


class TestViewingAnchors:
    def test_nadir_view_analytic(self) -> None:
        """θ_o = 0 (nadir): V2 = 0, V3 = 0 m, V4 = π/2, V0 = h_sensor, V1 = 0."""
        values = door_values(make_params())
        assert values["geometry.path_zenith_rad"] == pytest.approx(0.0, abs=1e-12)
        assert values["geometry.sensor_off_boresight_rad"] == pytest.approx(0.0, abs=1e-12)
        assert values["geometry.ground_range_m"] == pytest.approx(0.0, abs=1e-9)
        assert values["geometry.elevation_angle_rad"] == pytest.approx(math.pi / 2, abs=1e-12)
        assert values["geometry.target_range_m"] == pytest.approx(H_LEO, rel=1e-12)

    def test_level_bench_analytic(self) -> None:
        """A 2 m chord at 0 m: V0 = 2 m, V1 = 90° + φ/2 with φ = 2·asin(1/R_E)."""
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 0.0)
        ps.set("geometry.target_altitude_m", 0.0)
        ps.set("geometry.target_range_m", 2.0)
        ps.resolve()
        values = door_values(ps)
        assert values["geometry.target_range_m"] == pytest.approx(2.0, rel=1e-9)
        theta_o = resolve_viewing(ps).theta_o_rad
        assert values["geometry.path_zenith_rad"] == pytest.approx(theta_o, abs=1e-12)
        assert values["geometry.elevation_angle_rad"] == pytest.approx(
            math.pi / 2 - theta_o, abs=1e-12
        )


class TestViewingRoundTrip:
    @pytest.mark.parametrize(
        "door",
        [
            "geometry.path_zenith_rad",
            "geometry.sensor_off_boresight_rad",
            "geometry.ground_range_m",
            "geometry.elevation_angle_rad",
        ],
    )
    def test_down_looking_doors_reproduce_theta_o(self, door: str) -> None:
        ps = make_params(geometry__path_zenith_rad=0.6)
        expected = resolve_viewing(ps).theta_o_rad
        value = door_values(ps)[door]
        assert value is not None
        assert _theta_o_via(door, float(value)) == pytest.approx(expected, rel=1e-9)

    @pytest.mark.parametrize(
        "door",
        [
            "geometry.path_zenith_rad",
            "geometry.sensor_off_boresight_rad",
            "geometry.ground_range_m",
            "geometry.elevation_angle_rad",
        ],
    )
    def test_up_looking_doors_reproduce_theta_o(self, door: str) -> None:
        """Sensor on the ground looking up at 10 km: every door round-trips."""
        anchors = {"h_sensor": 0.0, "geometry__target_altitude_m": 10_000.0}
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", 0.0)
        ps.set("geometry.target_altitude_m", 10_000.0)
        ps.set("geometry.elevation_angle_rad", 0.7)
        ps.resolve()
        expected = resolve_viewing(ps).theta_o_rad
        value = door_values(ps)[door]
        assert value is not None
        assert _theta_o_via(door, float(value), **anchors) == pytest.approx(expected, rel=1e-9)

    def test_slant_range_door_is_the_derived_slant(self) -> None:
        ps = make_params(geometry__path_zenith_rad=0.6)
        assert door_values(ps)["geometry.target_range_m"] == pytest.approx(
            resolve_viewing(ps).slant_range_m, rel=1e-12
        )


class TestSolar:
    def test_s1_s2_from_zenith(self) -> None:
        ps = make_params(geometry__solar_zenith_rad=0.8)
        values = door_values(ps)
        assert values["geometry.solar_zenith_rad"] == pytest.approx(0.8, abs=1e-12)
        assert values["geometry.solar_elevation_rad"] == pytest.approx(math.pi / 2 - 0.8, abs=1e-12)

    def test_site_time_from_zenith_has_no_inverse(self) -> None:
        ps = make_params(geometry__solar_zenith_rad=0.8)
        values = door_values(ps)
        for name in (
            "geometry.site_latitude_rad",
            "geometry.day_of_year",
            "geometry.local_solar_time_h",
            "geometry.ltan_h",
        ):
            assert values[name] is None

    def test_s3_round_trips_through_s1(self) -> None:
        ps = make_params(
            geometry__site_latitude_rad=0.5,
            geometry__day_of_year=172,
            geometry__local_solar_time_h=9.0,
        )
        expected = resolve_solar(ps).theta_s_rad
        s1 = door_values(ps)["geometry.solar_zenith_rad"]
        assert s1 is not None
        ps2 = make_params(geometry__solar_zenith_rad=float(s1))
        assert resolve_solar(ps2).theta_s_rad == pytest.approx(expected, rel=1e-12)

    def test_night_has_no_solar_doors(self) -> None:
        ps = make_params(geometry__solar_illumination="night")
        values = door_values(ps)
        assert values["geometry.solar_zenith_rad"] is None
        assert values["geometry.solar_elevation_rad"] is None


class TestKinematicsAndLosRate:
    def test_circular_orbit_gives_the_direct_speed(self) -> None:
        ps = make_params(geometry__circular_orbit=True)
        values = door_values(ps)
        assert values["geometry.ground_speed_m_s"] == pytest.approx(
            resolve_kinematics(ps).ground_speed_m_s, rel=1e-12
        )
        assert values["geometry.circular_orbit"] is True

    def test_direct_speed_reports_not_circular(self) -> None:
        ps = make_params(geometry__ground_speed_m_s=7000.0)
        values = door_values(ps)
        assert values["geometry.ground_speed_m_s"] == pytest.approx(7000.0, rel=1e-12)
        assert values["geometry.circular_orbit"] is False

    def test_k1_is_the_platform_only_rate(self) -> None:
        ps = make_params(geometry__ground_speed_m_s=7000.0, geometry__path_zenith_rad=0.3)
        viewing = resolve_viewing(ps)
        rate = resolve_los_rate(ps, viewing, resolve_kinematics(ps)).los_angular_rate_rad_s
        values = door_values(ps)
        assert values["geometry.los_angular_rate_rad_s"] == pytest.approx(rate, rel=1e-12)
        assert values["geometry.target_speed_m_s"] is None
        assert values["geometry.target_heading_rad"] is None
        assert values["geometry.target_climb_rad"] is None
