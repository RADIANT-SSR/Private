"""Level 0 tests — input-mode detection and resolution (ADR-0006 §3 rules).

Covers every v1 mode (V1–V4, V6 viewing; S0–S3 solar), the
over-specification decision matrix, and the provenance-based detection
contract (defaults are inert).
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.orbit import ground_track_speed_m_s
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar_geometry import solar_zenith_angle_rad
from radiant.core.viewing_triangle import (
    eta_from_theta_o,
    ground_range_from_theta_o_m,
    level_central_angle_from_slant_m,
    level_theta_o_from_central_angle_rad,
    slant_range_from_theta_o_m,
    solve_from_lower_zenith,
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
        v = resolve_viewing(make_params(geometry__sensor_off_boresight_rad=eta))
        assert v.theta_o_rad == pytest.approx(theta_o_from_eta(eta, H_LEO, 0.0), rel=1e-12)
        assert v.eta_rad == pytest.approx(eta, rel=1e-9)
        assert v.mode == "geometry.sensor_off_boresight_rad"

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
                geometry__sensor_off_boresight_rad=eta,
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
                    geometry__sensor_off_boresight_rad=0.6,
                )
            )
        msg = str(exc.value)
        assert "path_zenith_rad" in msg and "off_boresight" in msg

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
        assert v.h_target_m == pytest.approx(4000.0, rel=1e-9)
        assert v.slant_range_m < H_LEO / math.cos(0.4)  # tighter than flat Earth

    @pytest.mark.parametrize("theta_o", [0.0, 0.1, 0.4, 0.7, 1.0, 1.3])
    def test_down_looking_arithmetic_is_bit_identical(self, theta_o: float) -> None:
        """Zero drift (plan §3 principle 3): the down-looking path must be
        the *same* expressions, not merely close — so exact float equality
        against the core solvers, no tolerance."""
        v = resolve_viewing(make_params(geometry__path_zenith_rad=theta_o))
        assert v.theta_o_rad == theta_o
        assert v.direction == "down"
        assert v.slant_range_m == slant_range_from_theta_o_m(theta_o, H_LEO, 0.0)
        if theta_o > 0.0:
            assert v.eta_rad == eta_from_theta_o(theta_o, H_LEO, 0.0)
            assert v.ground_range_m == ground_range_from_theta_o_m(theta_o, H_LEO, 0.0)
        else:
            assert v.eta_rad == 0.0
            assert v.ground_range_m == 0.0


# ---------------------------------------------------------------------------
# Direction-general viewing (ADR-0011, plan Phase 1)
# ---------------------------------------------------------------------------

H_GEO = 35_786_000.0


def uplooking_params(**inputs: object) -> ParameterSet:
    """Ground sensor (0 m) under an air/space target."""
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", 0.0)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


class TestUpLookingViewing:
    """The sensor below the target — the 2026-07-11 ruling is superseded."""

    def test_default_puts_target_at_the_sensor_zenith(self) -> None:
        v = resolve_viewing(uplooking_params(geometry__target_altitude_m=H_GEO))
        assert v.direction == "up"
        assert v.theta_o_rad == pytest.approx(math.pi, abs=1e-12)
        assert v.eta_rad == pytest.approx(math.pi, abs=1e-12)
        assert v.slant_range_m == pytest.approx(H_GEO, rel=1e-12)
        assert v.ground_range_m == pytest.approx(0.0, abs=1e-12)
        assert "default" in v.mode

    def test_v1_zenith_is_read_at_the_sensor(self) -> None:
        """V1 is the LOWER-endpoint zenith (ADR-0011 decision 3)."""
        zeta = 0.6
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__path_zenith_rad=zeta,
            )
        )
        expected = solve_from_lower_zenith(zeta, 0.0, 20_000.0)
        assert v.theta_o_rad == pytest.approx(expected.theta_o_rad, rel=1e-12)
        assert v.theta_o_rad > math.pi / 2.0
        assert v.slant_range_m == pytest.approx(expected.slant_range_m, rel=1e-9)
        assert v.ground_range_m == pytest.approx(R_EARTH_M * expected.central_angle_rad, rel=1e-6)
        assert "up-looking" in v.mode

    def test_v2_off_boresight_is_zenith_referenced_when_sensor_is_lower(self) -> None:
        """V2's reference axis flips with the altitude ordering, so the same
        number entered through V1 and V2 must describe the same scene."""
        angle = 0.45
        v1 = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__path_zenith_rad=angle,
            )
        )
        v2 = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__sensor_off_boresight_rad=angle,
            )
        )
        assert v2.theta_o_rad == pytest.approx(v1.theta_o_rad, rel=1e-12)
        assert v2.mode.startswith("geometry.sensor_off_boresight_rad")

    def test_v4_elevation_is_read_at_the_sensor(self) -> None:
        elev = math.radians(35.0)
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__elevation_angle_rad=elev,
            )
        )
        expected = solve_from_lower_zenith(math.pi / 2.0 - elev, 0.0, 20_000.0)
        assert v.theta_o_rad == pytest.approx(expected.theta_o_rad, rel=1e-12)

    def test_v3_ground_range_round_trips(self) -> None:
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__ground_range_m=15_000.0,
            )
        )
        assert v.direction == "up"
        assert v.ground_range_m == pytest.approx(15_000.0, rel=1e-6)

    def test_redundant_up_looking_entries_agree(self) -> None:
        zeta = 0.6
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__path_zenith_rad=zeta,
                geometry__elevation_angle_rad=math.pi / 2.0 - zeta,
            )
        )
        assert "consistent" in v.mode
        assert v.theta_o_rad > math.pi / 2.0

    def test_disagreeing_up_looking_entries_raise(self) -> None:
        with pytest.raises(GeometrySpecificationError):
            resolve_viewing(
                uplooking_params(
                    geometry__target_altitude_m=20_000.0,
                    geometry__path_zenith_rad=0.2,
                    geometry__elevation_angle_rad=0.2,
                )
            )

    def test_geometry_identity_eta_equals_pi_minus_lower_zenith(self) -> None:
        """η at the upper endpoint and ζ at the lower one are supplements of
        each other's roles: R_E·(θ_o − η) is the same arc either way."""
        zeta = 0.9
        h_tgt = 100_000.0
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=h_tgt,
                geometry__path_zenith_rad=zeta,
            )
        )
        sol = solve_from_lower_zenith(zeta, 0.0, h_tgt)
        assert v.eta_rad == pytest.approx(math.pi - zeta, rel=1e-9)
        assert v.ground_range_m == pytest.approx(R_EARTH_M * sol.central_angle_rad, rel=1e-9)


