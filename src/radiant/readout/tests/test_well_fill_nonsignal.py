"""Near-field and stray electrons fill the well too (CU-350).

``SpectralIntegrationStage`` publishes ``nearfield_e`` (warm-optics
self-emission) and ``stray_e``; ``DetectorStage`` re-publishes both and
already counts their **shot noise** in the raw budget. They therefore sit
in the same physical charge well as signal, dark, and glow, and must enter
the well-fill / saturation total in every readout architecture.

Unlike the point-source background pedestal (Gap 73), they are never
folded into ``signal_e`` by an upstream stage, so they accumulate in
**all** regimes and carry no regime gate.

Expected values here are hand-computed sums in e-, never taken from other
RADIANT code.
"""

from __future__ import annotations

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
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS


def _make_state(
    *,
    signal_e: float,
    dark_e: float = 0.0,
    glow_e: float = 0.0,
    background_e: float = 0.0,
    nearfield_e: float = 0.0,
    stray_e: float = 0.0,
    regime: str = "extended",
) -> ChainState:
    """ChainState carrying the detector-stage charge terms, all in e-."""
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
    budget: NoiseBudget = compute_noise_budget(
        signal_e=signal_e,
        background_e=background_e,
        dark_e=dark_e,
        read_noise_e_rms=5.0,
    )
    state = state.with_stage_output("detector", "signal_e", signal_e)
    state = state.with_stage_output("detector", "dark_e", dark_e)
    state = state.with_stage_output("detector", "glow_e", glow_e)
    state = state.with_stage_output("detector", "background_e", background_e)
    state = state.with_stage_output("detector", "nearfield_e", nearfield_e)
    state = state.with_stage_output("detector", "stray_e", stray_e)
    state = state.with_stage_output("optics", "regime", regime)
    return state.with_stage_output("detector", "noise_budget_raw", budget)


def _analog_params(
    *,
    fwc_e: float = 1.0e5,
    n_tdi: int = 1,
    mx_on: int = 1,
    my_on: int = 1,
) -> ParameterSet:
    ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS))
    ps.set("readout.read_noise_e_rms", 5.0)
    ps.set("readout.gain_e_per_dn", 10.0)
    ps.set("readout.adc_bits", 16)
    ps.set("readout.n_tdi", n_tdi)
    ps.set("readout.binning_x_onchip", mx_on)
    ps.set("readout.binning_y_onchip", my_on)
    ps.set("readout.full_well_capacity_e", fwc_e)
    ps.set("detector.noise_regime", "imaging")
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    ps.resolve()
    return ps


def _counting_params(
    *,
    counter_bits: int = 16,
    count_packet_e: float = 5000.0,
    n_tdi: int = 1,
    mx_on: int = 1,
    my_on: int = 1,
    **extra: object,
) -> ParameterSet:
    ps = ParameterSet(list(RO_PARAMS) + list(DET_PARAMS) + list(SI_PARAMS))
    ps.set("readout.architecture", "digital_counting")
    ps.set("readout.counter_bits", counter_bits)
    ps.set("readout.count_packet_e", count_packet_e)
    ps.set("readout.residue_readout", True)
    ps.set("readout.adc_bits", 14)
    ps.set("readout.n_tdi", n_tdi)
    ps.set("readout.binning_x_onchip", mx_on)
    ps.set("readout.binning_y_onchip", my_on)
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


