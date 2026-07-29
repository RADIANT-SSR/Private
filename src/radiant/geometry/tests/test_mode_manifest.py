"""Drift tests — the mode manifest states what the resolvers execute (CU-120).

:mod:`radiant.geometry.mode_manifest` is hand-maintained data describing the
ADR-0006 family → mode → parameter structure. These tests are the reason it
cannot drift silently:

* **schema coverage** — the manifest names exactly the ``geometry.*`` input-mode
  parameters (the ``geometry.target.*`` extent params are rendered by the GUI's
  target-shape panel, not the mode forms, and are excluded);
* **tag reconciliation** — the manifest's non-default doors agree with the
  ``mode_entry`` tags in ``_schema.py`` (and S3 with ``solar_site``);
* **per-mode round-trip** — setting exactly one mode's parameter(s) makes the
  corresponding ``resolve_*`` select that door and :func:`active_mode_key`
  report that mode key.
"""

from __future__ import annotations

from typing import Any

import pytest

from radiant.core.parameters import ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.mode_manifest import (
    KINEMATICS_FAMILY,
    LOS_RATE_FAMILY,
    MODE_FAMILIES,
    SOLAR_FAMILY,
    VIEWING_FAMILY,
    GeometryModeFamily,
    active_mode_key,
    all_mode_params,
)
from radiant.geometry.modes import (
    _provided,
    resolve_kinematics,
    resolve_los_rate,
    resolve_solar,
    resolve_viewing,
)

H_LEO = 500_000.0

#: ``geometry.*`` parameters that are deliberately not mode doors.
_NON_MODE_PARAMS = frozenset({"geometry.scene_class"})


def make_params(**inputs: object) -> ParameterSet:
    """Geometry-only ParameterSet with sensor altitude anchored (as test_modes)."""
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", H_LEO)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _active(family: GeometryModeFamily, ps: ParameterSet) -> str:
    """active_mode_key over a resolved ParameterSet's provenance."""

    def is_provided(dotpath: str) -> bool:
        return _provided(ps, dotpath)

    def get_value(dotpath: str) -> Any:
        return ps.get(dotpath)

    return active_mode_key(family, is_provided, get_value)


# ---------------------------------------------------------------------------
# Manifest ↔ schema
# ---------------------------------------------------------------------------


class TestManifestSchemaAgreement:
    def test_manifest_covers_every_input_mode_parameter(self) -> None:
        """The manifest names exactly the ``geometry.*`` input-mode parameters.

        Two documented exclusions: the ``geometry.target.*`` extent params
        (rendered by the GUI target-shape panel, not the mode forms) and
        ``geometry.scene_class`` — an optional *assertion* validated against
        the derivation (ADR-0011 decision 8), not a door onto a canonical
        quantity, so it belongs to no mode family.
        """
        schema_geometry = {
            d.name
            for d in ALL_PARAMETERS
            if d.name.startswith("geometry.")
            and not d.name.startswith("geometry.target.")
            and d.name not in _NON_MODE_PARAMS
        }
        assert set(all_mode_params()) == schema_geometry
        assert len(all_mode_params()) == len(schema_geometry)  # no duplicates

    def test_mode_entry_tags_reconcile_with_manifest(self) -> None:
        """`mode_entry` tags = the manifest's non-default doors (V0 excepted).

        ``geometry.target_range_m`` (V0) is a dual-purpose parameter — it also
        names the regime/detection slant range (tags ``geometry`` + ``target``)
        — so it deliberately carries no ``mode_entry`` tag; every other
        non-default door does, and no default door or anchor is tagged.
        """
        tagged = {d.name for d in ALL_PARAMETERS if "mode_entry" in d.tags}
        non_default_doors = {
            p
            for family in MODE_FAMILIES
            for mode in family.modes
            if mode.key != family.default_mode_key
            for p in mode.params
        }
        assert tagged == non_default_doors - {"geometry.target_range_m"}

    def test_solar_site_tags_are_the_s3_door(self) -> None:
        """`solar_site` tags = exactly the S3 mode's parameters."""
        tagged = {d.name for d in ALL_PARAMETERS if "solar_site" in d.tags}
        (s3,) = [m for m in SOLAR_FAMILY.modes if m.key == "S3"]
        assert tagged == set(s3.params)

    def test_families_are_the_stage_output_families(self) -> None:
        assert tuple(f.key for f in MODE_FAMILIES) == (
            "viewing",
            "solar",
            "kinematics",
            "los_rate",
        )

    def test_default_mode_keys_exist_in_their_family(self) -> None:
        for family in MODE_FAMILIES:
            assert family.default_mode_key in {m.key for m in family.modes}


# ---------------------------------------------------------------------------
# Manifest ↔ resolvers (per-mode round-trip)
# ---------------------------------------------------------------------------


