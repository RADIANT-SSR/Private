"""Tests for radiant.detector.dark_current."""

from __future__ import annotations

import math

import pytest

from radiant.core.constants import k_B, q
from radiant.detector.dark_current import DarkCurrent


def test_basic_accumulation() -> None:
    dc = DarkCurrent(rate_e_per_s=100.0)
    assert dc.electrons_accumulated(0.1) == pytest.approx(10.0, rel=1e-12)
    assert dc.electrons_accumulated(0.0) == 0.0


def test_shot_noise_is_sqrt_accumulated() -> None:
    dc = DarkCurrent(rate_e_per_s=100.0)
    # 100 e-/s * 1 s = 100 e- → √100 = 10 e- RMS.
    assert dc.shot_noise_e(1.0) == pytest.approx(10.0, rel=1e-12)


def test_zero_activation_energy_returns_unchanged_rate() -> None:
    dc = DarkCurrent(rate_e_per_s=50.0, reference_temperature_K=300.0)
    scaled = dc.at_temperature(250.0)
    assert scaled.rate_e_per_s == pytest.approx(50.0, rel=1e-12)
    assert scaled.reference_temperature_K == 250.0


def test_arrhenius_truth_anchor() -> None:
    # Truth anchor: closed-form Arrhenius match.
    # Eₐ = 0.65 eV (typical Si), T_ref = 300 K, T = 250 K.
    # factor = exp(-(0.65·q / k_B) · (1/250 − 1/300))
    ea = 0.65
    t_ref = 300.0
    t = 250.0
    expected_factor = math.exp(-(ea * q) / k_B * (1.0 / t - 1.0 / t_ref))
    dc = DarkCurrent(
        rate_e_per_s=1000.0,
        reference_temperature_K=t_ref,
        activation_energy_eV=ea,
    )
    scaled = dc.at_temperature(t)
    assert scaled.rate_e_per_s == pytest.approx(1000.0 * expected_factor, rel=1e-12)
    # Expected direction: cooling from 300 → 250 K reduces dark rate.
    assert scaled.rate_e_per_s < 1000.0


def test_arrhenius_heating_increases_rate() -> None:
    dc = DarkCurrent(
        rate_e_per_s=1.0,
        reference_temperature_K=300.0,
        activation_energy_eV=0.65,
    )
    warmer = dc.at_temperature(320.0)
    assert warmer.rate_e_per_s > 1.0


def test_arrhenius_at_reference_temperature_is_identity() -> None:
    dc = DarkCurrent(
        rate_e_per_s=42.0,
        reference_temperature_K=150.0,
        activation_energy_eV=0.3,
    )
    same = dc.at_temperature(150.0)
    assert same.rate_e_per_s == pytest.approx(42.0, rel=1e-12)


def test_arrhenius_halving_per_temperature_step() -> None:
    # Classic "dark current halves every ~7-8 K at room temp" rule of thumb,
    # purely as an order-of-magnitude sanity check with E_a = 0.63 eV.
    dc = DarkCurrent(
        rate_e_per_s=1.0,
        reference_temperature_K=300.0,
        activation_energy_eV=0.63,
    )
    cooler = dc.at_temperature(292.0)
    # Expect roughly half (within a factor of 2).
    assert 0.3 < cooler.rate_e_per_s < 0.7


@pytest.mark.parametrize("bad", [-1.0, -1e-9, math.inf, math.nan])
def test_invalid_rate_raises(bad: float) -> None:
    with pytest.raises(ValueError, match="rate_e_per_s"):
        DarkCurrent(rate_e_per_s=bad)


@pytest.mark.parametrize("bad_t", [0.0, -10.0, math.inf, math.nan])
def test_invalid_reference_temperature_raises(bad_t: float) -> None:
    with pytest.raises(ValueError, match="reference_temperature_K"):
        DarkCurrent(rate_e_per_s=1.0, reference_temperature_K=bad_t)


def test_invalid_activation_energy_raises() -> None:
    with pytest.raises(ValueError, match="activation_energy_eV"):
        DarkCurrent(rate_e_per_s=1.0, activation_energy_eV=-0.1)


@pytest.mark.parametrize("bad_t", [0.0, -10.0, math.inf, math.nan])
def test_at_temperature_rejects_invalid(bad_t: float) -> None:
    dc = DarkCurrent(rate_e_per_s=1.0)
    with pytest.raises(ValueError, match="temperature_K"):
        dc.at_temperature(bad_t)


def test_invalid_integration_time_raises() -> None:
    dc = DarkCurrent(rate_e_per_s=1.0)
    with pytest.raises(ValueError, match="integration_time_s"):
        dc.electrons_accumulated(-1.0)
    with pytest.raises(ValueError, match="integration_time_s"):
        dc.shot_noise_e(math.nan)


def test_round_trip() -> None:
    dc = DarkCurrent(
        rate_e_per_s=12.5,
        reference_temperature_K=200.0,
        activation_energy_eV=0.5,
        name="hgcdte",
    )
    restored = DarkCurrent.from_dict(dc.to_dict())
    assert restored == dc
