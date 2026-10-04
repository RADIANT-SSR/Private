"""The CU-393 advisory through a real chain evaluation.

The unit tests pin the predicate; this pins that the stage actually reaches the
observer class and the elevation's provenance. It lives here rather than beside the
unit tests because it needs the whole chain — `radiant.atmosphere` may not import
`radiant.api`, and the observer class arrives through ChainState from GeometryStage.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant import Sensor

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent

_MARKER = "site_elevation_m is still at its 0 m default"


def _ground_site_sensor(*, altitude_m: float) -> Sensor:
    """A minimal up-looking ground scene on the Hufnagel-Valley profile."""
    return Sensor.from_dict(
        {
            "source": {
                "scene_type": "extended",
                "target": {"temperature": 300.0, "emissivity": 0.95},
                "background": {"temperature": 295.0, "emissivity": 0.95},
            },
            "geometry": {
                "sensor_altitude_m": altitude_m,
                "target_altitude_m": 700_000.0,
                # Sensor BELOW target, so this is the sensor's own zenith angle with
                # 0 = target overhead (ADR-0011): 20 deg off the site zenith.
                "path_zenith_rad": 0.349,
            },
            "atmosphere": {"model": "simple", "cn2_profile": "hufnagel_valley"},
            "optics": {"aperture_diameter_m": 1.0, "focal_length_m": 10.0},
            "detector": {
                "pixel_pitch_x_um": 15.0,
                "pixel_pitch_y_um": 15.0,
                "qe_value": 0.8,
            },
            "spectral_integration": {
                "filter_min_um": 0.4,
                "filter_max_um": 0.9,
                "integration_time_s": 0.1,
            },
        },
        wavelength_points=24,
    )


def _advisory_fired(sensor: Sensor) -> bool:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Deliberately NOT guarded: a fixture that cannot evaluate is a broken test,
        # and swallowing that would make every assertion below vacuously pass.
        sensor.evaluate()
    return any(_MARKER in str(w.message) for w in caught)


@pytest.mark.integration
def test_a_high_ground_site_with_the_default_is_advised() -> None:
    """The CU-393 trap, through the chain: the stage reaches observer_class."""
    assert _advisory_fired(_ground_site_sensor(altitude_m=900.0))


@pytest.mark.integration
def test_declaring_the_terrain_silences_it() -> None:
    sensor = _ground_site_sensor(altitude_m=900.0)
    sensor.set("geometry.site_elevation_m", 900.0)
    assert not _advisory_fired(sensor)


@pytest.mark.integration
def test_an_explicit_zero_silences_it() -> None:
    """Provenance, not value — the user has answered the question."""
    sensor = _ground_site_sensor(altitude_m=900.0)
    sensor.set("geometry.site_elevation_m", 0.0)
    assert not _advisory_fired(sensor)


@pytest.mark.integration
def test_a_sea_level_ground_site_is_silent() -> None:
    assert not _advisory_fired(_ground_site_sensor(altitude_m=0.0))


@pytest.mark.integration
def test_scenario_10_3_no_longer_trips_it() -> None:
    """The scenario that found the defect now declares its terrain."""
    yaml_path = (
        _REPO
        / "scenarios"
        / "10_direction_general"
        / "10.3_ground_to_space_sst_visible"
        / "inputs"
        / "10.3_ground_to_space_sst_visible.gui.yaml"
    )
    assert not _advisory_fired(Sensor.load(yaml_path))
