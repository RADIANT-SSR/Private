"""Tests for radiant.atmosphere.exo.

Exo-atmosphere is a one-line model — these tests verify the trivial
contract holds at any geometry, on any wavelength grid, and that the
``AtmosphericState`` invariants are honoured.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.protocol import (
    Atmosphere,
    AtmosphericGeometry,
    AtmosphericState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _grid_vis_to_lwir() -> np.ndarray:
    return np.linspace(0.4, 14.0, 137)


def _ground_geometry() -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=500_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=math.radians(20.0),
    )


def _space_geometry() -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=600_000.0,
        target_altitude_m=600_000.0,
        path_zenith_rad=0.0,
        observer_type="space",
        target_type="space",
    )


# ---------------------------------------------------------------------------
# Protocol conformance and trivial contract
# ---------------------------------------------------------------------------


def test_exo_atmosphere_implements_protocol() -> None:
    src = ExoAtmosphere()
    assert isinstance(src, Atmosphere)


def test_exo_returns_unity_transmittance_and_zero_radiance() -> None:
    atm = ExoAtmosphere()
    state = atm.build_state(_grid_vis_to_lwir(), _ground_geometry())
    assert isinstance(state, AtmosphericState)
    assert np.allclose(state.transmittance.values, 1.0, atol=0.0)
    assert np.allclose(state.path_radiance.values, 0.0, atol=0.0)
    assert np.allclose(state.atm_emission_down.values, 0.0, atol=0.0)


def test_exo_units_are_correct() -> None:
    state = ExoAtmosphere().build_state(_grid_vis_to_lwir(), _ground_geometry())
    assert state.transmittance.unit == ""
    assert state.path_radiance.unit == "W/m²/sr/µm"
    assert state.atm_emission_down.unit == "W/m²/sr/µm"


def test_exo_geometry_passthrough() -> None:
    geo = _ground_geometry()
    state = ExoAtmosphere().build_state(_grid_vis_to_lwir(), geo)
    assert state.geometry is geo
    # Slant path > 0 for a downlooking ground geometry; air mass ≥ 1.
    assert state.slant_path_length_m > 0.0
    assert state.air_mass >= 1.0


def test_exo_space_to_space_zero_slant_air_mass_one() -> None:
    state = ExoAtmosphere().build_state(_grid_vis_to_lwir(), _space_geometry())
    # Δh = 0 ⇒ slant = 0 ⇒ air_mass conventionally 1.
    assert state.slant_path_length_m == pytest.approx(0.0, abs=1e-12)
    assert state.air_mass == pytest.approx(1.0, abs=1e-12)
    assert np.all(state.transmittance.values == 1.0)


def test_exo_works_on_arbitrary_grid() -> None:
    grid = np.array([0.5, 1.0, 2.0, 5.0, 10.0, 12.0])
    state = ExoAtmosphere().build_state(grid, _ground_geometry())
    assert state.transmittance.values.shape == grid.shape
    assert np.array_equal(state.wavelength_um, grid)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_exo_rejects_non_ascending_grid() -> None:
    grid = np.array([1.0, 0.5, 2.0])
    with pytest.raises(ValueError, match="ascending"):
        ExoAtmosphere().build_state(grid, _ground_geometry())


def test_exo_rejects_non_positive_grid() -> None:
    grid = np.array([0.0, 1.0, 2.0])
    with pytest.raises(ValueError, match="positive"):
        ExoAtmosphere().build_state(grid, _ground_geometry())


def test_exo_rejects_2d_grid() -> None:
    grid = np.ones((4, 4))
    with pytest.raises(ValueError, match="1-D"):
        ExoAtmosphere().build_state(grid, _ground_geometry())


def test_exo_rejects_single_sample_grid() -> None:
    with pytest.raises(ValueError, match="at least"):
        ExoAtmosphere().build_state(np.array([1.0]), _ground_geometry())
