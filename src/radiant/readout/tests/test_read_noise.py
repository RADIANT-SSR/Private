"""Tests for radiant.readout.read_noise."""

from __future__ import annotations

import math

import pytest

from radiant.readout.read_noise import ReadNoise


def test_basic_contribution() -> None:
    rn = ReadNoise(sigma_e_rms=5.0)
    assert rn.contribution_e() == pytest.approx(5.0, rel=1e-12)


def test_zero_read_noise_is_valid() -> None:
    rn = ReadNoise(sigma_e_rms=0.0)
    assert rn.contribution_e() == 0.0


@pytest.mark.parametrize("bad", [-1.0, -1e-9, math.inf, math.nan])
def test_invalid_sigma_raises(bad: float) -> None:
    with pytest.raises(ValueError, match="sigma_e_rms"):
        ReadNoise(sigma_e_rms=bad)


def test_round_trip() -> None:
    rn = ReadNoise(sigma_e_rms=3.7, name="my_read")
    restored = ReadNoise.from_dict(rn.to_dict())
    assert restored == rn
