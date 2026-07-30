"""Config-time coverage check for the interpolated backend (CU-239).

Level 0/1: the catalogue is pinned against the shipped NPZ node values, and the
scene ↔ axes rule is exercised on matching and mismatching pairs.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere import _schema as atm_schema
from radiant.atmosphere.errors import AtmosphereCapabilityError, AtmosphereValidationError
from radiant.atmosphere.interpolation_coverage import (
    SHIPPED_FAMILIES,
    check_interpolation_coverage,
    family_for,
    normalize_axes,
    profile_change_warning,
    recommended_axes,
    shipped_family_catalogue_text,
)
from radiant.atmosphere.loaders import _SHIPPED_FAMILY_BY_DIRECTION_AND_AXES
from radiant.core.parameters import ParameterSet
from radiant.geometry import _schema as geom_schema

_ATMOSPHERES_DIR = Path(__file__).resolve().parents[2] / "data" / "tables" / "atmospheres"


def _params(**overrides: object) -> ParameterSet:
    """A resolved set carrying just the geometry + atmosphere the check reads."""
    ps = ParameterSet(list(geom_schema.ALL_PARAMETERS + atm_schema.ALL_PARAMETERS), [])
    ps.set("atmosphere.model", "interpolated")
    ps.set("geometry.sensor_altitude_m", 500_000.0)
    ps.set("geometry.target_altitude_m", 0.0)
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


# ---------------------------------------------------------------------------
# Catalogue integrity
# ---------------------------------------------------------------------------


def test_loader_dispatch_table_is_derived_from_the_catalogue() -> None:
    """One authority (Rule 27): the loader table is exactly the catalogue rows."""
    assert {
        (f.los_direction, f.interpolation_axes): f.name for f in SHIPPED_FAMILIES
    } == _SHIPPED_FAMILY_BY_DIRECTION_AND_AXES
    assert len(_SHIPPED_FAMILY_BY_DIRECTION_AND_AXES) == len(SHIPPED_FAMILIES)


def test_every_catalogued_family_ships_with_at_least_two_runs() -> None:
    for family in SHIPPED_FAMILIES:
        runs = sorted((_ATMOSPHERES_DIR / family.name).glob("*.npz"))
        assert len(runs) >= 2, f"{family.name} has {len(runs)} NPZ runs"


def test_catalogued_axes_match_the_npz_geometry_coordinates() -> None:
    """The axes string a row advertises is one the family's runs actually vary."""
    for family in SHIPPED_FAMILIES:
        coords: list[dict[str, float]] = []
        for npz in sorted((_ATMOSPHERES_DIR / family.name).glob("*.npz")):
            with np.load(npz, allow_pickle=True) as data:
                raw = data["geometry"]
                coords.append(raw.item() if hasattr(raw, "item") else json.loads(str(raw)))
        for axis in family.interpolation_axes.split(","):
            values = {c[axis] for c in coords if axis in c}
            assert len(values) >= 2, f"{family.name} does not vary '{axis}': {values}"


def test_coverage_lines_state_their_units() -> None:
    """Owner rule: every number an operator reads carries its unit."""
    for family in SHIPPED_FAMILIES:
        assert "km" in family.coverage, family.coverage
        assert "degrees" in family.coverage, family.coverage
        assert family.interpolation_axes in family.summary
        assert family.name in family.summary


def test_catalogue_text_lists_every_row() -> None:
    text = shipped_family_catalogue_text()
    for family in SHIPPED_FAMILIES:
        assert family.name in text
        assert family.interpolation_axes in text


def test_normalize_axes_strips_whitespace_and_keeps_order() -> None:
    assert normalize_axes(" sensor_altitude_m , target_altitude_m ") == (
        "sensor_altitude_m,target_altitude_m"
    )
    # Order is part of the key, not incidental.
    assert normalize_axes("target_altitude_m,sensor_altitude_m") != (
        "sensor_altitude_m,target_altitude_m"
    )


