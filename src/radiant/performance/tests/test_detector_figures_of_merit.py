"""Level 0 tests for the Gap 45 detector figures of merit.

Truth anchors are hand calculations (Rule 18):

- Crossover: σ_read = 30 e⁻, t = 0.01 s → rate = 30²/0.01 = 90 000 e⁻/s.
- BLIP: signal = 5000 e⁻, t = 0.01 s → 500 000 e⁻/s.
- NEI: σ = 100 e⁻, QE = 0.8, A = 1e-6 cm², t = 0.01 s →
  100 / (0.8 · 1e-6 · 0.01) = 1.25e10 photons/s/cm².
"""

from __future__ import annotations

import pytest

from radiant.performance.blip_rate import BlipRateError, blip_rate_e_per_s
from radiant.performance.dark_crossover_rate import (
    DarkCrossoverError,
    dark_shot_crossover_rate_e_per_s,
)
from radiant.performance.noise_equivalent_irradiance import (
    NoiseEquivalentIrradianceError,
    noise_equivalent_irradiance_ph_s_cm2,
)


class TestDarkCrossover:
    def test_anchor(self) -> None:
        assert dark_shot_crossover_rate_e_per_s(30.0, 0.01) == pytest.approx(90_000.0, rel=1e-12)

    def test_scales_with_readnoise_squared(self) -> None:
        base = dark_shot_crossover_rate_e_per_s(10.0, 0.01)
        assert dark_shot_crossover_rate_e_per_s(20.0, 0.01) == pytest.approx(4.0 * base, rel=1e-12)

    def test_zero_integration_raises(self) -> None:
        with pytest.raises(DarkCrossoverError, match="integration_time_s"):
            dark_shot_crossover_rate_e_per_s(30.0, 0.0)


class TestBlipRate:
    def test_anchor(self) -> None:
        assert blip_rate_e_per_s(5000.0, 0.01) == pytest.approx(500_000.0, rel=1e-12)

    def test_zero_integration_raises(self) -> None:
        with pytest.raises(BlipRateError, match="integration_time_s"):
            blip_rate_e_per_s(5000.0, 0.0)


class TestNEI:
    def test_anchor(self) -> None:
        nei = noise_equivalent_irradiance_ph_s_cm2(100.0, 0.8, 1e-6, 0.01)
        assert nei == pytest.approx(1.25e10, rel=1e-9)

    def test_lower_noise_lower_nei(self) -> None:
        hi = noise_equivalent_irradiance_ph_s_cm2(200.0, 0.8, 1e-6, 0.01)
        lo = noise_equivalent_irradiance_ph_s_cm2(100.0, 0.8, 1e-6, 0.01)
        assert lo < hi

    def test_bad_qe_raises(self) -> None:
        with pytest.raises(NoiseEquivalentIrradianceError, match="qe"):
            noise_equivalent_irradiance_ph_s_cm2(100.0, 1.5, 1e-6, 0.01)
