"""Tests for ChainQuantity backward propagation.

Level 1: TestTransferFactors (helper that crawls a multi-stage ChainState).
Level 0: forward/back propagation algebra and dataclass contracts; identities
verified against analytic ratios (1/τ, 1/g, sqrt round-trip).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.quantity import (
    ChainQuantity,
    ReferenceFrame,
    _compute_transfer_factors,
    _get_forward_factor,
    noise_at,
    signal_at,
)
from radiant.core.radiometry import NoiseTerm, RadiometricFrame


def _make_chain_state(
    signal_e: float = 10000.0,
    tau_atm_mean: float = 0.8,
    tau_opt_mean: float = 0.6,
    L_aperture_mean: float = 5.0,
    n_tdi: int = 1,
    gain: float = 1.0,
) -> ChainState:
    """Build a ChainState with transfer factors available.

    Sets up stage_outputs to enable backward propagation testing.
    """
    wl = np.linspace(3.5, 5.0, 50)
    state = ChainState(wavelength_um=wl)

    # at_aperture frame with uniform radiance
    L_aperture = np.full_like(wl, L_aperture_mean)
    at_aperture_frame = RadiometricFrame(
        name="at_aperture",
        wavelength_um=wl,
        spectral_radiance=L_aperture,
    )
    state = state.with_frame(at_aperture_frame)

    # photoelectrons frame
    pe_frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=signal_e,
        in_band_unit="e-",
    )
    state = state.with_frame(pe_frame)

    # Atmosphere stage outputs
    tau_atm = np.full_like(wl, tau_atm_mean)
    state = state.with_stage_output("atmosphere", "tau_atm", tau_atm)

    # Optics stage outputs
    tau_opt = np.full_like(wl, tau_opt_mean)
    state = state.with_stage_output("optics", "tau_opt", tau_opt)
    state = state.with_stage_output("optics", "A_collect", 0.1)
    state = state.with_stage_output("optics", "Omega_pixel", 1e-10)

    # Spectral integration outputs
    signal_e_final = signal_e * n_tdi
    state = state.with_stage_output("spectral_integration", "signal_e", signal_e)
    state = state.with_stage_output("spectral_integration", "e_rate_per_s", signal_e / 0.01)

    # Detector stage outputs
    state = state.with_stage_output("detector", "signal_e", signal_e)

    # Readout stage outputs
    signal_dn = signal_e_final / gain
    state = state.with_stage_output("readout", "signal_e_final", signal_e_final)
    state = state.with_stage_output("readout", "signal_dn_final", signal_dn)

    # Noise terms
    state = state.with_noise(
        NoiseTerm(
            name="signal_shot",
            value_e=math.sqrt(signal_e),
            origin_frame="photoelectrons",
            physical_basis="Poisson",
        )
    )
    return state.with_noise(
        NoiseTerm(
            name="read_noise",
            value_e=5.0,
            origin_frame="photoelectrons",
            physical_basis="Gaussian",
        )
    )


class TestTransferFactors:
    @pytest.mark.level1
    def test_atm_factor(self) -> None:
        state = _make_chain_state(tau_atm_mean=0.8)
        factors = _compute_transfer_factors(state)
        assert factors["at_target->at_aperture"] == pytest.approx(0.8, rel=1e-10)

    @pytest.mark.level1
    def test_opt_factor(self) -> None:
        state = _make_chain_state(tau_opt_mean=0.6)
        factors = _compute_transfer_factors(state)
        assert factors["at_aperture->post_optics"] == pytest.approx(0.6, rel=1e-10)

    @pytest.mark.level1
    def test_readout_factor(self) -> None:
        state = _make_chain_state(n_tdi=1, gain=1.0)
        factors = _compute_transfer_factors(state)
        # photoelectrons→post_readout = signal_e_final / det_signal_e
        assert "photoelectrons->post_readout" in factors
        assert factors["photoelectrons->post_readout"] == pytest.approx(1.0, rel=1e-10)

    @pytest.mark.level1
    def test_dn_factor(self) -> None:
        state = _make_chain_state(gain=2.0)
        factors = _compute_transfer_factors(state)
        # post_readout→dn = signal_dn / signal_e_final
        assert "post_readout->dn" in factors
        assert factors["post_readout->dn"] == pytest.approx(0.5, rel=1e-10)


class TestForwardFactor:
    @pytest.mark.level0
    def test_identity(self) -> None:
        factors: dict[str, float] = {}
        factor = _get_forward_factor(
            ReferenceFrame.PHOTOELECTRONS,
            ReferenceFrame.PHOTOELECTRONS,
            factors,
        )
        assert factor == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    def test_forward_one_step(self) -> None:
        factors = {"at_target->at_aperture": 0.8}
        factor = _get_forward_factor(
            ReferenceFrame.AT_TARGET,
            ReferenceFrame.AT_APERTURE,
            factors,
        )
        assert factor == pytest.approx(0.8, rel=1e-10)

    @pytest.mark.level0
    def test_backward_one_step(self) -> None:
        factors = {"at_target->at_aperture": 0.8}
        factor = _get_forward_factor(
            ReferenceFrame.AT_APERTURE,
            ReferenceFrame.AT_TARGET,
            factors,
        )
        assert factor == pytest.approx(1.0 / 0.8, rel=1e-10)

    @pytest.mark.level0
    def test_missing_factor_returns_none(self) -> None:
        factors: dict[str, float] = {}
        factor = _get_forward_factor(
            ReferenceFrame.AT_TARGET,
            ReferenceFrame.AT_APERTURE,
            factors,
        )
        assert factor is None


class TestChainQuantity:
    @pytest.mark.level0
    def test_to_same_frame(self) -> None:
        state = _make_chain_state()
        q = ChainQuantity(100.0, ReferenceFrame.PHOTOELECTRONS, "e-", "test")
        result = q.to(ReferenceFrame.PHOTOELECTRONS, state)
        assert result.value == pytest.approx(100.0, rel=1e-12)
        assert result.frame == ReferenceFrame.PHOTOELECTRONS

    @pytest.mark.level0
    def test_to_dn(self) -> None:
        """photoelectrons → post_readout → dn with gain=2."""
        state = _make_chain_state(gain=2.0)
        q = ChainQuantity(1000.0, ReferenceFrame.PHOTOELECTRONS, "e-", "test")
        result = q.to(ReferenceFrame.DN, state)
        # 1000 e- / 2.0 gain = 500 DN
        assert result.value == pytest.approx(500.0, rel=1e-10)
        assert result.unit == "DN"

    @pytest.mark.level0
    def test_frozen(self) -> None:
        q = ChainQuantity(100.0, ReferenceFrame.PHOTOELECTRONS, "e-")
        with pytest.raises(AttributeError):
            q.value = 200.0  # type: ignore[misc]


class TestSignalAt:
    @pytest.mark.level0
    def test_at_photoelectrons(self) -> None:
        state = _make_chain_state(signal_e=10000.0)
        q = signal_at(state, ReferenceFrame.PHOTOELECTRONS)
        assert q.value == pytest.approx(10000.0, rel=1e-10)
        assert q.frame == ReferenceFrame.PHOTOELECTRONS

    @pytest.mark.level0
    def test_at_dn(self) -> None:
        state = _make_chain_state(signal_e=10000.0, gain=2.0)
        q = signal_at(state, ReferenceFrame.DN)
        assert q.value == pytest.approx(5000.0, rel=1e-10)
        assert q.unit == "DN"

    @pytest.mark.level0
    def test_missing_frame_raises(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        with pytest.raises(ValueError, match="photoelectrons"):
            signal_at(state, ReferenceFrame.PHOTOELECTRONS)


class TestNoiseAt:
    @pytest.mark.level0
    def test_total_noise_at_photoelectrons(self) -> None:
        state = _make_chain_state(signal_e=10000.0)
        q = noise_at(state, ReferenceFrame.PHOTOELECTRONS)
        expected = math.sqrt(math.sqrt(10000.0) ** 2 + 5.0**2)
        assert q.value == pytest.approx(expected, rel=1e-10)
        assert q.name == "total_noise"

    @pytest.mark.level0
    def test_specific_term(self) -> None:
        state = _make_chain_state(signal_e=10000.0)
        q = noise_at(state, ReferenceFrame.PHOTOELECTRONS, term_name="read_noise")
        assert q.value == pytest.approx(5.0, rel=1e-12)
        assert q.name == "read_noise"

    @pytest.mark.level0
    def test_noise_at_dn(self) -> None:
        """Noise propagated to DN frame divides by gain."""
        state = _make_chain_state(signal_e=10000.0, gain=2.0)
        q_e = noise_at(state, ReferenceFrame.PHOTOELECTRONS, term_name="read_noise")
        q_dn = noise_at(state, ReferenceFrame.DN, term_name="read_noise")
        assert q_dn.value == pytest.approx(q_e.value / 2.0, rel=1e-10)

    @pytest.mark.level0
    def test_unknown_term_raises(self) -> None:
        state = _make_chain_state()
        with pytest.raises(ValueError, match="no noise term"):
            noise_at(state, ReferenceFrame.PHOTOELECTRONS, term_name="nonexistent")

    @pytest.mark.level0
    def test_no_noise_raises(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        with pytest.raises(ValueError, match="no noise terms"):
            noise_at(state, ReferenceFrame.PHOTOELECTRONS)


class TestRoundTrip:
    @pytest.mark.level0
    def test_pe_to_dn_and_back(self) -> None:
        """Forward to DN, backward to photoelectrons returns original."""
        state = _make_chain_state(signal_e=10000.0, gain=2.0)
        q_pe = ChainQuantity(10000.0, ReferenceFrame.PHOTOELECTRONS, "e-")
        q_dn = q_pe.to(ReferenceFrame.DN, state)
        q_pe_back = q_dn.to(ReferenceFrame.PHOTOELECTRONS, state)
        assert q_pe_back.value == pytest.approx(10000.0, rel=1e-10)

    @pytest.mark.level0
    def test_noise_round_trip(self) -> None:
        """Noise: pe → DN → pe returns original value."""
        state = _make_chain_state(signal_e=10000.0, gain=2.0)
        q1 = noise_at(state, ReferenceFrame.PHOTOELECTRONS, term_name="read_noise")
        q2 = q1.to(ReferenceFrame.DN, state)
        q3 = q2.to(ReferenceFrame.PHOTOELECTRONS, state)
        assert q3.value == pytest.approx(q1.value, rel=1e-10)
