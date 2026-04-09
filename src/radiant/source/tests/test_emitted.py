"""Tests for :class:`radiant.source.emitted.ThermalSource`."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.source.emitted import ThermalSource
from radiant.source.protocol import SpectralRadianceSource


@pytest.mark.level0
def test_scalar_graybody_matches_epsilon_times_planck() -> None:
    """L(λ) = ε · B(λ, T) for scalar emissivity."""
    lam = np.linspace(3.0, 14.0, 200)
    src = ThermalSource(temperature_K=300.0, emissivity=0.8)
    L = src.spectral_radiance(lam)
    B = planck_spectral_radiance(lam, 300.0)
    assert np.allclose(L, 0.8 * B, rtol=0, atol=0)


@pytest.mark.level0
def test_epsilon_one_equals_blackbody() -> None:
    lam = np.linspace(0.4, 14.0, 100)
    src = ThermalSource(temperature_K=500.0, emissivity=1.0)
    L = src.spectral_radiance(lam)
    B = planck_spectral_radiance(lam, 500.0)
    assert np.array_equal(L, B)


@pytest.mark.level0
def test_epsilon_zero_gives_zero() -> None:
    lam = np.linspace(0.4, 14.0, 50)
    src = ThermalSource(temperature_K=500.0, emissivity=0.0)
    L = src.spectral_radiance(lam)
    assert np.all(L == 0.0)


@pytest.mark.level0
def test_spectral_emissivity() -> None:
    """Spectral ε(λ) is multiplied point-wise against B(λ, T)."""
    lam = np.linspace(3.0, 14.0, 50)
    # Linearly varying emissivity 0.5 → 1.0
    eps_values = np.linspace(0.5, 1.0, 50)
    eps = SpectralData(
        name="test_eps",
        wavelength_um=lam,
        values=eps_values,
        unit="",
        source="unit_test",
    )
    src = ThermalSource(temperature_K=300.0, emissivity=eps)
    L = src.spectral_radiance(lam)
    B = planck_spectral_radiance(lam, 300.0)
    assert np.allclose(L, eps_values * B)


@pytest.mark.level0
def test_spectral_emissivity_interpolates_to_request_grid() -> None:
    """Requesting an interior grid interpolates ε(λ) linearly."""
    eps_grid = np.linspace(3.0, 14.0, 50)
    eps_values = np.linspace(0.5, 1.0, 50)
    eps = SpectralData(
        name="eps",
        wavelength_um=eps_grid,
        values=eps_values,
        unit="",
        source="test",
    )
    src = ThermalSource(temperature_K=300.0, emissivity=eps)

    # Interior query grid with different sampling
    query = np.linspace(3.5, 13.5, 100)
    L = src.spectral_radiance(query)
    B = planck_spectral_radiance(query, 300.0)
    eps_interp = np.interp(query, eps_grid, eps_values)
    assert np.allclose(L, eps_interp * B)


@pytest.mark.level0
def test_spectral_emissivity_out_of_range_raises() -> None:
    eps = SpectralData(
        name="eps",
        wavelength_um=np.linspace(5.0, 10.0, 20),
        values=np.full(20, 0.9),
        unit="",
        source="test",
    )
    src = ThermalSource(temperature_K=300.0, emissivity=eps)
    with pytest.raises(ValueError, match="outside the emissivity table range"):
        src.spectral_radiance(np.linspace(3.0, 12.0, 10))


@pytest.mark.level0
def test_negative_temperature_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ThermalSource(temperature_K=-1.0, emissivity=0.9)


@pytest.mark.level0
def test_scalar_emissivity_out_of_bounds_raises() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        ThermalSource(temperature_K=300.0, emissivity=1.1)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        ThermalSource(temperature_K=300.0, emissivity=-0.01)


@pytest.mark.level0
def test_spectral_emissivity_out_of_bounds_raises() -> None:
    eps = SpectralData(
        name="bad",
        wavelength_um=np.linspace(1.0, 20.0, 10),
        values=np.array([0.9, 0.9, 1.2, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]),
        unit="",
        source="test",
    )
    with pytest.raises(ValueError, match=r"outside \[0, 1\]"):
        ThermalSource(temperature_K=300.0, emissivity=eps)


@pytest.mark.level0
def test_protocol_conformance() -> None:
    """ThermalSource satisfies the SpectralRadianceSource structural protocol."""
    src = ThermalSource(temperature_K=300.0, emissivity=0.9)
    assert isinstance(src, SpectralRadianceSource)


@pytest.mark.level0
def test_deterministic() -> None:
    lam = np.linspace(3.0, 14.0, 100)
    src = ThermalSource(temperature_K=300.0, emissivity=0.9)
    L1 = src.spectral_radiance(lam)
    L2 = src.spectral_radiance(lam)
    assert np.array_equal(L1, L2)


@pytest.mark.level0
def test_roundtrip_scalar() -> None:
    src = ThermalSource(temperature_K=295.0, emissivity=0.87, name="panel")
    d = src.to_dict()
    restored = ThermalSource.from_dict(d)
    assert restored == src


@pytest.mark.level0
def test_roundtrip_spectral() -> None:
    eps = SpectralData(
        name="eps_mwir",
        wavelength_um=np.linspace(3.0, 5.0, 21),
        values=np.linspace(0.7, 0.95, 21),
        unit="",
        source="lab",
    )
    src = ThermalSource(temperature_K=310.0, emissivity=eps, name="skin")
    d = src.to_dict()
    restored = ThermalSource.from_dict(d)
    assert restored.temperature_K == src.temperature_K
    assert restored.name == src.name
    assert isinstance(restored.emissivity, SpectralData)
    assert np.array_equal(restored.emissivity.values, eps.values)
    assert np.array_equal(restored.emissivity.wavelength_um, eps.wavelength_um)


@pytest.mark.level0
def test_frozen_instance_immutable() -> None:
    src = ThermalSource(temperature_K=300.0, emissivity=0.9)
    with pytest.raises(dataclasses.FrozenInstanceError):
        src.temperature_K = 400.0  # type: ignore[misc]
