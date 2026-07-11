"""Tests for ReadoutStage — full canonical readout chain.

ReadoutStage is the sole emitter of all 16 NoiseTerm objects. It reads
raw noise budget from ``stage_outputs["detector"]``, applies TDI/binning/
coadd scaling, and emits final scaled noise terms.
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
from radiant.readout.stage import ReadoutStage


def _make_state(
    wl: np.ndarray,
    signal_e: float = 10000.0,
    budget: NoiseBudget | None = None,
) -> ChainState:
    """Build ChainState with detector stage outputs pre-loaded."""
    state = ChainState(wavelength_um=wl)
    frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=signal_e,
        in_band_unit="e-",
    )
    state = state.with_frame(frame)

    if budget is None:
        budget = compute_noise_budget(signal_e=signal_e, read_noise_e_rms=5.0)

    state = state.with_stage_output("detector", "signal_e", signal_e)
    return state.with_stage_output("detector", "noise_budget_raw", budget)


def _make_params(
    read_noise: float = 5.0,
    gain: float = 1.0,
    bits: int = 16,
    n_tdi: int = 1,
    mx_on: int = 1,
    my_on: int = 1,
    px_off: int = 1,
    py_off: int = 1,
    n_coadds: int = 1,
    coadd_mode: str = "sum",
    fwc: float = 100000.0,
    noise_regime: str = "imaging",
) -> ParameterSet:
    schema = list(RO_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema)
    ps.set("readout.read_noise_e_rms", read_noise)
    ps.set("readout.gain_e_per_dn", gain)
    ps.set("readout.adc_bits", bits)
    ps.set("readout.n_tdi", n_tdi)
    ps.set("readout.binning_x_onchip", mx_on)
    ps.set("readout.binning_y_onchip", my_on)
    ps.set("readout.binning_x_offchip", px_off)
    ps.set("readout.binning_y_offchip", py_off)
    ps.set("readout.n_coadds", n_coadds)
    ps.set("readout.coadd_mode", coadd_mode)
    ps.set("readout.full_well_capacity_e", fwc)
    ps.set("detector.noise_regime", noise_regime)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    ps.resolve()
    return ps


class TestReadoutStageBasic:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_emits_16_noise_terms(self, wl: np.ndarray) -> None:
        out = ReadoutStage().run(_make_state(wl), _make_params())
        assert len(out.noise_terms) == 16

    @pytest.mark.level1
    def test_read_noise_term_present(self, wl: np.ndarray) -> None:
        rn = 5.0
        budget = compute_noise_budget(signal_e=10000.0, read_noise_e_rms=rn)
        out = ReadoutStage().run(
            _make_state(wl, budget=budget),
            _make_params(read_noise=rn),
        )
        read_terms = [n for n in out.noise_terms if n.name == "read_noise"]
        assert len(read_terms) == 1
        assert read_terms[0].value_e == pytest.approx(rn, rel=1e-12)

    @pytest.mark.level1
    def test_quantization_noise_term_present(self, wl: np.ndarray) -> None:
        gain = 2.0
        budget = compute_noise_budget(signal_e=10000.0, gain_e_per_dn=gain)
        out = ReadoutStage().run(
            _make_state(wl, budget=budget),
            _make_params(gain=gain),
        )
        quant_terms = [n for n in out.noise_terms if n.name == "quantization"]
        assert len(quant_terms) == 1
        expected = gain / math.sqrt(12.0)
        assert quant_terms[0].value_e == pytest.approx(expected, rel=1e-10)

    @pytest.mark.level1
    def test_signal_shot_noise(self, wl: np.ndarray) -> None:
        signal = 10000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(),
        )
        shot = [n for n in out.noise_terms if n.name == "signal_shot"][0]
        assert shot.value_e == pytest.approx(math.sqrt(signal), rel=1e-10)

    @pytest.mark.level1
    def test_stage_outputs(self, wl: np.ndarray) -> None:
        out = ReadoutStage().run(_make_state(wl), _make_params())
        ro = out.stage_outputs["readout"]
        assert "read_noise_e" in ro
        assert "quantization_noise_e" in ro
        assert "signal_dn_final" in ro
        assert "sigma_temporal_e" in ro
        assert "sigma_total_e" in ro

    @pytest.mark.level1
    def test_name(self) -> None:
        assert ReadoutStage().name == "readout"


class TestReadoutTDI:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_tdi_signal_scaling(self, wl: np.ndarray) -> None:
        """TDI N=8 multiplies signal by 8."""
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal, read_noise_e_rms=5.0)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(n_tdi=8),
        )
        ro = out.stage_outputs["readout"]
        assert ro["signal_e_final"] == pytest.approx(8000.0, rel=1e-10)

    @pytest.mark.level1
    def test_tdi_snr_improvement_read_limited(self, wl: np.ndarray) -> None:
        """TDI N=8, read-limited: SNR improves by ~N (signal ×N, read noise ×1)."""
        signal = 1.0  # very small signal → read-noise limited
        rn = 100.0
        budget = compute_noise_budget(signal_e=signal, read_noise_e_rms=rn)

        # No TDI
        out1 = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(read_noise=rn, n_tdi=1),
        )
        s1 = out1.stage_outputs["readout"]["signal_e_final"]
        n1 = out1.stage_outputs["readout"]["sigma_temporal_e"]

        # TDI N=8
        out8 = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(read_noise=rn, n_tdi=8),
        )
        s8 = out8.stage_outputs["readout"]["signal_e_final"]
        n8 = out8.stage_outputs["readout"]["sigma_temporal_e"]

        snr_ratio = (s8 / n8) / (s1 / n1)
        # Read-limited: signal ×N, noise ≈ constant → SNR ∝ N
        assert snr_ratio == pytest.approx(8.0, rel=0.01)


class TestReadoutSaturation:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_well_saturation_clips(self, wl: np.ndarray) -> None:
        """Signal exceeding FWC is clipped."""
        signal = 200000.0
        fwc = 100000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(fwc=fwc),
        )
        assert out.stage_outputs["readout"]["well_status"] == "clipped"
        # Signal DN should be at most FWC/gain
        assert out.stage_outputs["readout"]["signal_dn_pre_coadd"] <= fwc

    @pytest.mark.level1
    def test_adc_saturation_clips(self, wl: np.ndarray) -> None:
        """Signal exceeding ADC range is clipped."""
        signal = 50000.0
        # With gain=1, 50000 e- → 50000 DN. 8-bit ADC max = 255.
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(bits=8, fwc=1e6),
        )
        assert out.stage_outputs["readout"]["adc_status"] == "clipped"
        assert out.stage_outputs["readout"]["signal_dn_pre_coadd"] <= 255.0

    @pytest.mark.level1
    def test_no_saturation(self, wl: np.ndarray) -> None:
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(fwc=100000.0),
        )
        assert out.stage_outputs["readout"]["well_status"] == "ok"
        assert out.stage_outputs["readout"]["adc_status"] == "ok"

    @pytest.mark.level1
    def test_well_saturation_warns(self, wl: np.ndarray) -> None:
        """Rule 17 / Gap 65: clipping to FWC must emit a UserWarning."""
        signal = 200000.0
        budget = compute_noise_budget(signal_e=signal)
        with pytest.warns(UserWarning, match="full well saturated"):
            ReadoutStage().run(
                _make_state(wl, signal_e=signal, budget=budget),
                _make_params(fwc=100000.0),
            )

    @pytest.mark.level1
    def test_adc_saturation_warns(self, wl: np.ndarray) -> None:
        """Rule 17 / Gap 65: clipping to ADC full scale must emit a UserWarning."""
        signal = 50000.0
        budget = compute_noise_budget(signal_e=signal)
        with pytest.warns(UserWarning, match="ADC saturated"):
            ReadoutStage().run(
                _make_state(wl, signal_e=signal, budget=budget),
                _make_params(bits=8, fwc=1e6),
            )

    @pytest.mark.level1
    def test_no_saturation_no_warning(self, wl: np.ndarray) -> None:
        """An unclipped run must NOT emit saturation warnings."""
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = ReadoutStage().run(
                _make_state(wl, signal_e=signal, budget=budget),
                _make_params(fwc=100000.0),
            )
        assert out.stage_outputs["readout"]["well_status"] == "ok"


class TestReadoutBinning:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_onchip_2x2_signal(self, wl: np.ndarray) -> None:
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(mx_on=2, my_on=2),
        )
        # 2×2 on-chip: signal × 4
        assert out.stage_outputs["readout"]["signal_e_final"] == pytest.approx(
            4000.0,
            rel=1e-10,
        )


class TestReadoutCoadds:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_sum_coadd_k4_signal(self, wl: np.ndarray) -> None:
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(n_coadds=4, coadd_mode="sum"),
        )
        assert out.stage_outputs["readout"]["signal_e_final"] == pytest.approx(
            4000.0,
            rel=1e-10,
        )

    @pytest.mark.level1
    def test_average_coadd_signal_unchanged(self, wl: np.ndarray) -> None:
        signal = 1000.0
        budget = compute_noise_budget(signal_e=signal)
        out = ReadoutStage().run(
            _make_state(wl, signal_e=signal, budget=budget),
            _make_params(n_coadds=4, coadd_mode="average"),
        )
        assert out.stage_outputs["readout"]["signal_e_final"] == pytest.approx(
            1000.0,
            rel=1e-10,
        )


class TestReadoutNoiseRegime:
    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.5, 5.0, 50)

    @pytest.mark.level1
    def test_imaging_regime_excludes_spatial(self, wl: np.ndarray) -> None:
        """In 'imaging' mode, sigma_total = sigma_temporal (spatial excluded)."""
        budget = compute_noise_budget(
            signal_e=10000.0,
            prnu_pct=1.0,
            dsnu_e_rms=10.0,
        )
        out = ReadoutStage().run(
            _make_state(wl, budget=budget),
            _make_params(noise_regime="imaging"),
        )
        ro = out.stage_outputs["readout"]
        assert ro["sigma_total_e"] == pytest.approx(
            ro["sigma_temporal_e"],
            rel=1e-12,
        )
        assert ro["sigma_spatial_e"] > 0.0  # spatial computed, just not in total

    @pytest.mark.level1
    def test_detection_regime_includes_spatial(self, wl: np.ndarray) -> None:
        """In 'detection' mode, sigma_total = RSS(temporal, spatial)."""
        budget = compute_noise_budget(
            signal_e=10000.0,
            prnu_pct=1.0,
            dsnu_e_rms=10.0,
        )
        out = ReadoutStage().run(
            _make_state(wl, budget=budget),
            _make_params(noise_regime="detection"),
        )
        ro = out.stage_outputs["readout"]
        expected = math.sqrt(ro["sigma_temporal_e"] ** 2 + ro["sigma_spatial_e"] ** 2)
        assert ro["sigma_total_e"] == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level1
    def test_contributes_to_tags(self, wl: np.ndarray) -> None:
        """Temporal terms tag ('temporal', 'total'), spatial tag ('spatial', 'total')."""
        budget = compute_noise_budget(signal_e=10000.0, prnu_pct=1.0)
        out = ReadoutStage().run(
            _make_state(wl, budget=budget),
            _make_params(),
        )
        for nt in out.noise_terms:
            if nt.name == "prnu":
                assert "spatial" in nt.contributes_to
            elif nt.name == "signal_shot":
                assert "temporal" in nt.contributes_to
            assert "total" in nt.contributes_to