def test_family_for_is_direction_keyed() -> None:
    assert family_for("down", "path_zenith_rad") is not None
    assert family_for("up", "path_zenith_rad") is None
    up = family_for("up", "target_altitude_m")
    assert up is not None and up.name == "midlat_summer_uplooking_ladder"
    assert family_for("down", "target_altitude_m") is None


# ---------------------------------------------------------------------------
# Scene-aware recommendation (layer 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "h_tgt_m", "theta_o_rad", "expected"),
    [
        ("down", 20_000.0, 0.0, "sensor_altitude_m,target_altitude_m"),
        ("down", 20_000.0, 0.5, "sensor_altitude_m,target_altitude_m,path_zenith_rad"),
        ("down", 0.0, 0.0, "sensor_altitude_m"),
        ("down", 0.0, 0.5, "path_zenith_rad"),
        ("up", 5_000.0, 0.0, "target_altitude_m"),
        ("level", 0.0, 0.0, None),
    ],
)
def test_recommended_axes_is_covered_by_a_shipped_family(
    direction: str, h_tgt_m: float, theta_o_rad: float, expected: str | None
) -> None:
    got = recommended_axes(direction, h_tgt_m, theta_o_rad)
    assert got == expected
    if got is not None:
        assert family_for(direction, got) is not None, f"{direction}/{got} is not shipped"


# ---------------------------------------------------------------------------
# The coverage check — matching pairs are silent
# ---------------------------------------------------------------------------


def test_non_interpolated_model_is_a_noop() -> None:
    check_interpolation_coverage(_params(atmosphere__model="simple"))


def test_ground_target_with_default_axes_is_accepted() -> None:
    """The historical default (path_zenith_rad, h_tgt = 0) still passes."""
    check_interpolation_coverage(_params())


@pytest.mark.parametrize("family", SHIPPED_FAMILIES, ids=lambda f: f.name)
def test_every_shipped_family_passes_a_scene_it_covers(family: object) -> None:
    assert isinstance(family, type(SHIPPED_FAMILIES[0]))
    if family.los_direction == "up":
        ps = _params(
            geometry__sensor_altitude_m=0.0,
            geometry__target_altitude_m=10_000.0,
            atmosphere__interpolation_axes=family.interpolation_axes,
        )
    else:
        h_tgt = 20_000.0 if "target_altitude_m" in family.interpolation_axes else 0.0
        ps = _params(
            geometry__target_altitude_m=h_tgt,
            atmosphere__interpolation_axes=family.interpolation_axes,
        )
    check_interpolation_coverage(ps)


def test_whitespace_in_the_axes_string_is_tolerated() -> None:
    check_interpolation_coverage(
        _params(
            geometry__target_altitude_m=20_000.0,
            atmosphere__interpolation_axes="sensor_altitude_m , target_altitude_m",
        )
    )


def test_explicit_data_dir_bypasses_the_family_reachability_rule() -> None:
    """An unshipped axes combination is legal with a directory of your own."""
    check_interpolation_coverage(
        _params(
            atmosphere__interpolation_axes="solar_zenith_rad",
            atmosphere__interpolated_data_dir="/somewhere/of/my/own",
        )
    )


# ---------------------------------------------------------------------------
# The coverage check — mismatching pairs are refused at the door
# ---------------------------------------------------------------------------


def test_above_ground_target_without_a_target_axis_is_refused() -> None:
    """CU-239's reproduction: LEO nadir → 20 km target, default axes."""
    ps = _params(geometry__target_altitude_m=20_000.0)
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        check_interpolation_coverage(ps)
    msg = str(excinfo.value)
    # Names the offending value, the axis, and the exact remedy string.
    assert "geometry.target_altitude_m = 20000.0 m" in msg
    assert "'path_zenith_rad'" in msg
    assert "sensor_altitude_m,target_altitude_m" in msg
    assert "midlat_summer_ladders" in msg
    # Coverage prose with units travels with the remedy.
    assert "0-29 km" in msg
    assert excinfo.value.context["suggested_axes"] == "sensor_altitude_m,target_altitude_m"
    assert excinfo.value.context["suggested_family"] == "midlat_summer_ladders"


