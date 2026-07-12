"""Level 0 tests — input-mode detection and resolution (ADR-0006 §3 rules).

Covers every v1 mode (V1–V4, V6 viewing; S0–S3 solar), the
over-specification decision matrix, and the provenance-based detection
contract (defaults are inert).
"""

from __future__ import annotations

import math

import pytest

from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.orbit import ground_track_speed_m_s
from radiant.core.parameters import ParameterSet
from radiant.core.solar_geometry import solar_zenith_angle_rad
from radiant.core.viewing_triangle import (
    eta_from_theta_o,
    ground_range_from_theta_o_m,
)
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.modes import (
    resolve_kinematics,
    resolve_solar,
    resolve_viewing,
)

H_LEO = 500_000.0


def make_params(**inputs: object) -> ParameterSet:
    """Geometry-only ParameterSet with sensor altitude anchored."""
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", H_LEO)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


# ---------------------------------------------------------------------------
# Viewing modes
# ---------------------------------------------------------------------------


class TestViewingModes:
    def test_default_is_nadir(self) -> None:
        v = resolve_viewing(make_params())
        assert v.theta_o_rad == pytest.approx(0.0, abs=1e-12)
        assert v.slant_range_m == pytest.approx(H_LEO, rel=1e-12)
        assert v.ground_range_m == pytest.approx(0.0, abs=1e-9)
        assert "default" in v.mode

    def test_v1_path_zenith(self) -> None:
        v = resolve_viewing(make_params(geometry__path_zenith_rad=0.6))
        assert v.theta_o_rad == pytest.approx(0.6, rel=1e-12)
        assert v.mode == "geometry.path_zenith_rad"

    def test_v2_off_nadir_derives_theta_o(self) -> None:
        eta = 0.5
        v = resolve_viewing(make_params(geometry__sensor_off_nadir_rad=eta))
        assert v.theta_o_rad == pytest.approx(theta_o_from_eta(eta, H_LEO, 0.0), rel=1e-12)
        assert v.eta_rad == pytest.approx(eta, rel=1e-9)
        assert v.mode == "geometry.sensor_off_nadir_rad"

    def test_v3_ground_range_derives_theta_o(self) -> None:
        theta_ref = 0.7
        s = ground_range_from_theta_o_m(theta_ref, H_LEO, 0.0)
        v = resolve_viewing(make_params(geometry__ground_range_m=s))
        assert v.theta_o_rad == pytest.approx(theta_ref, rel=1e-6)
        assert v.ground_range_m == pytest.approx(s, rel=1e-6)
        assert v.mode == "geometry.ground_range_m"

    def test_v4_elevation_is_complement(self) -> None:
        elev = math.radians(60.0)
        v = resolve_viewing(make_params(geometry__elevation_angle_rad=elev))
        assert v.theta_o_rad == pytest.approx(math.pi / 2.0 - elev, rel=1e-12)
        assert v.mode == "geometry.elevation_angle_rad"

    def test_consistent_redundant_entries_accepted(self) -> None:
        theta_o = 0.6
        # The eta that implies exactly theta_o = 0.6 (sine-rule inverse).
        eta = eta_from_theta_o(theta_o, H_LEO, 0.0)
        v = resolve_viewing(
            make_params(
                geometry__path_zenith_rad=theta_o,
                geometry__sensor_off_nadir_rad=eta,
            )
        )
        assert v.theta_o_rad == pytest.approx(theta_o, rel=1e-9)
        assert "consistent" in v.mode

    def test_disagreeing_entries_raise(self) -> None:
        with pytest.raises(GeometrySpecificationError) as exc:
            resolve_viewing(
                make_params(
                    geometry__path_zenith_rad=0.6,
                    # 0.6 rad off-nadir at LEO implies theta_o ≈ 0.65 — >1% off.
                    geometry__sensor_off_nadir_rad=0.6,
                )
            )
        msg = str(exc.value)
        assert "path_zenith_rad" in msg and "off_nadir" in msg

    def test_three_way_disagreement_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError):
            resolve_viewing(
                make_params(
                    geometry__path_zenith_rad=0.3,
                    geometry__elevation_angle_rad=math.radians(45.0),
                    geometry__ground_range_m=1_000_000.0,
                )
            )

    def test_elevated_target_enters_triangle(self) -> None:
        v = resolve_viewing(
            make_params(
                geometry__path_zenith_rad=0.4,
                geometry__target_altitude_m=4000.0,
            )
        )
        assert v.h_target_m == pytest.approx(4000.0)
        assert v.slant_range_m < H_LEO / math.cos(0.4)  # tighter than flat Earth


# ---------------------------------------------------------------------------
# Solar modes
# ---------------------------------------------------------------------------


