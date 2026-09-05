"""Level-0 tests for counting quantization noise (Gap 117 Phase 1).

Written before the implementation (Rule 18). Analytic truth: the RMS of a
uniform distribution on an interval of width L is L/√12 — applied to the
packet (residue discarded) or to the residue-ADC LSB (residue digitized),
per ``docs/plans/Digital_Pixel_Readout_Plan.md`` §2.2 and ruling D2.

Includes the plan §7 anchor-2 Monte Carlo: a numeric floor-model simulation
over a flux sweep against the analytic σ_q at rel=1e-2, with the low-flux
regime where the uniform-residue assumption degrades exercised explicitly.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.readout.counting_quantization import (
    counting_quantization_noise_e,
    residue_adc_gain_e_per_dn,
)
from radiant.readout.errors import ReadoutValidationError

_SQRT12 = math.sqrt(12.0)


class TestPacketQuantization:
    """residue_readout=False: σ_q = Q_pkt/√12."""

    @pytest.mark.level0
    def test_hand_value(self) -> None:
        # 5000 e- / √12 = 1443.3757… e- RMS.
        sigma = counting_quantization_noise_e(5000.0, residue_readout=False, adc_bits=14)
        assert sigma == pytest.approx(1443.37567, abs=1e-4)

    @pytest.mark.level0
    def test_adc_bits_irrelevant_without_residue(self) -> None:
        # The bare counter never sees the ADC; bits must not leak in.
        s1 = counting_quantization_noise_e(5000.0, residue_readout=False, adc_bits=8)
        s2 = counting_quantization_noise_e(5000.0, residue_readout=False, adc_bits=16)
        assert s1 == s2

    @pytest.mark.level0
    def test_scales_linearly_with_packet(self) -> None:
        s1 = counting_quantization_noise_e(1000.0, residue_readout=False, adc_bits=14)
        s2 = counting_quantization_noise_e(2000.0, residue_readout=False, adc_bits=14)
        assert s2 == pytest.approx(2.0 * s1, rel=1e-15)


class TestResidueAdcQuantization:
    """residue_readout=True: existing ADC model on the residue, full scale = Q_pkt.

    Ruling D2: residue gain = Q_pkt / 2^M e-/DN, so σ_q = (Q_pkt/2^M)/√12.
    """

    @pytest.mark.level0
    def test_residue_gain_hand_value(self) -> None:
        # 5000 e- / 2^14 = 0.30517578125 e-/DN exactly.
        assert residue_adc_gain_e_per_dn(5000.0, 14) == pytest.approx(
            0.30517578125, rel=0.0, abs=1e-15
        )

    @pytest.mark.level0
    def test_hand_value(self) -> None:
        # (5000 / 2^14) / √12 = 0.30517578125 / 3.46410… = 0.0880967… e- RMS.
        sigma = counting_quantization_noise_e(5000.0, residue_readout=True, adc_bits=14)
        assert sigma == pytest.approx(0.30517578125 / _SQRT12, rel=1e-12)

    @pytest.mark.level0
    def test_residue_recovers_dynamic_range_floor(self) -> None:
        # The residue ADC shrinks the quantization floor by exactly 2^M.
        s_bare = counting_quantization_noise_e(5000.0, residue_readout=False, adc_bits=12)
        s_res = counting_quantization_noise_e(5000.0, residue_readout=True, adc_bits=12)
        assert s_bare / s_res == pytest.approx(4096.0, rel=1e-12)

    @pytest.mark.level0
    def test_matches_existing_adc_model(self) -> None:
        # Cross-model consistency (in-repo trusted implementation): the
        # residue branch must equal adc.AnalogToDigital.quantization_noise_e
        # evaluated at the residue gain — same model, two routes.
        from radiant.readout.adc import AnalogToDigital

        pkt, bits = 4321.0, 13
        via_counting = counting_quantization_noise_e(pkt, residue_readout=True, adc_bits=bits)
        via_adc = AnalogToDigital(
            gain_e_per_dn=residue_adc_gain_e_per_dn(pkt, bits), n_bits=bits
        ).quantization_noise_e()
        assert via_counting == pytest.approx(via_adc, rel=1e-15)


class TestValidation:
    @pytest.mark.level0
    @pytest.mark.parametrize("packet", [0.0, -1.0, float("nan"), float("inf")])
    def test_invalid_packet_rejected(self, packet: float) -> None:
        with pytest.raises(ReadoutValidationError, match="count_packet_e"):
            counting_quantization_noise_e(packet, residue_readout=False, adc_bits=14)

    @pytest.mark.level0
    @pytest.mark.parametrize("bits", [0, -1])
    def test_invalid_bits_rejected_when_residue_on(self, bits: int) -> None:
        with pytest.raises(ReadoutValidationError, match="adc_bits"):
            counting_quantization_noise_e(5000.0, residue_readout=True, adc_bits=bits)


class TestMonteCarloFloorModel:
    """Plan §7 anchor 2: analytic σ_q vs a numeric floor-model simulation."""

    @pytest.mark.level0
    def test_uniform_residue_regime(self) -> None:
        # High flux (Q >> Q_pkt): quantization error of the bare counter,
        # e = Q − Q_pkt·floor(Q/Q_pkt), over a flux ensemble spanning many
        # packets is uniform on [0, Q_pkt) → RMS about the mean = Q_pkt/√12.
        rng = np.random.default_rng(20260904)
        pkt = 5000.0
        q = rng.uniform(50 * pkt, 250 * pkt, size=200_000)  # 50–250 packets
        residue = q - pkt * np.floor(q / pkt)
        sigma_mc = float(np.std(residue))
        sigma_analytic = counting_quantization_noise_e(pkt, residue_readout=False, adc_bits=14)
        assert sigma_mc == pytest.approx(sigma_analytic, rel=1e-2)

    @pytest.mark.level0
    def test_residue_adc_regime(self) -> None:
        # With the residue digitized at gain g = Q_pkt/2^M, the error is the
        # ADC rounding of the residue: uniform on one LSB → g/√12.
        rng = np.random.default_rng(20260905)
        pkt, bits = 5000.0, 10
        g = pkt / float(1 << bits)
        q = rng.uniform(50 * pkt, 250 * pkt, size=200_000)
        residue = q - pkt * np.floor(q / pkt)
        dn = np.floor(residue / g)  # floor-quantizer residue ADC
        err = residue - g * dn
        sigma_mc = float(np.std(err))
        sigma_analytic = counting_quantization_noise_e(pkt, residue_readout=True, adc_bits=bits)
        assert sigma_mc == pytest.approx(sigma_analytic, rel=1e-2)

    @pytest.mark.level0
    def test_low_flux_regime_degrades_as_expected(self) -> None:
        # Regime note (plan §7 anchor 2): for Q < Q_pkt the counter never
        # trips — the "residue" is the whole signal, its ensemble spread is
        # the signal spread, NOT Q_pkt/√12. The uniform-residue formula is
        # a flux-ensemble statement valid only for Q spanning ≥ several
        # packets. Document by construction: an ensemble confined to
        # [0, Q_pkt/10] has RMS ≈ (Q_pkt/10)/√12 ≠ Q_pkt/√12.
        rng = np.random.default_rng(20260906)
        pkt = 5000.0
        q = rng.uniform(0.0, pkt / 10.0, size=200_000)
        residue = q - pkt * np.floor(q / pkt)  # = q identically here
        sigma_mc = float(np.std(residue))
        assert sigma_mc == pytest.approx((pkt / 10.0) / _SQRT12, rel=1e-2)
        sigma_analytic = counting_quantization_noise_e(pkt, residue_readout=False, adc_bits=14)
        assert sigma_mc < 0.2 * sigma_analytic  # far below the uniform-residue value
