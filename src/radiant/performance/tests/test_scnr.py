"""Tests for SCNR — signal-to-clutter-plus-noise ratio (Gap 77)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.performance.scnr import compute_scnr


def _state(contrast_e: float, sigma_temporal: float, sigma_spatial: float) -> ChainState:
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("readout", "contrast_e_final", contrast_e)
    state = state.with_stage_output("readout", "sigma_temporal_e", sigma_temporal)
    return state.with_stage_output("readout", "sigma_spatial_e", sigma_spatial)


class TestSCNR:
    @pytest.mark.level0
    def test_clutter_inclusive_denominator(self) -> None:
        """SCNR = ΔS / √(σ_temporal² + σ_spatial²) (hand calculation)."""
        r = compute_scnr(_state(1000.0, 30.0, 40.0))
        assert r.value == pytest.approx(1000.0 / math.sqrt(30.0**2 + 40.0**2), rel=1e-12)
        assert r.value == pytest.approx(1000.0 / 50.0, rel=1e-12)

    @pytest.mark.level0
    def test_scnr_below_temporal_only_snr(self) -> None:
        """Adding spatial (clutter) noise lowers SCNR vs a temporal-only ratio."""
        contrast, temporal, spatial = 1000.0, 30.0, 40.0
        scnr = compute_scnr(_state(contrast, temporal, spatial)).value
        temporal_only = contrast / temporal
        assert scnr < temporal_only

    @pytest.mark.level0
    def test_no_spatial_equals_temporal(self) -> None:
        r = compute_scnr(_state(1000.0, 25.0, 0.0))
        assert r.value == pytest.approx(1000.0 / 25.0, rel=1e-12)

    @pytest.mark.level0
    def test_negative_contrast_negative_scnr(self) -> None:
        r = compute_scnr(_state(-500.0, 30.0, 40.0))
        assert r.value < 0.0

    @pytest.mark.level0
    def test_missing_noise_split_fails_typed(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        state = state.with_stage_output("readout", "contrast_e_final", 1000.0)
        r = compute_scnr(state)
        assert math.isnan(r.value)
        assert r.failure_reason is not None

    @pytest.mark.level0
    def test_missing_contrast_fails_typed(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        r = compute_scnr(ChainState(wavelength_um=wl))
        assert math.isnan(r.value)
        assert "contrast_e" in (r.failure_reason or "")