class TestSolarModes:
    def test_s0_night_strips_solar(self) -> None:
        s = resolve_solar(make_params(geometry__solar_illumination="night"))
        assert s.theta_s_rad is None
        assert s.delta_phi_rad is None
        assert s.mode == "night"

    def test_s1_default(self) -> None:
        s = resolve_solar(make_params())
        assert s.theta_s_rad == pytest.approx(0.5, rel=1e-12)  # schema default
        assert "default" in s.mode

    def test_s1_explicit(self) -> None:
        s = resolve_solar(make_params(geometry__solar_zenith_rad=0.9))
        assert s.theta_s_rad == pytest.approx(0.9, rel=1e-12)
        assert s.mode == "geometry.solar_zenith_rad"

    def test_s2_elevation_is_complement(self) -> None:
        elev = math.radians(35.0)
        s = resolve_solar(make_params(geometry__solar_elevation_rad=elev))
        assert s.theta_s_rad == pytest.approx(math.pi / 2.0 - elev, rel=1e-12)

    def test_s3_equator_equinox_noon_is_overhead(self) -> None:
        s = resolve_solar(
            make_params(
                geometry__site_latitude_rad=0.0,
                geometry__day_of_year=80,
                geometry__local_solar_time_h=12.0,
            )
        )
        # Equator, equinox, solar noon → sun essentially overhead.
        assert s.theta_s_rad == pytest.approx(0.0, abs=math.radians(1.5))

    def test_s3_matches_core_solar_geometry(self) -> None:
        lat_rad, doy, lst = math.radians(35.0), 200, 9.5
        s = resolve_solar(
            make_params(
                geometry__site_latitude_rad=lat_rad,
                geometry__day_of_year=doy,
                geometry__local_solar_time_h=lst,
            )
        )
        expected = solar_zenith_angle_rad(math.degrees(lat_rad), doy, lst)
        assert s.theta_s_rad == pytest.approx(expected, rel=1e-12)

    def test_s3_partial_inputs_use_documented_defaults(self) -> None:
        # Only latitude set: DOY and LST fall back to schema defaults
        # (equinox, noon) — rule 4 under-specification behavior.
        lat_rad = math.radians(45.0)
        s = resolve_solar(make_params(geometry__site_latitude_rad=lat_rad))
        expected = solar_zenith_angle_rad(45.0, 80, 12.0)
        assert s.theta_s_rad == pytest.approx(expected, rel=1e-12)

    def test_ltan_and_lst_together_raise(self) -> None:
        with pytest.raises(GeometrySpecificationError):
            resolve_solar(
                make_params(
                    geometry__ltan_h=10.5,
                    geometry__local_solar_time_h=10.5,
                )
            )

    def test_s1_vs_s3_disagreement_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError):
            resolve_solar(
                make_params(
                    geometry__solar_zenith_rad=0.1,
                    geometry__site_latitude_rad=math.radians(60.0),
                    geometry__day_of_year=355,
                    geometry__local_solar_time_h=8.0,
                )
            )

    def test_azimuth_wraps_into_pm_pi(self) -> None:
        s = resolve_solar(make_params(geometry__solar_azimuth_rad=4.0))
        assert s.delta_phi_rad == pytest.approx(4.0 - 2.0 * math.pi, rel=1e-9)


# ---------------------------------------------------------------------------
# Kinematics (V6)
# ---------------------------------------------------------------------------


class TestKinematics:
    def test_direct_default(self) -> None:
        k = resolve_kinematics(make_params())
        assert k.ground_speed_m_s == 0.0
        assert k.orbital_period_s is None
        assert k.mode == "direct"

    def test_direct_explicit_speed(self) -> None:
        k = resolve_kinematics(make_params(geometry__ground_speed_m_s=250.0))
        assert k.ground_speed_m_s == pytest.approx(250.0)
        assert k.mode == "direct"

    def test_circular_orbit_derives_speed_and_period(self) -> None:
        k = resolve_kinematics(make_params(geometry__circular_orbit=True))
        assert k.ground_speed_m_s == pytest.approx(ground_track_speed_m_s(H_LEO), rel=1e-12)
        assert k.orbital_period_s is not None and k.orbital_period_s > 0
        assert k.mode == "circular_orbit"

    def test_circular_orbit_with_agreeing_speed_ok(self) -> None:
        v = ground_track_speed_m_s(H_LEO)
        k = resolve_kinematics(
            make_params(geometry__circular_orbit=True, geometry__ground_speed_m_s=v)
        )
        assert k.ground_speed_m_s == pytest.approx(v, rel=1e-12)

    def test_circular_orbit_with_disagreeing_speed_raises(self) -> None:
        with pytest.raises(GeometrySpecificationError):
            resolve_kinematics(
                make_params(
                    geometry__circular_orbit=True,
                    geometry__ground_speed_m_s=250.0,  # aircraft speed at LEO
                )
            )
