"""Tests for SNR computation.

Level 0: analytic formula checks.
Level 1: edge cases and failure modes.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.performance.snr import SNRResult, compute_snr

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    signal_e: float = 1000.0,
    noise_values: list[float] | None = None,
    *,
    include_pe_frame: bool = True,
) -> ChainState:
    """Build a minimal ChainState for SNR testing."""
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)

    if include_pe_frame:
        frame = RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            in_band_value=signal_e,
            in_band_unit="e-",
        )
        state = state.with_frame(frame)

    if noise_values is not None:
        for i, nv in enumerate(noise_values):
            state = state.with_noise(
                NoiseTerm(
                    name=f"noise_{i}",
                    value_e=nv,
                    origin_frame="photoelectrons",
                    physical_basis="test",
                )
            )

    return state


# ---------------------------------------------------------------------------
# Level 0 — formula correctness
# ---------------------------------------------------------------------------


class TestSNRFormula:
    """Verify SNR = S / RSS(noise) against hand-calculated values."""

    @pytest.mark.level0
    def test_single_noise_source(self) -> None:
        """SNR = 1000 / 100 = 10."""
        state = _make_state(signal_e=1000.0, noise_values=[100.0])
        result = compute_snr(state)
        assert result.value == pytest.approx(10.0, rel=1e-12)
        assert result.signal_e == pytest.approx(1000.0, rel=1e-12)
        assert result.noise_e == pytest.approx(100.0, rel=1e-12)
        assert result.ok is True
        assert result.failure_reason is None

    @pytest.mark.level0
    def test_multiple_noise_rss(self) -> None:
        """SNR = 500 / sqrt(300² + 400²) = 500 / 500 = 1.0."""
        state = _make_state(signal_e=500.0, noise_values=[300.0, 400.0])
        result = compute_snr(state)
        assert result.value == pytest.approx(1.0, rel=1e-12)
        assert result.noise_e == pytest.approx(500.0, rel=1e-12)

    @pytest.mark.level0
    def test_three_noise_terms(self) -> None:
        """SNR = 1000 / sqrt(10² + 20² + 30²)."""
        sigma = math.sqrt(10**2 + 20**2 + 30**2)
        state = _make_state(signal_e=1000.0, noise_values=[10.0, 20.0, 30.0])
        result = compute_snr(state)
        assert result.value == pytest.approx(1000.0 / sigma, rel=1e-12)

    @pytest.mark.level0
    def test_high_snr_regime(self) -> None:
        """Large signal, small noise → large SNR."""
        state = _make_state(signal_e=1e8, noise_values=[100.0])
        result = compute_snr(state)
        assert result.value == pytest.approx(1e6, rel=1e-12)
        assert result.ok is True


# ---------------------------------------------------------------------------
# Level 1 — edge cases and failure modes
# ---------------------------------------------------------------------------


class TestSNREdgeCases:
    """Edge cases per the SNR module docstring."""

    @pytest.mark.level1
    def test_zero_noise_returns_inf(self) -> None:
        """No noise terms → inf with 'noiseless configuration' reason."""
        state = _make_state(signal_e=1000.0, noise_values=[])
        result = compute_snr(state)
        assert result.value == float("inf")
        assert result.failure_reason == "noiseless configuration"
        assert result.ok is False

    @pytest.mark.level1
    def test_all_zero_noise_values(self) -> None:
        """Noise terms present but all zero → inf."""
        state = _make_state(signal_e=1000.0, noise_values=[0.0, 0.0])
        result = compute_snr(state)
        assert result.value == float("inf")
        assert result.failure_reason == "noiseless configuration"

    @pytest.mark.level1
    def test_zero_signal_finite_noise(self) -> None:
        """Zero signal with finite noise → SNR = 0."""
        state = _make_state(signal_e=0.0, noise_values=[10.0])
        result = compute_snr(state)
        assert result.value == pytest.approx(0.0, abs=1e-15)
        assert result.ok is True

    @pytest.mark.level1
    def test_negative_signal_returns_nan(self) -> None:
        """Negative signal → NaN with failure reason."""
        state = _make_state(signal_e=-100.0, noise_values=[10.0])
        result = compute_snr(state)
        assert math.isnan(result.value)
        assert result.failure_reason is not None
        assert "Negative signal" in result.failure_reason
        assert result.ok is False

    @pytest.mark.level1
    def test_missing_pe_frame_returns_nan(self) -> None:
        """No 'photoelectrons' frame → NaN with failure reason."""
        state = _make_state(include_pe_frame=False)
        result = compute_snr(state)
        assert math.isnan(result.value)
        assert "photoelectrons" in result.failure_reason  # type: ignore[operator]
        assert result.ok is False

    @pytest.mark.level1
    def test_none_in_band_value(self) -> None:
        """in_band_value is None (spectral-only frame) → NaN."""
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        # Create a spectral-only frame named "photoelectrons" — in_band_value is None.
        frame = RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            spectral_radiance=np.ones_like(wl),
        )
        state = state.with_frame(frame)
        state = state.with_noise(
            NoiseTerm(
                name="noise_0",
                value_e=10.0,
                origin_frame="photoelectrons",
                physical_basis="test",
            )
        )
        result = compute_snr(state)
        assert math.isnan(result.value)
        assert result.ok is False


class TestSNRResult:
    """Test the SNRResult dataclass itself."""

    @pytest.mark.level0
    def test_ok_property_finite(self) -> None:
        r = SNRResult(value=10.0, signal_e=100.0, noise_e=10.0)
        assert r.ok is True

    @pytest.mark.level0
    def test_ok_property_inf(self) -> None:
        r = SNRResult(value=float("inf"), signal_e=100.0, noise_e=0.0)
        assert r.ok is False

    @pytest.mark.level0
    def test_ok_property_nan(self) -> None:
        r = SNRResult(value=float("nan"), signal_e=0.0, noise_e=0.0, failure_reason="test")
        assert r.ok is False

    @pytest.mark.level0
    def test_ok_property_failure_reason(self) -> None:
        r = SNRResult(value=10.0, signal_e=100.0, noise_e=10.0, failure_reason="forced")
        assert r.ok is False

    @pytest.mark.level0
    def test_frozen(self) -> None:
        r = SNRResult(value=10.0, signal_e=100.0, noise_e=10.0)
        with pytest.raises(AttributeError):
            r.value = 20.0  # type: ignore[misc]
