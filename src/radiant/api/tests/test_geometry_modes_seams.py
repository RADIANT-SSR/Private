"""Tests for the two CU-377 geometry-door seams on ``Sensor``.

``validate_geometry_modes`` refuses a second explicit door of one family at the
door (a provenance read — works on an incomplete configuration), and
``geometry_door_values`` reports what every door would carry under the resolved
scene, ``None`` where a door has no inverse or the scene cannot resolve.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor
from radiant.geometry import GeometrySpecificationError

_MWIR_YAML = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


class TestValidateGeometryModes:
    def test_example_config_passes(self) -> None:
        Sensor.load(_MWIR_YAML).validate_geometry_modes()

    def test_one_door_passes(self) -> None:
        s = Sensor.load(_MWIR_YAML)
        s.set("geometry.ground_range_m", 300_000.0)
        s.validate_geometry_modes()

    def test_second_viewing_door_is_refused(self) -> None:
        s = Sensor.load(_MWIR_YAML)
        s.set("geometry.path_zenith_rad", 0.3)
        s.set("geometry.ground_range_m", 300_000.0)
        with pytest.raises(GeometrySpecificationError) as info:
            s.validate_geometry_modes()
        assert set(info.value.context) == {"geometry.path_zenith_rad", "geometry.ground_range_m"}

    def test_runs_on_an_incomplete_configuration(self) -> None:
        s = Sensor()  # blank: required parameters unset, cannot resolve
        s.set("geometry.solar_zenith_rad", 0.8)
        s.validate_geometry_modes()
        s.set("geometry.solar_elevation_rad", 0.7)
        with pytest.raises(GeometrySpecificationError):
            s.validate_geometry_modes()

    def test_ltan_and_local_solar_time_are_refused(self) -> None:
        s = Sensor.load(_MWIR_YAML)
        s.set("geometry.ltan_h", 10.5)
        s.set("geometry.local_solar_time_h", 10.5)
        with pytest.raises(GeometrySpecificationError):
            s.validate_geometry_modes()


class TestGeometryDoorValues:
    def test_nadir_example_doors(self) -> None:
        s = Sensor.load(_MWIR_YAML)
        values = s.geometry_door_values()
        assert values["geometry.path_zenith_rad"] == pytest.approx(0.0, abs=1e-12)
        assert values["geometry.elevation_angle_rad"] == pytest.approx(math.pi / 2, abs=1e-12)
        assert values["geometry.target_range_m"] == pytest.approx(
            s.get("geometry.sensor_altitude_m"), rel=1e-12
        )

    def test_door_switch_reproduces_theta_o(self) -> None:
        """Set V1, read V3's door value, set V3 alone → the same θ_o (the seed contract)."""
        s = Sensor.load(_MWIR_YAML)
        s.set("geometry.path_zenith_rad", 0.4)
        theta_o = s.evaluate().stage_outputs["geometry"]["theta_o_rad"]
        ground = s.geometry_door_values()["geometry.ground_range_m"]
        assert ground is not None
        s.reset("geometry.path_zenith_rad")
        s.set("geometry.ground_range_m", float(ground))
        assert s.evaluate().stage_outputs["geometry"]["theta_o_rad"] == pytest.approx(
            theta_o, rel=1e-9
        )

    def test_unresolvable_configuration_reads_none(self) -> None:
        values = Sensor().geometry_door_values()
        assert values and all(v is None for v in values.values())

    def test_does_not_mutate_inputs(self) -> None:
        s = Sensor.load(_MWIR_YAML)
        before = dict(s.inputs())
        s.geometry_door_values()
        assert dict(s.inputs()) == before
