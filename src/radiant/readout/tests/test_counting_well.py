"""Level-0 tests for the digital-pixel counting well (Gap 117 Phase 1).

Written before the implementation (Rule 18) against hand-computed analytic
values from ``docs/archive/Digital_Pixel_Readout_Plan.md`` §2.1/§2.3/§7 —
never against values computed by other RADIANT code.
"""

from __future__ import annotations

import math

import pytest

from radiant.readout.counting_well import (
    CountConversion,
    convert_to_counts,
    counting_saturation,
    dead_time_ceiling_e,
    effective_well_e,
)
from radiant.readout.errors import ReadoutValidationError


class TestEffectiveWell:
    """Q_eff = 2^N × Q_pkt."""

    @pytest.mark.level0
    def test_plan_anchor_value(self) -> None:
        # Plan §7 anchor 1: 2^16 × 5000 e-/count = 327.68 Me- exactly.
        assert effective_well_e(16, 5000.0) == pytest.approx(327_680_000.0, rel=0.0, abs=1e-6)

    @pytest.mark.level0
    def test_one_bit_counter(self) -> None:
        # 2^1 × 1000 e- = 2000 e- — the degenerate single-trip counter.
        assert effective_well_e(1, 1000.0) == pytest.approx(2000.0, rel=0.0, abs=1e-12)

    @pytest.mark.level0
    def test_32_bit_counter_no_overflow(self) -> None:
        # 2^32 × 1e7 e- = 4.294967296e16 e- — exact in float64 (< 2^53).
        assert effective_well_e(32, 1.0e7) == pytest.approx(4.294967296e16, rel=0.0, abs=1.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("bits", [0, -1, 33])
    def test_bits_out_of_domain_rejected(self, bits: int) -> None:
        with pytest.raises(ReadoutValidationError, match="counter_bits"):
            effective_well_e(bits, 5000.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("packet", [0.0, -5000.0, float("nan"), float("inf")])
    def test_invalid_packet_rejected(self, packet: float) -> None:
        with pytest.raises(ReadoutValidationError, match="count_packet_e"):
            effective_well_e(16, packet)


class TestDeadTimeCeiling:
    """Q_dead = f_max × t_int × Q_pkt."""

    @pytest.mark.level0
    def test_hand_value(self) -> None:
        # 2 MHz × 10 ms × 5000 e-/count = 2e6 × 0.01 × 5000 = 1e8 e-.
        assert dead_time_ceiling_e(2.0e6, 0.01, 5000.0) == pytest.approx(1.0e8, rel=0.0, abs=1.0)

    @pytest.mark.level0
    def test_unset_rate_means_no_ceiling(self) -> None:
        # 0.0 = unset sentinel (schema convention): no dead-time bound.
        assert dead_time_ceiling_e(0.0, 0.01, 5000.0) is None

    @pytest.mark.level0
    def test_negative_rate_rejected(self) -> None:
        with pytest.raises(ReadoutValidationError, match="max_count_rate_hz"):
            dead_time_ceiling_e(-1.0, 0.01, 5000.0)

    @pytest.mark.level0
    @pytest.mark.parametrize("t_int", [0.0, -0.01, float("nan")])
    def test_invalid_integration_time_rejected(self, t_int: float) -> None:
        with pytest.raises(ReadoutValidationError, match="integration_time_s"):
            dead_time_ceiling_e(2.0e6, t_int, 5000.0)


class TestCountingSaturation:
    """Q_sat = min(2^N·Q_pkt, f_max·t_int·Q_pkt) with the governing mechanism."""

    @pytest.mark.level0
    def test_dead_time_governs(self) -> None:
        # Rollover bound 327.68 Me- vs dead-time bound 1e8 e- → dead_time.
        q_sat, mechanism = counting_saturation(16, 5000.0, 2.0e6, 0.01)
        assert q_sat == pytest.approx(1.0e8, rel=0.0, abs=1.0)
        assert mechanism == "dead_time"

    @pytest.mark.level0
    def test_rollover_governs(self) -> None:
        # 100 MHz × 10 ms × 5000 e- = 5e9 e- > 327.68 Me- → rollover.
        q_sat, mechanism = counting_saturation(16, 5000.0, 1.0e8, 0.01)
        assert q_sat == pytest.approx(327_680_000.0, rel=0.0, abs=1e-6)
        assert mechanism == "rollover"

    @pytest.mark.level0
    def test_no_ceiling_rollover_governs(self) -> None:
        q_sat, mechanism = counting_saturation(16, 5000.0, 0.0, 0.01)
        assert q_sat == pytest.approx(327_680_000.0, rel=0.0, abs=1e-6)
        assert mechanism == "rollover"

    @pytest.mark.level0
    def test_exact_tie_reports_rollover(self) -> None:
        # Both bounds equal: 2^4 × 100 e- = 1600 e-; 1600 Hz × 1 s × 100 e- /
        # 100 e- per count → f_max·t_int = 16 counts exactly. Tie breaks to
        # rollover (the counter physically stops there first).
        q_sat, mechanism = counting_saturation(4, 100.0, 16.0, 1.0)
        assert q_sat == pytest.approx(1600.0, rel=0.0, abs=1e-12)
        assert mechanism == "rollover"


class TestCountConversion:
    """n = floor(Q/Q_pkt), residue = Q mod Q_pkt (plan §2.1)."""

    @pytest.mark.level0
    def test_exact_division(self) -> None:
        c = convert_to_counts(25_000.0, 5000.0)
        assert c == CountConversion(n_counts=5, residue_e=0.0)

    @pytest.mark.level0
    def test_hand_value_with_residue(self) -> None:
        # 12,345 e- / 5000 e-/count → 2 counts, 2345 e- residue.
        c = convert_to_counts(12_345.0, 5000.0)
        assert c.n_counts == 2
        assert c.residue_e == pytest.approx(2345.0, rel=0.0, abs=1e-9)

    @pytest.mark.level0
    def test_sub_packet_charge_is_all_residue(self) -> None:
        c = convert_to_counts(4999.0, 5000.0)
        assert c.n_counts == 0
        assert c.residue_e == pytest.approx(4999.0, rel=0.0, abs=1e-9)

    @pytest.mark.level0
    def test_zero_charge(self) -> None:
        c = convert_to_counts(0.0, 5000.0)
        assert c.n_counts == 0
        assert c.residue_e == 0.0

    @pytest.mark.level0
    def test_reconstruction_identity(self) -> None:
        # Q = n·Q_pkt + residue must hold exactly for representable inputs.
        q, pkt = 987_654.321, 4321.0
        c = convert_to_counts(q, pkt)
        assert c.n_counts * pkt + c.residue_e == pytest.approx(q, rel=1e-15)

    @pytest.mark.level0
    def test_negative_charge_rejected(self) -> None:
        with pytest.raises(ReadoutValidationError, match="charge"):
            convert_to_counts(-1.0, 5000.0)

    @pytest.mark.level0
    def test_nan_charge_rejected(self) -> None:
        # Rule 16: physics functions never accept/propagate NaN silently.
        with pytest.raises(ReadoutValidationError, match="charge"):
            convert_to_counts(float("nan"), 5000.0)

    @pytest.mark.level0
    def test_huge_charge_count_is_exact_integer(self) -> None:
        # Near the 32-bit rollover: floor must not suffer float drift.
        pkt = 1000.0
        q = (2**32 - 1) * pkt + 999.0
        c = convert_to_counts(q, pkt)
        assert c.n_counts == 2**32 - 1
        assert c.residue_e == pytest.approx(999.0, rel=0.0, abs=1e-3)


class TestDynamicRangeArithmetic:
    """Cross-check: the counting well feeds the existing DR = 20log10 form."""

    @pytest.mark.level0
    def test_hdr_dynamic_range_hand_value(self) -> None:
        # 2^16 × 5000 e- / 5 e- floor → 20·log10(6.5536e7) = 156.33 dB
        # (hand: log10(6.5536e7) = 7.81648…, ×20 = 156.3297).
        q_eff = effective_well_e(16, 5000.0)
        dr_db = 20.0 * math.log10(q_eff / 5.0)
        assert dr_db == pytest.approx(156.3297, abs=1e-3)
