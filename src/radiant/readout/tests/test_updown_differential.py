"""Level-0 tests for up/down differential counting (Gap 117 Phase 4).

Written before the implementation (Rule 18) against hand values from
``docs/plans/Digital_Pixel_Readout_Plan.md`` §2.4 and §7 anchors 4–5.
The signed modulo accumulator ends at the differential ΔQ = Q_up − Q_down;
capacity is the signed bound ±2^(N−1)·Q_pkt; the mean cancels but the noise
does not (σ² = Q_up + Q_down — the √2 background penalty).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.readout.errors import ReadoutValidationError
from radiant.readout.updown_differential import (
    DifferentialResult,
    differential_capacity_e,
    reference_shot_noise_e,
    updown_differential,
)


class TestDifferentialCapacity:
    """|ΔQ| ≤ 2^(N−1) × Q_pkt (plan §2.4)."""

    @pytest.mark.level0
    def test_hand_value(self) -> None:
        # 2^15 × 5000 e- = 163.84 Me- signed capacity for a 16-bit counter.
        assert differential_capacity_e(16, 5000.0) == pytest.approx(
            163_840_000.0, rel=0.0, abs=1e-6
        )

    @pytest.mark.level0
    def test_one_bit_counter(self) -> None:
        # 2^0 × 1000 e- = 1000 e- — the degenerate signed single-packet range.
        assert differential_capacity_e(1, 1000.0) == pytest.approx(1000.0, rel=0.0, abs=1e-12)

    @pytest.mark.level0
    def test_invalid_inputs_rejected(self) -> None:
        with pytest.raises(ReadoutValidationError, match="counter_bits"):
            differential_capacity_e(0, 5000.0)
        with pytest.raises(ReadoutValidationError, match="count_packet_e"):
            differential_capacity_e(16, 0.0)


class TestUpDownDifferential:
    """ΔQ = Q_up − Q_down with signed count conversion (floor, residue ≥ 0)."""

    @pytest.mark.level0
    def test_wrap_unwound_exactly(self) -> None:
        # Plan §7 anchor 4: a background of 1e5 counts (1e8 e- at 1000
        # e-/count) wraps a 16-bit counter during the up phase (1e5 > 65,536)
        # but the down phase unwinds it: the differential is the small target
        # signal exactly, and it is far inside the ±2^15-count capacity.
        pkt = 1000.0
        target_e = 12_345.0
        q_up = 1.0e8 + target_e
        q_down = 1.0e8
        r = updown_differential(q_up, q_down, counter_bits=16, count_packet_e=pkt)
        assert isinstance(r, DifferentialResult)
        assert r.delta_q_e == pytest.approx(target_e, rel=1e-12)
        assert not r.clipped
        assert r.n_counts == 12  # floor(12,345 / 1000)
        assert r.residue_e == pytest.approx(345.0, rel=0.0, abs=1e-6)

    @pytest.mark.level0
    def test_negative_differential_floor_semantics(self) -> None:
        # ΔQ = −7300 e- at 1000 e-/count → n = −8 counts, residue = +700 e-
        # (two's-complement counter word + non-negative analog residue).
        r = updown_differential(10_000.0, 17_300.0, counter_bits=16, count_packet_e=1000.0)
        assert r.delta_q_e == pytest.approx(-7300.0, rel=1e-12)
        assert r.n_counts == -8
        assert r.residue_e == pytest.approx(700.0, rel=0.0, abs=1e-9)

    @pytest.mark.level0
    def test_capacity_edge_inside(self) -> None:
        # Exactly +2^15 counts (plan §7 anchor 4 edge case): not clipped.
        pkt = 100.0
        cap = differential_capacity_e(16, pkt)  # 2^15 × 100 e- = 3.2768 Me-
        r = updown_differential(cap, 0.0, counter_bits=16, count_packet_e=pkt)
        assert not r.clipped
        assert r.delta_q_e == pytest.approx(cap, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize("sign", [1.0, -1.0])
    def test_capacity_edge_clipped(self, sign: float) -> None:
        # One packet beyond ±2^15 counts clips to the signed bound.
        pkt = 100.0
        cap = differential_capacity_e(16, pkt)
        over = cap + pkt
        q_up, q_down = (over, 0.0) if sign > 0 else (0.0, over)
        r = updown_differential(q_up, q_down, counter_bits=16, count_packet_e=pkt)
        assert r.clipped
        assert r.delta_q_e == pytest.approx(sign * cap, rel=1e-12)

    @pytest.mark.level0
    def test_zero_phases(self) -> None:
        r = updown_differential(0.0, 0.0, counter_bits=16, count_packet_e=1000.0)
        assert r.delta_q_e == 0.0
        assert r.n_counts == 0
        assert r.residue_e == 0.0
        assert not r.clipped

    @pytest.mark.level0
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
    def test_invalid_charges_rejected(self, bad: float) -> None:
        with pytest.raises(ReadoutValidationError, match="charge"):
            updown_differential(bad, 0.0, counter_bits=16, count_packet_e=1000.0)
        with pytest.raises(ReadoutValidationError, match="charge"):
            updown_differential(0.0, bad, counter_bits=16, count_packet_e=1000.0)


class TestReferenceShotNoise:
    """The mean cancels, the noise does not: σ_ref = √Q_down [e- RMS]."""

    @pytest.mark.level0
    def test_hand_value(self) -> None:
        # √(1e8 e-) = 10,000 e- RMS.
        assert reference_shot_noise_e(1.0e8) == pytest.approx(10_000.0, rel=1e-12)

    @pytest.mark.level0
    def test_zero_reference(self) -> None:
        assert reference_shot_noise_e(0.0) == 0.0

    @pytest.mark.level0
    def test_negative_rejected(self) -> None:
        with pytest.raises(ReadoutValidationError, match="reference"):
            reference_shot_noise_e(-1.0)

    @pytest.mark.level0
    def test_monte_carlo_differential_variance(self) -> None:
        # Plan §7 anchor 5: two-phase Poisson floor model. Var(ΔQ) =
        # Q_up + Q_down within rel 1e-2, i.e. the √2 penalty for equal
        # phases; a noiseless-reference control shows Var = Q_up alone.
        rng = np.random.default_rng(20260906)
        q_up, q_down = 2.0e5, 2.0e5
        up = rng.poisson(q_up, size=200_000).astype(float)
        down = rng.poisson(q_down, size=200_000).astype(float)
        var_two_phase = float(np.var(up - down))
        sigma_model = math.sqrt(q_up + reference_shot_noise_e(q_down) ** 2)
        assert math.sqrt(var_two_phase) == pytest.approx(sigma_model, rel=1e-2)
        # √2 penalty vs the noiseless-reference control:
        var_control = float(np.var(up))
        assert math.sqrt(var_two_phase / var_control) == pytest.approx(math.sqrt(2.0), rel=1e-2)
