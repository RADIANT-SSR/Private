"""Tests for ChainResult backward propagation queries."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.quantity import ReferenceFrame
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.io.results import ChainResult


def _make_result(
    signal_e: float = 10000.0,
    gain: float = 2.0,
) -> ChainResult:
    """Build a ChainResult with enough state for backward propagation."""
    wl = np.linspace(3.5, 5.0, 50)
    state = ChainState(wavelength_um=wl)

    pe_frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=signal_e,
        in_band_unit="e-",
    )
    state = state.with_frame(pe_frame)

    # Detector + readout outputs
    state = state.with_stage_output("detector", "signal_e", signal_e)
    signal_dn = signal_e / gain
    state = state.with_stage_output("readout", "signal_e_final", signal_e)
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
    state = state.with_noise(
        NoiseTerm(
            name="read_noise",
            value_e=5.0,
            origin_frame="photoelectrons",
            physical_basis="Gaussian",
        )
    )

    return ChainResult(state)


class TestChainResultSignalAt:
    def test_signal_at_photoelectrons(self) -> None:
        result = _make_result(signal_e=10000.0)
        q = result.signal_at("photoelectrons")
        assert q.value == pytest.approx(10000.0, rel=1e-10)

    def test_signal_at_dn(self) -> None:
        result = _make_result(signal_e=10000.0, gain=2.0)
        q = result.signal_at(ReferenceFrame.DN)
        assert q.value == pytest.approx(5000.0, rel=1e-10)

    def test_signal_at_string(self) -> None:
        result = _make_result(signal_e=10000.0, gain=2.0)
        q = result.signal_at("dn")
        assert q.value == pytest.approx(5000.0, rel=1e-10)


class TestChainResultNoiseAt:
    def test_total_noise(self) -> None:
        result = _make_result(signal_e=10000.0)
        q = result.noise_at("photoelectrons")
        expected = math.sqrt(100.0**2 + 5.0**2)
        assert q.value == pytest.approx(expected, rel=1e-10)

    def test_specific_term(self) -> None:
        result = _make_result()
        q = result.noise_at("photoelectrons", term_name="read_noise")
        assert q.value == pytest.approx(5.0, rel=1e-12)

    def test_noise_at_dn(self) -> None:
        result = _make_result(signal_e=10000.0, gain=2.0)
        q = result.noise_at("dn", term_name="read_noise")
        # 5 e- / 2 gain = 2.5 DN
        assert q.value == pytest.approx(2.5, rel=1e-10)

    def test_round_trip(self) -> None:
        result = _make_result(signal_e=10000.0, gain=2.0)
        q1 = result.noise_at("photoelectrons", term_name="read_noise")
        q2 = result.noise_at("dn", term_name="read_noise")
        # Back to PE: q2 × gain = q1
        q3 = q2.to(ReferenceFrame.PHOTOELECTRONS, result.state)
        assert q3.value == pytest.approx(q1.value, rel=1e-10)


class TestChainResultDeprecatedAliases:
    """CU-NEW-03 — `signal_at_frame` / `noise_at_frame` kept as deprecated
    aliases for one minor version. They must emit DeprecationWarning and
    return the same value as the new method names.
    """

    def test_signal_at_frame_emits_deprecation_warning(self) -> None:
        result = _make_result(signal_e=10000.0)
        with pytest.warns(DeprecationWarning, match="signal_at_frame"):
            q = result.signal_at_frame("photoelectrons")
        assert q.value == pytest.approx(10000.0, rel=1e-10)

    def test_noise_at_frame_emits_deprecation_warning(self) -> None:
        result = _make_result()
        with pytest.warns(DeprecationWarning, match="noise_at_frame"):
            q = result.noise_at_frame("photoelectrons", term_name="read_noise")
        assert q.value == pytest.approx(5.0, rel=1e-12)

    def test_deprecated_alias_returns_same_value(self) -> None:
        result = _make_result(signal_e=10000.0, gain=2.0)
        q_new = result.signal_at("dn")
        with pytest.warns(DeprecationWarning):
            q_old = result.signal_at_frame("dn")
        assert q_old.value == pytest.approx(q_new.value, rel=1e-12)


class TestChainResultMetricAccessors:
    """CU-NEW-03 — `result.snr()` / `nedt()` / `niirs()` convenience accessors."""

    def _result_with_metrics(self) -> ChainResult:
        wl = np.linspace(3.5, 5.0, 50)
        state = ChainState(wavelength_um=wl)
        state = state.with_metric("snr", 47.3)
        state = state.with_metric("nedt_K", 0.023)
        state = state.with_metric("niirs", 5.4)
        return ChainResult(state)

    def test_snr_accessor(self) -> None:
        result = self._result_with_metrics()
        assert result.snr() == pytest.approx(47.3, rel=1e-12)

    def test_nedt_accessor_returns_kelvin(self) -> None:
        result = self._result_with_metrics()
        assert result.nedt() == pytest.approx(0.023, rel=1e-12)

    def test_niirs_accessor(self) -> None:
        result = self._result_with_metrics()
        assert result.niirs() == pytest.approx(5.4, rel=1e-12)

    def test_metric_accessor_raises_keyerror_when_unavailable(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        result = ChainResult(ChainState(wavelength_um=wl))
        with pytest.raises(KeyError):
            result.snr()
