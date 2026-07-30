"""``Sensor.validate_atmosphere_coverage`` and the family catalogue seam (CU-239).

The resolve-time seam must reject exactly what ``evaluate()`` rejects, with the
same text, and must be a no-op for every configuration ``evaluate()`` accepts.
"""

from __future__ import annotations

from typing import Any

import pytest

from radiant.api import (
    Sensor,
    shipped_atmosphere_families,
    shipped_family_for_axes,
    suggested_interpolation_axes,
)
from radiant.atmosphere.errors import AtmosphereCapabilityError, AtmosphereValidationError

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