def test_off_nadir_above_ground_target_is_pointed_at_the_three_axis_family() -> None:
    ps = _params(geometry__target_altitude_m=20_000.0, geometry__path_zenith_rad=0.7)
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        check_interpolation_coverage(ps)
    assert (
        excinfo.value.context["suggested_axes"]
        == "sensor_altitude_m,target_altitude_m,path_zenith_rad"
    )
    assert "midlat_summer_boost_offnadir" in str(excinfo.value)


def test_unshipped_axes_with_no_data_dir_names_the_whole_catalogue() -> None:
    ps = _params(atmosphere__interpolation_axes="solar_zenith_rad")
    with pytest.raises(AtmosphereValidationError) as excinfo:
        check_interpolation_coverage(ps)
    msg = str(excinfo.value)
    assert "solar_zenith_rad" in msg
    for family in SHIPPED_FAMILIES:
        assert family.name in msg
    assert "Action:" in msg


def test_up_looking_scene_with_down_looking_axes_is_refused() -> None:
    """Direction is part of the key: a down-looking axes string is unreachable up."""
    ps = _params(geometry__sensor_altitude_m=0.0, geometry__target_altitude_m=10_000.0)
    with pytest.raises(AtmosphereValidationError) as excinfo:
        check_interpolation_coverage(ps)
    assert "up-looking" in str(excinfo.value)
    assert "target_altitude_m" in str(excinfo.value)


def test_missing_geometry_schema_is_a_noop() -> None:
    """Partial-chain fixtures without geometry registered are not second-guessed."""
    ps = ParameterSet(list(atm_schema.ALL_PARAMETERS), [])
    ps.set("atmosphere.model", "interpolated")
    ps.resolve()
    check_interpolation_coverage(ps)


# ---------------------------------------------------------------------------
# Profile safety: adopting a family must never silently change the profile
# ---------------------------------------------------------------------------


def test_profile_change_warning_is_silent_when_the_profile_was_never_asked_for() -> None:
    ladders = family_for("down", "sensor_altitude_m,target_altitude_m")
    assert ladders is not None
    assert profile_change_warning(_params(), ladders) is None


def test_profile_change_warning_is_silent_when_the_profiles_agree() -> None:
    ladders = family_for("down", "sensor_altitude_m,target_altitude_m")
    assert ladders is not None
    ps = _params(atmosphere__standard_atmosphere="midlat_summer")
    assert profile_change_warning(ps, ladders) is None


def test_profile_change_warning_fires_on_a_conflicting_explicit_profile() -> None:
    ladders = family_for("down", "sensor_altitude_m,target_altitude_m")
    assert ladders is not None
    ps = _params(atmosphere__standard_atmosphere="tropical")
    warning = profile_change_warning(ps, ladders)
    assert warning is not None
    assert "midlat_summer" in warning
    assert "tropical" in warning
    assert "interpolated_data_dir" in warning


def test_coverage_error_carries_the_profile_caveat() -> None:
    """The remedy never silently swaps the operator's requested profile."""
    ps = _params(
        geometry__target_altitude_m=20_000.0,
        atmosphere__standard_atmosphere="tropical",
    )
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        check_interpolation_coverage(ps)
    msg = str(excinfo.value)
    assert "changes the atmosphere profile" in msg
    assert "tropical" in msg


def test_profile_caveat_is_omitted_when_the_operator_brings_their_own_dir() -> None:
    """With an explicit dir, no shipped family is being adopted — no caveat."""
    ps = _params(
        geometry__target_altitude_m=20_000.0,
        atmosphere__standard_atmosphere="tropical",
        atmosphere__interpolated_data_dir="/somewhere/of/my/own",
    )
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        check_interpolation_coverage(ps)
    assert "changes the atmosphere profile" not in str(excinfo.value)
