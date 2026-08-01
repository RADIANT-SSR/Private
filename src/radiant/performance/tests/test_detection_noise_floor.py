"""Level 0 tests for the target-free noise floor (CU-263).

The decomposition under test is the variance identity

    σ_total² = S + N₀²

— the target's own shot variance is *S* electrons², everything else (background
shot, dark, read, kTC, quantisation, clutter) is the range-independent floor
N₀².  The test values are hand arithmetic, not RADIANT output.
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.detection_noise_floor import target_free_noise_floor_e
from radiant.performance.errors import PerformanceValidationError


class TestTargetFreeNoiseFloor:
    @pytest.mark.level0
    def test_hand_value(self) -> None:
        """σ = 100 e- RMS over S = 3600 e- ⇒ N₀ = √(10000 − 3600) = 80 e- RMS."""
        assert target_free_noise_floor_e(100.0, 3600.0) == pytest.approx(80.0, rel=1e-12)

    @pytest.mark.level0
    def test_shot_limited_case_has_zero_floor(self) -> None:
        """σ² = S exactly (pure target shot noise) ⇒ N₀ = 0 e- RMS."""
        assert target_free_noise_floor_e(100.0, 1.0e4) == pytest.approx(0.0, abs=1e-9)

    @pytest.mark.level0
    def test_zero_signal_returns_the_whole_noise(self) -> None:
        assert target_free_noise_floor_e(42.0, 0.0) == pytest.approx(42.0, rel=1e-12)

    @pytest.mark.level0
    def test_floor_dominates_when_signal_is_negligible(self) -> None:
        """S ≪ σ² ⇒ N₀ → σ (the frozen-noise limit)."""
        assert target_free_noise_floor_e(1000.0, 1.0) == pytest.approx(
            math.sqrt(1.0e6 - 1.0), rel=1e-12
        )

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_non_physical_noise_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            target_free_noise_floor_e(bad, 100.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_non_physical_signal_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            target_free_noise_floor_e(100.0, bad)

    @pytest.mark.level0
    def test_signal_above_total_variance_raises(self) -> None:
        """σ² < S is not a decomposition — it is an inconsistent noise budget."""
        with pytest.raises(PerformanceValidationError, match="exceeds"):
            target_free_noise_floor_e(10.0, 1.0e4)
