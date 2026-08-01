"""Level 0 tests for the shot-consistent detection criterion (CU-263).

Forward model
    SNR(S) = S / √(S + N₀²)
and its analytic inverse
    S*(T) = ½(T² + √(T⁴ + 4 T² N₀²))

Every expected value below is hand arithmetic or an exactly-solvable case, not
RADIANT output (Rule 18).
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.detection_shot_consistent_snr import (
    shot_consistent_snr,
    threshold_signal_e,
)
from radiant.performance.errors import PerformanceValidationError


class TestShotConsistentSNR:
    @pytest.mark.level0
    def test_hand_value(self) -> None:
        """S = 3600 e-, N₀ = 80 e- RMS ⇒ SNR = 3600/√(3600+6400) = 36."""
        assert shot_consistent_snr(3600.0, 80.0) == pytest.approx(36.0, rel=1e-12)

    @pytest.mark.level0
    def test_pure_shot_limit_is_root_signal(self) -> None:
        """N₀ = 0 ⇒ SNR = S/√S = √S."""
        assert shot_consistent_snr(2500.0, 0.0) == pytest.approx(50.0, rel=1e-12)

    @pytest.mark.level0
    def test_floor_dominated_limit_is_the_frozen_noise_answer(self) -> None:
        """N₀² ≫ S ⇒ SNR → S/N₀, the frozen-noise expression."""
        assert shot_consistent_snr(1.0, 1.0e4) == pytest.approx(1.0e-4, rel=1e-7)

    @pytest.mark.level0
    def test_zero_signal_is_zero_snr(self) -> None:
        assert shot_consistent_snr(0.0, 10.0) == 0.0

    @pytest.mark.level0
    def test_monotone_increasing_in_signal(self) -> None:
        values = [shot_consistent_snr(s, 50.0) for s in (1.0, 10.0, 100.0, 1.0e4, 1.0e6)]
        assert values == sorted(values)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_non_physical_signal_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            shot_consistent_snr(bad, 10.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_non_physical_floor_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            shot_consistent_snr(100.0, bad)

    @pytest.mark.level0
    def test_zero_signal_and_zero_floor_raises(self) -> None:
        """SNR is undefined with no signal and no noise — 0/0, not 0."""
        with pytest.raises(PerformanceValidationError):
            shot_consistent_snr(0.0, 0.0)


class TestThresholdSignal:
    @pytest.mark.level0
    def test_hand_value(self) -> None:
        """T = 36, N₀ = 80 e- RMS ⇒ S* = ½(1296 + √(1296² + 4·1296·6400)) = 3600 e-.

        The inverse of :class:`TestShotConsistentSNR.test_hand_value`, solved
        by hand: ½(1296 + √(1679616 + 33177600)) = ½(1296 + 5904) = 3600.
        """
        assert threshold_signal_e(36.0, 80.0) == pytest.approx(3600.0, rel=1e-12)

    @pytest.mark.level0
    def test_pure_shot_limit_is_threshold_squared(self) -> None:
        """N₀ = 0 ⇒ SNR = √S = T ⇒ S* = T²."""
        assert threshold_signal_e(5.0, 0.0) == pytest.approx(25.0, rel=1e-12)

    @pytest.mark.level0
    def test_floor_dominated_limit_approaches_the_frozen_noise_product(self) -> None:
        """N₀ ≫ T ⇒ S* → T·N₀ + T²/2, i.e. the shipped ``T·σ_ref`` answer."""
        t, n0 = 5.0, 1.0e6
        assert threshold_signal_e(t, n0) == pytest.approx(t * n0 + 0.5 * t * t, rel=1e-9)

    @pytest.mark.level0
    def test_is_below_the_frozen_noise_product_whenever_the_target_is_detectable(self) -> None:
        """S* < T·σ_ref on the solver's whole domain — the correction only lengthens.

        With σ_ref² = S_ref + N₀² the frozen-noise solve needs T·σ_ref
        electrons and the shot-consistent solve needs S*.  The two criteria
        coincide *at* the reference range by construction, so the inequality
        holds exactly where the solver operates: SNR_ref = S_ref/σ_ref ≥ T.
        (Outside that domain — a target already below threshold at the
        reference range — the inequality reverses and neither solver reports a
        range.)
        """
        checked = 0
        for s_ref in (1.0, 1.0e2, 1.0e4, 1.0e6):
            for n0 in (0.0, 1.0, 30.0, 1.0e3):
                sigma_ref = math.sqrt(s_ref + n0 * n0)
                if s_ref / sigma_ref < 5.0:
                    continue
                checked += 1
                assert threshold_signal_e(5.0, n0) < 5.0 * sigma_ref
        assert checked >= 6

    @pytest.mark.level0
    def test_round_trips_with_the_forward_model(self) -> None:
        """SNR(S*(T)) = T exactly — the two are analytic inverses."""
        for t in (0.5, 1.0, 5.0, 6.0, 100.0):
            for n0 in (0.0, 1.0, 33.5872, 1.0e4):
                assert shot_consistent_snr(threshold_signal_e(t, n0), n0) == pytest.approx(
                    t, rel=1e-10
                )

    @pytest.mark.level0
    def test_cu_263_verified_value(self) -> None:
        """CU-263's 10.4 anchor: T = 5, N₀ = 33.58721 e- RMS ⇒ S* = 180.90 e-."""
        assert threshold_signal_e(5.0, 33.587211) == pytest.approx(180.901, rel=1e-5)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
    def test_non_physical_threshold_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            threshold_signal_e(bad, 10.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_non_physical_floor_raises(self, bad: float) -> None:
        with pytest.raises(PerformanceValidationError):
            threshold_signal_e(5.0, bad)