class TestLevelViewing:
    """Equal altitudes — the horizontal solution that retires the carve-out."""

    def _level(self, h_m: float, **inputs: object) -> ParameterSet:
        ps = ParameterSet(list(ALL_PARAMETERS))
        ps.set("geometry.sensor_altitude_m", h_m)
        ps.set("geometry.target_altitude_m", h_m)
        for name, value in inputs.items():
            ps.set(name.replace("__", "."), value)
        ps.resolve()
        return ps

    def test_coincident_endpoints_have_no_triangle(self) -> None:
        v = resolve_viewing(self._level(0.0))
        assert v.direction == "level"
        assert v.theta_o_rad == pytest.approx(math.pi / 2.0, abs=1e-15)
        assert v.eta_rad is None and v.slant_range_m is None and v.ground_range_m is None
        assert "coincident endpoints" in v.mode

    def test_chord_builds_the_triangle(self) -> None:
        v = resolve_viewing(self._level(0.0, geometry__target_range_m=5.0))
        assert v.slant_range_m == pytest.approx(5.0, rel=1e-9)
        assert v.theta_o_rad == pytest.approx(
            level_theta_o_from_central_angle_rad(level_central_angle_from_slant_m(5.0, 0.0)),
            rel=1e-15,
        )
        assert "chord" in v.mode

    def test_ground_arc_builds_the_triangle(self) -> None:
        v = resolve_viewing(self._level(30.0, geometry__ground_range_m=8_000.0))
        assert v.slant_range_m == pytest.approx(8_000.0, rel=1e-4)
        assert v.ground_range_m == pytest.approx(8_000.0, rel=1e-9)
        # Isoceles triangle: each endpoint looks *down* at the other by φ/2.
        phi = 8_000.0 / R_EARTH_M
        assert v.theta_o_rad == pytest.approx(math.pi / 2.0 + phi / 2.0, rel=1e-12)
        assert v.eta_rad == pytest.approx(math.pi - v.theta_o_rad, rel=1e-9)

    def test_negative_elevation_is_the_level_door(self) -> None:
        """A level arm sags below the horizontal, so its elevation entry is
        negative — legal since ADR-0011, rejected by the old 0.5° floor."""
        phi = 8_000.0 / R_EARTH_M
        v = resolve_viewing(self._level(30.0, geometry__elevation_angle_rad=-phi / 2.0))
        assert v.theta_o_rad == pytest.approx(math.pi / 2.0 + phi / 2.0, rel=1e-12)
        assert v.ground_range_m == pytest.approx(8_000.0, rel=1e-6)


class TestHemisphereInvariant:
    """h_sensor > h_target ⟺ θ_o < π/2 — a violating pair is a bad input."""

    def test_down_looking_with_obtuse_zenith_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="hemisphere"):
            resolve_viewing(make_params(geometry__path_zenith_rad=2.0))

    def test_error_names_both_altitudes(self) -> None:
        with pytest.raises(ParameterBoundsError) as exc:
            resolve_viewing(
                make_params(
                    geometry__target_altitude_m=1000.0,
                    geometry__path_zenith_rad=2.0,
                )
            )
        msg = str(exc.value)
        assert "h_sensor_m" in msg and "h_target_m" in msg

    def test_up_looking_pair_cannot_take_an_acute_target_zenith(self) -> None:
        """V3 is the one door that names θ_o-space directly; an arc of zero
        on an up-looking pair is θ_o = π, never θ_o = 0."""
        v = resolve_viewing(
            uplooking_params(
                geometry__target_altitude_m=20_000.0,
                geometry__ground_range_m=0.0,
            )
        )
        assert v.theta_o_rad == pytest.approx(math.pi, abs=1e-12)


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
        assert k.ground_speed_m_s == pytest.approx(250.0, rel=1e-9)
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


class TestOffBoresightDeprecatedAlias:
    """CU-247 — the rename must not break a single saved config or script."""

    def test_old_dotpath_still_sets_the_parameter(self) -> None:
        """`geometry.sensor_off_nadir_rad` warn-and-redirects to the new name."""
        params = ParameterSet(list(ALL_PARAMETERS))
        params.set("geometry.sensor_altitude_m", 500_000.0)
        with pytest.warns(DeprecationWarning, match="sensor_off_nadir_rad"):
            params.set("geometry.sensor_off_nadir_rad", 0.25)
        params.resolve()
        assert params.get("geometry.sensor_off_boresight_rad") == pytest.approx(0.25)

    def test_old_and_new_names_are_one_parameter(self) -> None:
        """Not two doors: the alias is the same slot, so mode detection sees one entry."""
        params = ParameterSet(list(ALL_PARAMETERS))
        params.set("geometry.sensor_altitude_m", 500_000.0)
        params.set("geometry.sensor_off_boresight_rad", 0.3)
        params.resolve()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert params.get("geometry.sensor_off_nadir_rad") == pytest.approx(0.3)
