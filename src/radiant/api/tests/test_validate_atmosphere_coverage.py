"""``Sensor.validate_atmosphere_coverage`` and the family catalogue seam (CU-239).

The resolve-time seam must reject exactly what ``evaluate()`` rejects, with the
same text, and must be a no-op for every configuration ``evaluate()`` accepts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radiant.api import (
    Sensor,
    shipped_atmosphere_families,
    shipped_family_for_axes,
    suggested_interpolation_axes,
)
from radiant.atmosphere.errors import AtmosphereCapabilityError, AtmosphereValidationError
from radiant.atmosphere.interpolation_coverage import SHIPPED_FAMILIES

# A LEO nadir stare at a sub-pixel target — the CU-239 operator scenario,
# trimmed to the parameters the coverage check reads.
_BASE: dict[str, dict[str, Any]] = {
    "source": {
        "scene_type": "sub_pixel",
        "regime_override": "sub_pixel",
        "target": {"temperature": 900.0, "emissivity": 0.9, "fill_fraction": 0.05},
        "background": {"temperature": 250.0, "emissivity": 0.95},
    },
    "geometry": {
        "sensor_altitude_m": 500_000.0,
        "target_altitude_m": 20_000.0,
        "path_zenith_rad": 0.0,
        "target_range_m": 480_000.0,
        "target": {"projected_area_m2": 4.0},
    },
    "optics": {
        "aperture_diameter_m": 0.30,
        "focal_length_m": 1.2,
        "transmission_scalar": 0.80,
    },
    "detector": {"pixel_pitch_x_um": 20.0, "pixel_pitch_y_um": 20.0, "qe_value": 0.70},
    "spectral_integration": {
        "filter_min_um": 3.0,
        "filter_max_um": 5.0,
        "integration_time_s": 1.0e-5,
    },
    "atmosphere": {"model": "interpolated"},
}


def _config(**atmosphere: Any) -> dict[str, dict[str, Any]]:
    cfg: dict[str, dict[str, Any]] = {k: dict(v) for k, v in _BASE.items()}
    cfg["atmosphere"].update(atmosphere)
    return cfg


def test_default_axes_with_an_above_ground_target_is_rejected_at_the_door() -> None:
    """CU-239: the reproduction now fails at resolve time, not five stages in."""
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        Sensor.from_dict(_config()).validate_atmosphere_coverage()
    msg = str(excinfo.value)
    assert "geometry.target_altitude_m = 20000.0 m" in msg
    assert "sensor_altitude_m,target_altitude_m" in msg
    assert "midlat_summer_ladders" in msg
    assert "0-29 km" in msg


def test_the_seam_and_evaluate_reject_the_same_config_with_the_same_text() -> None:
    """Defence in depth, one grammar: the door text is the chain text."""
    seam = Sensor.from_dict(_config())
    with pytest.raises(AtmosphereCapabilityError) as seam_exc:
        seam.validate_atmosphere_coverage()
    run = Sensor.from_dict(_config())
    with pytest.raises(AtmosphereCapabilityError) as run_exc:
        run.evaluate()
    assert str(seam_exc.value) == str(run_exc.value)


def test_the_recommended_axes_from_the_error_makes_the_seam_pass() -> None:
    """The remedy the error prints is the remedy that works."""
    with pytest.raises(AtmosphereCapabilityError) as excinfo:
        Sensor.from_dict(_config()).validate_atmosphere_coverage()
    fixed = str(excinfo.value.context["suggested_axes"])
    Sensor.from_dict(_config(interpolation_axes=fixed)).validate_atmosphere_coverage()


def test_seam_is_a_noop_for_a_non_interpolated_model() -> None:
    Sensor.from_dict(_config(model="simple")).validate_atmosphere_coverage()


def test_unshipped_axes_without_a_directory_is_rejected() -> None:
    # Ground target, so the target-altitude rule stands down and the
    # family-reachability rule is the one under test.
    cfg = _config(interpolation_axes="solar_zenith_rad")
    cfg["geometry"]["target_altitude_m"] = 0.0
    sensor = Sensor.from_dict(cfg)
    with pytest.raises(AtmosphereValidationError) as excinfo:
        sensor.validate_atmosphere_coverage()
    assert "solar_zenith_rad" in str(excinfo.value)


def test_catalogue_accessor_exposes_every_shipped_family() -> None:
    families = shipped_atmosphere_families()
    assert len(families) >= 5
    names = {f.name for f in families}
    assert "midlat_summer_ladders" in names
    assert "midlat_summer_uplooking_ladder" in names
    for family in families:
        # Picker labels must be self-describing and unit-bearing.
        assert family.interpolation_axes
        assert "km" in family.coverage
        assert family.los_direction in {"down", "up"}


def test_family_lookup_accessor_is_direction_keyed() -> None:
    assert shipped_family_for_axes("down", "path_zenith_rad") is not None
    assert shipped_family_for_axes("up", "path_zenith_rad") is None


def test_suggested_axes_accessor_matches_the_scene() -> None:
    assert (
        suggested_interpolation_axes("down", 20_000.0, 0.0) == "sensor_altitude_m,target_altitude_m"
    )
    assert suggested_interpolation_axes("up", 5_000.0, 0.0) == "target_altitude_m"
    assert suggested_interpolation_axes("level", 0.0, 0.0) is None


def test_the_boost_ladder_is_reachable_by_name_from_the_catalogue() -> None:
    """Ex-CU-296: 24 committed runs no ``(direction, axes)`` key can select.

    ``midlat_summer_boost_ladder`` shares its signature with
    ``midlat_summer_ladders``, which owns it — so the row is published as
    ``explicit_dir_only`` (never in the loader's dispatch table) and carries the
    directory a caller must write. That is what lets a picker offer it by *name*.
    """
    by_name = {f.name: f for f in shipped_atmosphere_families()}
    boost = by_name["midlat_summer_boost_ladder"]

    assert boost.explicit_dir_only is True
    assert boost.bundled_dir.endswith("midlat_summer_boost_ladder")
    assert Path(boost.bundled_dir).is_dir()
    assert len(sorted(Path(boost.bundled_dir).glob("*.npz"))) == 24
    assert "0-100 km" in boost.coverage  # the boost band, units explicit

    # It is deliberately NOT selectable by axes: the same key still resolves to the
    # 0-29 km ladders, so no existing 2-axis result is re-baselined.
    selected = shipped_family_for_axes("down", boost.interpolation_axes)
    assert selected is not None
    assert selected.name == "midlat_summer_ladders"
    assert all(not f.explicit_dir_only for f in SHIPPED_FAMILIES)


def test_the_boost_ladder_directory_actually_loads_as_a_family() -> None:
    """Writing ``bundled_dir`` is a real remedy, not just a label (ex-CU-296)."""
    boost = next(f for f in shipped_atmosphere_families() if f.name == "midlat_summer_boost_ladder")
    cfg = _config(
        interpolation_axes=boost.interpolation_axes,
        interpolated_data_dir=boost.bundled_dir,
    )
    cfg["geometry"]["target_altitude_m"] = 50_000.0  # mid-boost, outside the 0-29 km ladders
    cfg["geometry"]["target_range_m"] = 450_000.0  # the nadir slant range for that pair
    sensor = Sensor.from_dict(cfg)
    sensor.validate_atmosphere_coverage()  # no raise

    result = sensor.evaluate()
    assert float(result.stage_outputs["atmosphere"]["tau_atm"].mean()) > 0.0


def test_suggested_family_seam_derives_the_family_from_the_scene() -> None:
    """``Sensor.suggested_atmosphere_family`` — the GUI picker's one API call."""
    sensor = Sensor.from_dict(_config())
    family = sensor.suggested_atmosphere_family()
    assert family is not None
    assert family.name == "midlat_summer_ladders"  # 20 km target, nadir, down-looking

    ground = _config()
    ground["geometry"]["target_altitude_m"] = 0.0
    ground["geometry"]["target_range_m"] = 500_000.0  # the nadir slant range for that pair
    ground_family = Sensor.from_dict(ground).suggested_atmosphere_family()
    assert ground_family is not None
    assert ground_family.name == "midlat_summer_sensor_ladder"

    # A recommendation only: nothing was written.
    assert Sensor.from_dict(_config()).get_input("atmosphere.interpolation_axes") == (
        "path_zenith_rad"
    )


def test_profile_warning_seam_fires_only_on_an_explicit_mismatch() -> None:
    """Adopting a family must never silently change the requested profile."""
    family = shipped_family_for_axes("down", "sensor_altitude_m,target_altitude_m")
    assert family is not None
    assert family.profile == "midlat_summer"

    # No explicit request: nothing to contradict.
    assert Sensor.from_dict(_config()).atmosphere_profile_change_warning(family) is None

    asked = Sensor.from_dict(_config(standard_atmosphere="tropical"))
    warning = asked.atmosphere_profile_change_warning(family)
    assert warning is not None
    assert "tropical" in warning
    assert "midlat_summer" in warning

    matching = Sensor.from_dict(_config(standard_atmosphere="midlat_summer"))
    assert matching.atmosphere_profile_change_warning(family) is None
