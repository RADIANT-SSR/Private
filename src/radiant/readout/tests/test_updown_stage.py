"""ReadoutStage up/down (signed differential) branch tests (Gap 117 Phase 4).

Analytic expectations hand-computed per plan §2.4 and rulings D6/D7 — never
taken from other RADIANT code.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.noise_budget import NoiseBudget
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.detector.noise.budget import compute_noise_budget
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.readout.errors import (
    ArchitectureOverSpecificationError,
    CountingConfigIncompleteError,
)
from radiant.readout.stage import ReadoutStage
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS

_SQRT12 = math.sqrt(12.0)

# Point-source scene: 20,000 e- target excess over a 1e6 e- background
# pedestal, 1000 e- dark, at t_int = 10 ms with a 1000 e-/count packet.
_TARGET_E = 20_000.0
_BACKGROUND_E = 1.0e6
_DARK_E = 1000.0
_PKT = 1000.0


def _make_state(
    signal_e: float = _TARGET_E,
    background_e: float = _BACKGROUND_E,
    dark_e: float = _DARK_E,
    regime: str = "point_source",
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
        budget = compute_noise_budget(
            signal_e=signal_e,
            background_e=background_e,
            dark_e=dark_e,
            read_noise_e_rms=5.0,
        )
    state = state.with_stage_output("detector", "signal_e", signal_e)
    state = state.with_stage_output("detector", "background_e", background_e)
    state = state.with_stage_output("detector", "dark_e", dark_e)
    state = state.with_stage_output("optics", "regime", regime)
    return state.with_stage_output("detector", "noise_budget_raw", budget)


def _make_params(**extra: object) -> ParameterSet:
    ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS) + list(SI_PARAMS))
    ps.set("readout.architecture", "digital_counting")
    ps.set("readout.counter_bits", 16)
    ps.set("readout.count_packet_e", _PKT)
    ps.set("readout.counting_mode", "up_down")
    ps.set("detector.noise_regime", "imaging")
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    ps.set("spectral_integration.filter_min_um", 3.5)
    ps.set("spectral_integration.filter_max_um", 5.0)
    ps.set("spectral_integration.integration_time_s", 0.01)
    for name, value in extra.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


class TestBalancedBackgroundSubtraction:
    """Equal phases, reference = background term: the pedestal cancels."""

    @pytest.mark.level1
    def test_differential_is_target_signal(self) -> None:
        # Up phase: target + background + dark = 20,000 + 1e6 + 1000 e-.
        # Down phase (equal, background_term): background + dark = 1.001e6 e-.
        # Differential = 20,000 e- exactly; 20 counts at 1000 e-/count.
        out = ReadoutStage().run(_make_state(), _make_params())
        ro = out.stage_outputs["readout"]
        assert ro["counting_mode"] == "up_down"
        assert ro["differential_e"] == pytest.approx(_TARGET_E, rel=1e-12)
        assert ro["counts"] == 20
        assert ro["reference_charge_e"] == pytest.approx(_BACKGROUND_E + _DARK_E, rel=1e-12)
        assert ro["saturation_mechanism"] == "none"
        assert ro["well_status"] == "ok"

    @pytest.mark.level1
    def test_seventeen_terms_with_reference_shot(self) -> None:
        out = ReadoutStage().run(_make_state(), _make_params())
        names = {n.name for n in out.noise_terms}
        assert len(out.noise_terms) == 17
        assert "reference_shot" in names
        assert "counting_quantization" in names
        assert "packet_reset" in names
        assert "quantization" not in names and "ktc_reset" not in names

    @pytest.mark.level1
    def test_reference_shot_value(self) -> None:
        # √(1.001e6 e-) = 1000.49988 e- RMS.
        out = ReadoutStage().run(_make_state(), _make_params())
        term = next(n for n in out.noise_terms if n.name == "reference_shot")
        assert term.value_e == pytest.approx(math.sqrt(_BACKGROUND_E + _DARK_E), rel=1e-12)

    @pytest.mark.level1
    def test_counting_chain_noise_paid_per_phase(self) -> None:
        # Ruling D3 reinterpretation over two phases: 5 e- RMS × √2 = 7.0711.
        out = ReadoutStage().run(_make_state(), _make_params())
        term = next(n for n in out.noise_terms if n.name == "read_noise")
        assert term.value_e == pytest.approx(5.0 * math.sqrt(2.0), rel=1e-12)

    @pytest.mark.level1
    def test_snr_numerator_unchanged(self) -> None:
        # Plan §2.4 "Metrics": signal_e_final stays the scene-phase target.
        out = ReadoutStage().run(_make_state(), _make_params())
        assert out.stage_outputs["readout"]["signal_e_final"] == pytest.approx(_TARGET_E, rel=1e-12)

    @pytest.mark.level1
    def test_published_well_bound_is_signed_capacity(self) -> None:
        # 2^15 × 1000 e- = 32.768 Me- (no dead-time ceiling set).
        out = ReadoutStage().run(_make_state(), _make_params())
        assert out.stage_outputs["readout"]["full_well_capacity_e"] == pytest.approx(
            32_768_000.0, rel=1e-12
        )


class TestAsymmetricPhases:
    @pytest.mark.level1
    def test_short_reference_leaves_pedestal_residual(self) -> None:
        # t_down = t_up/2 (ruling D7 parameterized): only half the pedestal
        # cancels. Differential = target + (bg+dark)·(1 − 0.5) =
        # 20,000 + 500,500 = 520,500 e-.
        params = _make_params(readout__reference_integration_s=0.005)
        out = ReadoutStage().run(_make_state(), params)
        ro = out.stage_outputs["readout"]
        assert ro["reference_integration_s_used"] == pytest.approx(0.005, rel=1e-12)
        assert ro["differential_e"] == pytest.approx(520_500.0, rel=1e-12)


class TestUserLevelReference:
    @pytest.mark.level1
    def test_user_rate_integrates_reference(self) -> None:
        # Extended scene + user_level: rate 1e8 e-/s × 0.01 s + dark 1000 e-
        # = 1.001e6 e- down phase; up = signal(=target+bg inside) + dark.
        params = _make_params(
            readout__reference_source="user_level",
            readout__reference_rate_e_per_s=1.0e8,
        )
        state = _make_state(
            signal_e=_TARGET_E + _BACKGROUND_E,  # extended: bg inside signal
            regime="extended",
        )
        out = ReadoutStage().run(state, params)
        ro = out.stage_outputs["readout"]
        assert ro["reference_charge_e"] == pytest.approx(1.001e6, rel=1e-12)
        # Differential = (target+bg+dark) − (rate·t + dark) = 20,000 e-.
        assert ro["differential_e"] == pytest.approx(_TARGET_E, rel=1e-12)

    @pytest.mark.level1
    def test_user_level_without_rate_incomplete(self) -> None:
        params = _make_params(readout__reference_source="user_level")
        with pytest.raises(CountingConfigIncompleteError, match="reference_rate_e_per_s"):
            ReadoutStage().run(_make_state(), params)


class TestValidationMatrix:
    @pytest.mark.level1
    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("readout.reference_source", "user_level"),
            ("readout.reference_rate_e_per_s", 1.0e8),
            ("readout.reference_integration_s", 0.005),
        ],
    )
    def test_reference_param_under_up_mode_rejected(self, name: str, value: object) -> None:
        ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS) + list(SI_PARAMS))
        ps.set("readout.architecture", "digital_counting")
        ps.set("readout.count_packet_e", _PKT)  # counting_mode defaults to "up"
        ps.set(name, value)
        ps.set("detector.noise_regime", "imaging")
        ps.set("detector.pixel_pitch_x_um", 18.0)
        ps.set("detector.pixel_pitch_y_um", 18.0)
        ps.set("detector.qe_value", 0.7)
        ps.set("spectral_integration.filter_min_um", 3.5)
        ps.set("spectral_integration.filter_max_um", 5.0)
        ps.set("spectral_integration.integration_time_s", 0.01)
        ps.resolve()
        with pytest.raises(ArchitectureOverSpecificationError, match="up_down"):
            ReadoutStage().run(_make_state(), ps)

    @pytest.mark.level1
    def test_background_term_needs_separable_background(self) -> None:
        params = _make_params()  # background_term default
        with pytest.raises(ArchitectureOverSpecificationError, match="user_level"):
            ReadoutStage().run(_make_state(regime="extended"), params)

    @pytest.mark.level1
    def test_counting_mode_under_analog_rejected(self) -> None:
        ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS))
        ps.set("readout.counting_mode", "up_down")
        ps.set("detector.noise_regime", "imaging")
        ps.set("detector.pixel_pitch_x_um", 18.0)
        ps.set("detector.pixel_pitch_y_um", 18.0)
        ps.set("detector.qe_value", 0.7)
        ps.resolve()
        with pytest.raises(ArchitectureOverSpecificationError, match="counting_mode"):
            ReadoutStage().run(_make_state(), ps)


class TestDifferentialOverflow:
    @pytest.mark.level1
    def test_overflow_clips_with_mechanism(self) -> None:
        # 8-bit counter: signed capacity 2^7 × 1000 = 128,000 e-. An
        # unbalanced 1.02e6-e- pedestal residual (no reference: user_level
        # tiny rate) overflows the differential.
        params = _make_params(
            readout__counter_bits=8,
            readout__reference_source="user_level",
            readout__reference_rate_e_per_s=1.0,  # ~0 reference
        )
        state = _make_state(signal_e=_TARGET_E + _BACKGROUND_E, regime="extended")
        with pytest.warns(UserWarning, match="differential_overflow"):
            out = ReadoutStage().run(state, params)
        ro = out.stage_outputs["readout"]
        assert ro["saturation_mechanism"] == "differential_overflow"
        assert ro["well_status"] == "clipped"
        assert ro["differential_e"] == pytest.approx(128_000.0, rel=1e-12)

    @pytest.mark.level1
    def test_negative_differential_dn_is_signed(self) -> None:
        # Reference brighter than scene: user_level 2e8 e-/s × 0.01 s = 2e6
        # e- down vs ~1.021e6 e- up → ΔQ < 0, DN < 0 (D2 signed word).
        params = _make_params(
            readout__reference_source="user_level",
            readout__reference_rate_e_per_s=2.0e8,
        )
        state = _make_state(signal_e=_TARGET_E + _BACKGROUND_E, regime="extended")
        out = ReadoutStage().run(state, params)
        ro = out.stage_outputs["readout"]
        assert ro["differential_e"] < 0.0
        assert ro["signal_dn_pre_coadd"] < 0.0

    @pytest.mark.level1
    def test_up_phase_dead_time_still_applies(self) -> None:
        # f_max = 5 kHz × 0.01 s × 1000 e- = 50,000 e- up-phase ceiling —
        # the 1.021e6-e- up phase clips (per-phase ceiling, plan §2.4).
        params = _make_params(readout__max_count_rate_hz=5000.0)
        with pytest.warns(UserWarning, match="dead-time"):
            out = ReadoutStage().run(_make_state(), params)
        assert out.stage_outputs["readout"]["saturation_mechanism"] in (
            "dead_time",
            "differential_overflow",
        )
