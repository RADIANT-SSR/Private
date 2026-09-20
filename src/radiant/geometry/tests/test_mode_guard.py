"""Level 0 tests for :mod:`radiant.geometry.mode_guard` (CU-377 F-05 / F-25).

The guard is a pure provenance read: one explicit door per family passes,
two explicit doors of one family raise a ``GeometrySpecificationError`` whose
context names both parameters (so the GUI locator tints the right family), and
the S3 site-and-time door's two hour-angle entries are exclusive. It works on
an unresolved set too — the seam runs at the door, before any resolve.
"""

from __future__ import annotations

import pytest

from radiant.core.parameters import ParameterSet
from radiant.geometry._schema import ALL_PARAMETERS
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.mode_guard import validate_mode_doors


def make_params(*, resolve: bool = True, **inputs: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    ps.set("geometry.sensor_altitude_m", 500_000.0)
    for name, value in inputs.items():
        ps.set(name.replace("__", "."), value)
    if resolve:
        ps.resolve()
    return ps


class TestClean:
    def test_nothing_set_passes(self) -> None:
        validate_mode_doors(make_params())

    def test_one_door_per_family_passes(self) -> None:
        validate_mode_doors(
            make_params(
                geometry__ground_range_m=100_000.0,
                geometry__solar_elevation_rad=0.9,
                geometry__circular_orbit=True,
                geometry__los_angular_rate_rad_s=0.01,
            )
        )

    def test_s3_door_with_several_of_its_fields_passes(self) -> None:
        validate_mode_doors(
            make_params(
                geometry__site_latitude_rad=0.5,
                geometry__day_of_year=100,
                geometry__local_solar_time_h=10.0,
            )
        )

    def test_anchors_are_not_doors(self) -> None:
        validate_mode_doors(
            make_params(geometry__target_altitude_m=100.0, geometry__solar_azimuth_rad=1.0)
        )

    def test_unresolved_set_is_readable(self) -> None:
        validate_mode_doors(make_params(resolve=False, geometry__path_zenith_rad=0.3))


class TestConflicts:
    def test_two_viewing_doors_raise_naming_both(self) -> None:
        ps = make_params(geometry__path_zenith_rad=0.3, geometry__ground_range_m=300_000.0)
        with pytest.raises(GeometrySpecificationError) as info:
            validate_mode_doors(ps)
        exc = info.value
        assert "geometry.path_zenith_rad" in exc.context
        assert "geometry.ground_range_m" in exc.context
        assert "viewing" in str(exc.what).lower()
        assert "selector" in str(exc.action).lower()

    def test_consistent_pair_is_still_two_doors(self) -> None:
        """Evaluate tolerates an agreeing pair (ADR-0006 rule 2); the door seam
        does not — one door per family is the GUI contract (CU-377)."""
        ps = make_params(geometry__path_zenith_rad=0.0, geometry__sensor_off_boresight_rad=0.0)
        with pytest.raises(GeometrySpecificationError):
            validate_mode_doors(ps)

    def test_direct_range_and_an_angle_raise(self) -> None:
        ps = make_params(geometry__target_range_m=600_000.0, geometry__elevation_angle_rad=1.0)
        with pytest.raises(GeometrySpecificationError) as info:
            validate_mode_doors(ps)
        assert "geometry.target_range_m" in info.value.context

    def test_two_solar_doors_raise(self) -> None:
        ps = make_params(geometry__solar_zenith_rad=0.8, geometry__solar_elevation_rad=0.7)
        with pytest.raises(GeometrySpecificationError) as info:
            validate_mode_doors(ps)
        assert "solar" in str(info.value.what).lower()

    def test_ltan_and_local_solar_time_raise(self) -> None:
        ps = make_params(geometry__ltan_h=10.5, geometry__local_solar_time_h=10.5)
        with pytest.raises(GeometrySpecificationError) as info:
            validate_mode_doors(ps)
        assert "geometry.ltan_h" in info.value.context
        assert "geometry.local_solar_time_h" in info.value.context

    def test_two_los_rate_doors_raise(self) -> None:
        ps = make_params(geometry__los_angular_rate_rad_s=0.01, geometry__target_speed_m_s=10.0)
        with pytest.raises(GeometrySpecificationError):
            validate_mode_doors(ps)

    def test_unresolved_conflict_is_caught_before_resolve(self) -> None:
        ps = make_params(
            resolve=False, geometry__path_zenith_rad=0.3, geometry__ground_range_m=300_000.0
        )
        with pytest.raises(GeometrySpecificationError):
            validate_mode_doors(ps)
