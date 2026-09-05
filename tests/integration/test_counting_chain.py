"""Full-chain digital-counting integration tests (Gap 117 Phase 2).

Runs the complete chain (Sensor.evaluate) under
``readout.architecture = "digital_counting"`` and checks the plan §7
cross-model consistency requirement: with the packet sized to the analog
full-well equivalent and residue readout on, the counting chain's SNR
converges to the analog chain's in the shot-limited regime. Also locks the
counting noise-budget surface and the HDR dynamic-range behavior at the
metric level.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import pytest

from radiant.api.sensor import Sensor

_EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(s: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NIIRS extrapolation warning, unrelated
        return s.evaluate()


def _counting_sensor(
    counter_bits: int = 16,
    count_packet_e: float = 5000.0,
    residue_readout: bool = True,
) -> Sensor:
    s = Sensor.from_yaml(_EXAMPLE)
    # The example pins the analog full well explicitly; under counting an
    # explicit FWC is (by design) rejected, so clear it back to the default.
    s.reset("readout.full_well_capacity_e")
    s.set("readout.architecture", "digital_counting")
    s.set("readout.counter_bits", counter_bits)
    s.set("readout.count_packet_e", count_packet_e)
    s.set("readout.residue_readout", residue_readout)
    return s


@pytest.mark.level2
class TestCountingChain:
    def test_chain_runs_and_publishes_counting_outputs(self) -> None:
        r = _evaluate(_counting_sensor())
        ro = r.stage_outputs["readout"]
        assert ro["architecture"] == "digital_counting"
        assert ro["saturation_mechanism"] in ("none", "rollover", "dead_time")
        assert ro["effective_well_e"] == pytest.approx(2**16 * 5000.0, rel=1e-12)
        assert ro["counts"] >= 0
        assert "snr" in r.metrics

    def test_noise_budget_has_counting_terms(self) -> None:
        r = _evaluate(_counting_sensor())
        names = set(r.stage_outputs["readout"]["scaled_noise_terms"])
        assert "counting_quantization" in names
        assert "packet_reset" in names
        assert "quantization" not in names
        assert "ktc_reset" not in names

    def test_analog_chain_unchanged_surface(self) -> None:
        # The analog default publishes its architecture and no counting
        # outputs — the Phase 2 dispatch must not leak counting fields.
        r = _evaluate(Sensor.from_yaml(_EXAMPLE))
        ro = r.stage_outputs["readout"]
        assert ro["architecture"] == "analog_well"
        assert "counts" not in ro
        assert "quantization" in ro["scaled_noise_terms"]

    def test_snr_converges_to_analog_in_shot_limited_regime(self) -> None:
        """Plan §7 cross-model consistency: Q_pkt → analog-FWC equivalent
        with residue on must reproduce the analog SNR in the shot-limited
        regime. The example's 2 Me- well is far above the collected signal,
        both chains are unclipped and shot-dominated, and the conversion
        noises differ negligibly (analog: 32/√12 ≈ 9.2 e-; counting residue
        ADC: (2e6/2^16)/√12 ≈ 8.8 e- vs a shot noise of hundreds of e-)."""
        r_analog = _evaluate(Sensor.from_yaml(_EXAMPLE))
        # Packet = analog FWC (2 Me-), 16-bit residue ADC per the example.
        r_count = _evaluate(_counting_sensor(counter_bits=16, count_packet_e=2.0e6))
        snr_a = r_analog.metrics["snr"]
        snr_c = r_count.metrics["snr"]
        assert snr_c == pytest.approx(snr_a, rel=1e-2)

    def test_dynamic_range_uses_counting_bound(self) -> None:
        """dynamic_range_dB = 20·log10(Q_sat/σ_temporal) with the counting
        saturation bound, not the (defaulted) analog FWC parameter."""
        r = _evaluate(_counting_sensor())
        ro = r.stage_outputs["readout"]
        expected = 20.0 * math.log10(ro["full_well_capacity_e"] / ro["sigma_temporal_e"])
        assert r.metrics["dynamic_range_dB"] == pytest.approx(expected, rel=1e-9)
        # And the counting bound is the 327.68 Me- effective well — far
        # beyond any plausible analog FWC parameter default (100 ke-).
        assert ro["full_well_capacity_e"] == pytest.approx(327_680_000.0, rel=1e-12)

    def test_adc_margin_suppressed_under_counting(self) -> None:
        r_analog = _evaluate(Sensor.from_yaml(_EXAMPLE))
        r_count = _evaluate(_counting_sensor())
        assert "adc_margin_dB" in r_analog.metrics
        assert "adc_margin_dB" not in r_count.metrics

    def test_hdr_dynamic_range_exceeds_analog(self) -> None:
        """The workflow-visible HDR claim: same FPA, DROIC readout, higher
        single-frame dynamic range than the analog well."""
        r_analog = _evaluate(Sensor.from_yaml(_EXAMPLE))
        r_count = _evaluate(_counting_sensor())
        assert r_count.metrics["dynamic_range_dB"] > r_analog.metrics["dynamic_range_dB"] + 20.0