def _run_quiet(state: ChainState, params: ParameterSet) -> ChainState:
    """Run the stage swallowing the deliberate saturation UserWarnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return ReadoutStage().run(state, params)


class TestAnalogWell:
    @pytest.mark.level1
    def test_nearfield_and_stray_raise_total_well(self) -> None:
        """total_well_e = signal + dark + glow + nearfield + stray, in e-."""
        out = _run_quiet(
            _make_state(
                signal_e=1000.0,  # e-
                dark_e=200.0,  # e-
                glow_e=50.0,  # e-
                nearfield_e=3000.0,  # e-
                stray_e=700.0,  # e-
            ),
            _analog_params(fwc_e=1.0e6),
        )
        ro = out.stage_outputs["readout"]
        # 1000 + 200 + 50 + 3000 + 700 = 4950 e-
        assert ro["total_well_e"] == pytest.approx(4950.0, rel=1e-12)
        assert ro["well_fill_fraction"] == pytest.approx(4950.0 / 1.0e6, rel=1e-12)

    @pytest.mark.level1
    def test_zero_nearfield_and_stray_is_bit_identical(self) -> None:
        """Regression: with no near-field/stray the total is the old sum."""
        out = _run_quiet(
            _make_state(signal_e=1000.0, dark_e=200.0, glow_e=50.0),  # e-
            _analog_params(fwc_e=1.0e6),
        )
        ro = out.stage_outputs["readout"]
        assert ro["total_well_e"] == pytest.approx(1250.0, rel=1e-12)  # e-
        assert ro["well_status"] == "ok"

    @pytest.mark.level1
    def test_nearfield_flips_well_status(self) -> None:
        """Owner reproduction: 6.0e7 e- near-field against a 1e5 e- well.

        Before CU-350 this reported ``ok`` at fill 0.27; the pixel actually
        rails ~600x over.
        """
        state = _make_state(signal_e=27000.0, nearfield_e=6.0e7)  # e-
        params = _analog_params(fwc_e=1.0e5)  # e-
        with pytest.warns(UserWarning, match="full well saturated"):
            out = ReadoutStage().run(state, params)
        ro = out.stage_outputs["readout"]
        assert ro["well_status"] == "clipped"
        # (27000 + 6.0e7) / 1.0e5 = 600.27
        assert ro["well_fill_fraction"] == pytest.approx(600.27, rel=1e-12)
        # Non-signal charge alone exceeds the well → no capacity for signal.
        assert ro["signal_e_final"] == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.level1
    def test_warning_names_the_included_terms(self) -> None:
        with pytest.warns(UserWarning, match=r"near-field \+ stray"):
            ReadoutStage().run(
                _make_state(signal_e=27000.0, nearfield_e=6.0e7),  # e-
                _analog_params(fwc_e=1.0e5),  # e-
            )

    @pytest.mark.level1
    @pytest.mark.parametrize("regime", ["extended", "sub_pixel", "point_source"])
    def test_applies_in_every_regime(self, regime: str) -> None:
        """No regime gate: near-field/stray are never folded into signal_e."""
        out = _run_quiet(
            _make_state(
                signal_e=1000.0,  # e-
                nearfield_e=3000.0,  # e-
                stray_e=700.0,  # e-
                regime=regime,
            ),
            _analog_params(fwc_e=1.0e6),
        )
        # 1000 + 3000 + 700 = 4700 e- (background_e is 0 in every case)
        assert out.stage_outputs["readout"]["total_well_e"] == pytest.approx(4700.0, rel=1e-12)

    @pytest.mark.level1
    def test_tdi_and_binning_scale_nearfield_and_stray(self) -> None:
        """TDI stages and on-chip binned pixels each contribute their charge."""
        n_tdi, mx_on, my_on = 8, 2, 2  # 8 stages x 4 binned pixels = 32x
        out = _run_quiet(
            _make_state(
                signal_e=100.0,  # e-
                dark_e=10.0,  # e-
                nearfield_e=300.0,  # e-
                stray_e=90.0,  # e-
            ),
            _analog_params(fwc_e=1.0e7, n_tdi=n_tdi, mx_on=mx_on, my_on=my_on),
        )
        # (100 + 10 + 300 + 90) e- x 32 = 16000 e-
        assert out.stage_outputs["readout"]["total_well_e"] == pytest.approx(16000.0, rel=1e-12)

    @pytest.mark.level1
    def test_available_capacity_shrinks_by_nearfield(self) -> None:
        """Signal is clipped to FWC minus the full non-signal pedestal."""
        out = _run_quiet(
            _make_state(signal_e=1.0e5, nearfield_e=4.0e4, stray_e=1.0e4),  # e-
            _analog_params(fwc_e=1.0e5),  # e-
        )
        ro = out.stage_outputs["readout"]
        # available = 1.0e5 - (4.0e4 + 1.0e4) = 5.0e4 e-
        assert ro["signal_e_final"] == pytest.approx(5.0e4, rel=1e-12)
        assert ro["well_status"] == "clipped"


class TestCountingWell:
    @pytest.mark.level1
    def test_nearfield_and_stray_raise_counting_total(self) -> None:
        out = _run_quiet(
            _make_state(
                signal_e=1000.0,  # e-
                dark_e=200.0,  # e-
                glow_e=50.0,  # e-
                nearfield_e=3000.0,  # e-
                stray_e=700.0,  # e-
            ),
            _counting_params(),
        )
        ro = out.stage_outputs["readout"]
        assert ro["total_well_e"] == pytest.approx(4950.0, rel=1e-12)  # e-

    @pytest.mark.level1
    def test_zero_nearfield_and_stray_is_bit_identical(self) -> None:
        out = _run_quiet(
            _make_state(signal_e=1000.0, dark_e=200.0, glow_e=50.0),  # e-
            _counting_params(),
        )
        assert out.stage_outputs["readout"]["total_well_e"] == pytest.approx(1250.0, rel=1e-12)

    @pytest.mark.level1
    def test_nearfield_flips_counting_well_status(self) -> None:
        """8-bit counter x 100 e-/count = 25600 e- effective well."""
        state = _make_state(signal_e=1000.0, nearfield_e=5.0e4)  # e-
        params = _counting_params(counter_bits=8, count_packet_e=100.0)
        with pytest.warns(UserWarning, match="digital-counting saturation"):
            out = ReadoutStage().run(state, params)
        ro = out.stage_outputs["readout"]
        assert ro["well_status"] == "clipped"
        # (1000 + 5.0e4) / 25600 e-
        assert ro["well_fill_fraction"] == pytest.approx(51000.0 / 25600.0, rel=1e-12)

    @pytest.mark.level1
    def test_tdi_and_binning_scale_in_counting_path(self) -> None:
        out = _run_quiet(
            _make_state(signal_e=100.0, dark_e=10.0, nearfield_e=300.0, stray_e=90.0),  # e-
            _counting_params(counter_bits=20, n_tdi=8, mx_on=2, my_on=2),
        )
        # (100 + 10 + 300 + 90) e- x 32 = 16000 e-
        assert out.stage_outputs["readout"]["total_well_e"] == pytest.approx(16000.0, rel=1e-12)


class TestUpDownWell:
    """The up/down branch inherits ``non_signal_e`` from the counting path."""

    @pytest.mark.level1
    def test_updown_up_phase_charge_includes_nearfield(self) -> None:
        out = _run_quiet(
            _make_state(
                signal_e=1000.0,  # e-
                dark_e=200.0,  # e-
                background_e=500.0,  # e-
                nearfield_e=3000.0,  # e-
                stray_e=700.0,  # e-
                regime="point_source",
            ),
            _counting_params(
                count_packet_e=100.0,
                readout__counting_mode="up_down",
                readout__reference_source="background_term",
            ),
        )
        # Up phase: 1000 signal + 500 background + 200 dark + 3000 nf + 700 stray
        assert out.stage_outputs["readout"]["total_well_e"] == pytest.approx(5400.0, rel=1e-12)

    @pytest.mark.level1
    def test_updown_dead_time_ceiling_sees_nearfield(self) -> None:
        """Dead-time clip: available = ceiling − full non-signal pedestal.

        f_max = 1.0e6 Hz x t = 0.01 s x Q_pkt = 100 e- → 1.0e6 e- ceiling.
        """
        out = _run_quiet(
            _make_state(
                signal_e=9.0e5,  # e-
                nearfield_e=4.0e5,  # e-
                regime="point_source",
            ),
            _counting_params(
                counter_bits=24,
                count_packet_e=100.0,
                readout__counting_mode="up_down",
                readout__reference_source="user_level",
                readout__reference_rate_e_per_s=1000.0,
                readout__max_count_rate_hz=1.0e6,
            ),
        )
        ro = out.stage_outputs["readout"]
        assert ro["saturation_mechanism"] == "dead_time"
        # available = 1.0e6 − 4.0e5 = 6.0e5 e- of signal → 1.0e6 e- total
        assert ro["total_well_e"] == pytest.approx(1.0e6, rel=1e-12)
