"""ReadoutStage digital-counting branch tests (Gap 117 Phase 2).

The counting branch swaps the analog conversion noise pair for
``counting_quantization`` / ``packet_reset``, saturates at the counting
bound through ``check_well_saturation``, and emits ruling-D2 DN. Analytic
expectations are hand-computed, never taken from other RADIANT code.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.noise_budget import NoiseBudget
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.detector.noise.budget import compute_noise_budget
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.readout.errors import ReadoutValidationError
from radiant.readout.stage import ReadoutStage
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS

_SQRT12 = math.sqrt(12.0)


def _make_state(
    signal_e: float = 100_000.0,
    budget: NoiseBudget | None = None,
) -> ChainState:
    wl = np.linspace(3.5, 5.0, 50)
    state = ChainState(wavelength_um=wl)
    state = state.with_frame(
        RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            in_band_value=signal_e,
            in_band_unit="e-",
        )
    )
    if budget is None:
        budget = compute_noise_budget(signal_e=signal_e, read_noise_e_rms=5.0)
    state = state.with_stage_output("detector", "signal_e", signal_e)
    return state.with_stage_output("detector", "noise_budget_raw", budget)


def _make_params(
    counter_bits: int = 16,
    count_packet_e: float = 5000.0,
    residue_readout: bool = True,
    max_count_rate_hz: float = 0.0,
    adc_bits: int = 14,
    t_int_s: float | None = 0.01,
    **extra: object,
) -> ParameterSet:
    schema = list(RO_PARAMS) + list(DET_PARAMS) + list(SI_PARAMS)
    ps = ParameterSet(schema)
    ps.set("readout.architecture", "digital_counting")
    ps.set("readout.counter_bits", counter_bits)
    ps.set("readout.count_packet_e", count_packet_e)
    ps.set("readout.residue_readout", residue_readout)
    if max_count_rate_hz > 0.0:
        ps.set("readout.max_count_rate_hz", max_count_rate_hz)
    ps.set("readout.adc_bits", adc_bits)
    ps.set("detector.noise_regime", "imaging")
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    if t_int_s is not None:
        ps.set("spectral_integration.integration_time_s", t_int_s)
    for name, value in extra.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


class TestNoiseTermSwap:
    @pytest.mark.level1
    def test_sixteen_terms_with_counting_pair(self) -> None:
        out = ReadoutStage().run(_make_state(), _make_params())
        names = {n.name for n in out.noise_terms}
        assert len(out.noise_terms) == 16
        assert "counting_quantization" in names
        assert "packet_reset" in names
        assert "quantization" not in names
        assert "ktc_reset" not in names

    @pytest.mark.level1
    def test_counting_quantization_residue_on(self) -> None:
        # (5000 e- / 2^14) / √12 = 0.30517578125 / 3.4641016 = 0.088097 e- RMS.
        out = ReadoutStage().run(_make_state(), _make_params(adc_bits=14))
        term = next(n for n in out.noise_terms if n.name == "counting_quantization")
        assert term.value_e == pytest.approx((5000.0 / 2**14) / _SQRT12, rel=1e-12)

    @pytest.mark.level1
    def test_counting_quantization_residue_off(self) -> None:
        # 5000 e- / √12 = 1443.3757 e- RMS.
        out = ReadoutStage().run(_make_state(), _make_params(residue_readout=False))
        term = next(n for n in out.noise_terms if n.name == "counting_quantization")
        assert term.value_e == pytest.approx(1443.37567, abs=1e-4)

    @pytest.mark.level1
    def test_packet_reset_cds_on_is_zero(self) -> None:
        # CDS on (default): raw kTC = 0 → packet_reset = √n × 0 = 0.
        out = ReadoutStage().run(_make_state(), _make_params())
        term = next(n for n in out.noise_terms if n.name == "packet_reset")
        assert term.value_e == 0.0

    @pytest.mark.level1
    def test_packet_reset_cds_off(self) -> None:
        # kTC per reset: σ = √(kTC)/q e-. C = 10 fF, T = 77 K:
        # √(1.380649e-23 × 77 × 1e-14) / 1.602177e-19 = 643.72 e- RMS/reset.
        # signal 100,000 e- / 5000 e- per count → n = 20 trips →
        # packet_reset = √20 × 643.72 = 2878.8 e- RMS.
        budget = compute_noise_budget(
            signal_e=100_000.0,
            read_noise_e_rms=5.0,
            node_capacitance_F=1.0e-14,
            detector_temp_K=77.0,
            cds_enabled=False,
        )
        params = _make_params(
            readout__cds_enabled=0,
            readout__node_capacitance_F=1.0e-14,
            detector__detector_temperature_K=77.0,
        )
        out = ReadoutStage().run(_make_state(budget=budget), params)
        term = next(n for n in out.noise_terms if n.name == "packet_reset")
        sigma_ktc = math.sqrt(1.380649e-23 * 77.0 * 1.0e-14) / 1.602176634e-19
        assert term.value_e == pytest.approx(math.sqrt(20.0) * sigma_ktc, rel=1e-6)


class TestDnSemantics:
    @pytest.mark.level1
    def test_combined_word_residue_on(self) -> None:
        # D2: gain = Q_pkt/2^M = 5000/16384 e-/DN; DN = signal/gain =
        # 100,000 × 16384 / 5000 = 327,680 DN (= n·2^M + res/g exactly).
        out = ReadoutStage().run(_make_state(100_000.0), _make_params(adc_bits=14))
        ro = out.stage_outputs["readout"]
        assert ro["gain_e_per_dn"] == pytest.approx(5000.0 / 16384.0, rel=1e-15)
        assert ro["signal_dn_pre_coadd"] == pytest.approx(327_680.0, rel=1e-12)

    @pytest.mark.level1
    def test_bare_counter_residue_off(self) -> None:
        # D2: gain = Q_pkt = 5000 e-/DN; DN = 100,000/5000 = 20 DN.
        out = ReadoutStage().run(_make_state(100_000.0), _make_params(residue_readout=False))
        ro = out.stage_outputs["readout"]
        assert ro["gain_e_per_dn"] == pytest.approx(5000.0, rel=1e-15)
        assert ro["signal_dn_pre_coadd"] == pytest.approx(20.0, rel=1e-12)


class TestCountingSaturation:
    @pytest.mark.level1
    def test_unsaturated_mechanism_none(self) -> None:
        out = ReadoutStage().run(_make_state(100_000.0), _make_params())
        ro = out.stage_outputs["readout"]
        assert ro["saturation_mechanism"] == "none"
        assert ro["well_status"] == "ok"
        assert ro["counts"] == 20
        assert ro["effective_well_e"] == pytest.approx(327_680_000.0, rel=1e-12)
        assert ro["full_well_capacity_e"] == pytest.approx(327_680_000.0, rel=1e-12)

    @pytest.mark.level1
    def test_rollover_clip_and_warning(self) -> None:
        # 4-bit counter × 1000 e- = 16,000 e- effective well; 100,000 e-
        # signal clips to 16,000 e- with the Gap 117 counting warning.
        params = _make_params(counter_bits=4, count_packet_e=1000.0)
        with pytest.warns(UserWarning, match="rollover"):
            out = ReadoutStage().run(_make_state(100_000.0), params)
        ro = out.stage_outputs["readout"]
        assert ro["saturation_mechanism"] == "rollover"
        assert ro["well_status"] == "clipped"
        assert ro["signal_e_final"] == pytest.approx(16_000.0, rel=1e-12)

    @pytest.mark.level1
    def test_dead_time_clip_and_mechanism(self) -> None:
        # f_max = 1 kHz × 0.01 s × 1000 e-/count = 10,000 e- ceiling <
        # rollover bound 2^16 × 1000 = 65.536 Me- → dead_time governs, and
        # the 100,000 e- signal clips to the 10,000 e- ceiling.
        params = _make_params(
            counter_bits=16,
            count_packet_e=1000.0,
            max_count_rate_hz=1000.0,
            t_int_s=0.01,
        )
        with pytest.warns(UserWarning, match="dead_time"):
            out = ReadoutStage().run(_make_state(100_000.0), params)
        ro = out.stage_outputs["readout"]
        assert ro["saturation_mechanism"] == "dead_time"
        assert ro["full_well_capacity_e"] == pytest.approx(10_000.0, rel=1e-12)
        assert ro["signal_e_final"] == pytest.approx(10_000.0, rel=1e-12)

    @pytest.mark.level1
    def test_dead_time_without_integration_time_rejected(self) -> None:
        # Partial chain: no spectral_integration schema at all — a dead-time
        # ceiling cannot be evaluated without t_int and must raise.
        ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS))
        ps.set("readout.architecture", "digital_counting")
        ps.set("readout.count_packet_e", 5000.0)
        ps.set("readout.max_count_rate_hz", 1.0e6)
        ps.set("detector.noise_regime", "imaging")
        ps.set("detector.pixel_pitch_x_um", 18.0)
        ps.set("detector.pixel_pitch_y_um", 18.0)
        ps.set("detector.qe_value", 0.7)
        ps.resolve()
        with pytest.raises(ReadoutValidationError, match="integration_time_s"):
            ReadoutStage().run(_make_state(), ps)


class TestAnalogDiagnosticsSuppressed:
    @pytest.mark.level1
    def test_no_adc_well_match_warning_under_counting(self) -> None:
        # An analog config with these values (gain 1 e-/DN, 8-bit ADC vs a
        # 327 Me- well) would warn egregious-mismatch; counting must not.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = ReadoutStage().run(
                _make_state(100_000.0),
                _make_params(readout__gain_e_per_dn=1.0, adc_bits=8),
            )
        assert "adc_well_match_ratio" not in out.stage_outputs["readout"]

    @pytest.mark.level1
    def test_adc_status_ok_under_counting(self) -> None:
        # The counter IS the ADC — no separate ADC clip is ever reported.
        out = ReadoutStage().run(_make_state(100_000.0), _make_params(residue_readout=False))
        assert out.stage_outputs["readout"]["adc_status"] == "ok"


class TestArchitectureOutput:
    @pytest.mark.level1
    def test_counting_branch_publishes_architecture(self) -> None:
        out = ReadoutStage().run(_make_state(), _make_params())
        assert out.stage_outputs["readout"]["architecture"] == "digital_counting"

    @pytest.mark.level1
    def test_analog_branch_publishes_architecture(self) -> None:
        schema = list(RO_PARAMS) + list(DET_PARAMS)
        ps = ParameterSet(schema)
        ps.set("detector.noise_regime", "imaging")
        ps.set("detector.pixel_pitch_x_um", 18.0)
        ps.set("detector.pixel_pitch_y_um", 18.0)
        ps.set("detector.qe_value", 0.7)
        ps.resolve()
        out = ReadoutStage().run(_make_state(), ps)
        ro = out.stage_outputs["readout"]
        assert ro["architecture"] == "analog_well"
        names = {n.name for n in out.noise_terms}
        assert "counting_quantization" not in names
        assert "packet_reset" not in names
        assert "counts" not in ro


class TestSigmaConsistency:
    @pytest.mark.level1
    def test_temporal_rss_matches_terms(self) -> None:
        out = ReadoutStage().run(_make_state(), _make_params())
        ro = out.stage_outputs["readout"]
        scaled = ro["scaled_noise_terms"]
        from radiant.core.noise_budget import TEMPORAL_TERMS

        expected = math.sqrt(sum(v**2 for k, v in scaled.items() if k in TEMPORAL_TERMS))
        assert ro["sigma_temporal_e"] == pytest.approx(expected, rel=1e-12)