class TestViewingRoundTrip:
    def test_default_door_is_v1(self) -> None:
        ps = make_params()
        assert "default" in resolve_viewing(ps).mode
        assert _active(VIEWING_FAMILY, ps) == "V1"

    def test_v1_path_zenith(self) -> None:
        ps = make_params(geometry__path_zenith_rad=0.6)
        assert resolve_viewing(ps).mode == "geometry.path_zenith_rad"
        assert _active(VIEWING_FAMILY, ps) == "V1"

    def test_v2_off_nadir(self) -> None:
        ps = make_params(geometry__sensor_off_boresight_rad=0.3)
        assert resolve_viewing(ps).mode == "geometry.sensor_off_boresight_rad"
        assert _active(VIEWING_FAMILY, ps) == "V2"

    def test_v3_ground_range(self) -> None:
        ps = make_params(geometry__ground_range_m=100_000.0)
        assert resolve_viewing(ps).mode == "geometry.ground_range_m"
        assert _active(VIEWING_FAMILY, ps) == "V3"

    def test_v4_elevation(self) -> None:
        ps = make_params(geometry__elevation_angle_rad=1.0)
        assert resolve_viewing(ps).mode == "geometry.elevation_angle_rad"
        assert _active(VIEWING_FAMILY, ps) == "V4"

    def test_v0_direct_range(self) -> None:
        """V0 is the range-only door: the viewing *triangle* resolves to the
        nadir default (the range drives regime/detection via
        ``check_range_consistency``, not ``resolve_viewing``), but the manifest
        detects V0 as the active door."""
        ps = make_params(geometry__target_range_m=600_000.0)
        assert "default" in resolve_viewing(ps).mode
        assert _active(VIEWING_FAMILY, ps) == "V0"


class TestSolarRoundTrip:
    def test_default_door_is_s1(self) -> None:
        ps = make_params()
        assert "default" in resolve_solar(ps).mode
        assert _active(SOLAR_FAMILY, ps) == "S1"

    def test_s1_solar_zenith(self) -> None:
        ps = make_params(geometry__solar_zenith_rad=0.4)
        assert resolve_solar(ps).mode == "geometry.solar_zenith_rad"
        assert _active(SOLAR_FAMILY, ps) == "S1"

    def test_s2_solar_elevation(self) -> None:
        ps = make_params(geometry__solar_elevation_rad=1.2)
        assert resolve_solar(ps).mode == "geometry.solar_elevation_rad"
        assert _active(SOLAR_FAMILY, ps) == "S2"

    def test_s3_site_time(self) -> None:
        ps = make_params(
            geometry__site_latitude_rad=0.6,
            geometry__day_of_year=172,
            geometry__local_solar_time_h=10.0,
        )
        assert resolve_solar(ps).mode == "site+time (S3)"
        assert _active(SOLAR_FAMILY, ps) == "S3"

    def test_s3_via_ltan(self) -> None:
        ps = make_params(geometry__site_latitude_rad=0.6, geometry__ltan_h=10.5)
        assert resolve_solar(ps).mode == "site+time (S3)"
        assert _active(SOLAR_FAMILY, ps) == "S3"

    def test_night_falls_back_to_default_door(self) -> None:
        """The manifest carries no ``night`` mode (night is the illumination
        anchor, not a door onto θ_s), so detection reports the default door."""
        ps = make_params(geometry__solar_illumination="night")
        assert resolve_solar(ps).mode == "night"
        assert _active(SOLAR_FAMILY, ps) == SOLAR_FAMILY.default_mode_key


class TestKinematicsRoundTrip:
    def test_direct_speed(self) -> None:
        ps = make_params(geometry__ground_speed_m_s=6_800.0)
        assert resolve_kinematics(ps).mode == "direct"
        assert _active(KINEMATICS_FAMILY, ps) == "direct"

    def test_circular_orbit(self) -> None:
        ps = make_params(geometry__circular_orbit=True)
        assert resolve_kinematics(ps).mode == "circular_orbit"
        assert _active(KINEMATICS_FAMILY, ps) == "circular"

    def test_default_is_direct(self) -> None:
        ps = make_params()
        assert resolve_kinematics(ps).mode == "direct"
        assert _active(KINEMATICS_FAMILY, ps) == "direct"


class TestLosRateRoundTrip:
    def test_default_door_is_k0_platform_only(self) -> None:
        ps = make_params()
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        assert resolve_los_rate(ps, viewing, kin).mode == "platform-only (derived)"
        assert _active(LOS_RATE_FAMILY, ps) == "K0"

    def test_k1_direct_rate(self) -> None:
        ps = make_params(geometry__los_angular_rate_rad_s=0.004)
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        resolved = resolve_los_rate(ps, viewing, kin)
        assert resolved.mode == "geometry.los_angular_rate_rad_s"
        assert resolved.los_angular_rate_rad_s == pytest.approx(0.004, rel=1e-12)
        assert _active(LOS_RATE_FAMILY, ps) == "K1"

    def test_k2_target_velocity(self) -> None:
        ps = make_params(geometry__target_speed_m_s=250.0)
        viewing = resolve_viewing(ps)
        kin = resolve_kinematics(ps)
        assert resolve_los_rate(ps, viewing, kin).mode == "target velocity (K2)"
        assert _active(LOS_RATE_FAMILY, ps) == "K2"

    def test_k2_detected_from_heading_alone(self) -> None:
        """Any member of the triple opens the K2 door (a zero speed warns)."""
        ps = make_params(geometry__target_heading_rad=0.5)
        assert _active(LOS_RATE_FAMILY, ps) == "K2"
