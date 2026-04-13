"""Tests for metric registry — can_compute and available_metrics."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.performance.registry import (
    METRIC_SPECS,
    available_metrics,
    can_compute,
    missing_for,
)


def _minimal_state() -> ChainState:
    """Bare ChainState — no frames, no noise, no outputs."""
    wl = np.linspace(3.5, 5.0, 10)
    return ChainState(wavelength_um=wl)


def _snr_ready_state() -> ChainState:
    """State with photoelectrons frame + noise terms → SNR computable."""
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    frame = RadiometricFrame(
        name="photoelectrons",
        wavelength_um=wl,
        in_band_value=10000.0,
        in_band_unit="e-",
    )
    state = state.with_frame(frame)
    return state.with_noise(
        NoiseTerm(
            name="signal_shot",
            value_e=100.0,
            origin_frame="photoelectrons",
            physical_basis="Poisson",
        )
    )


class TestCanCompute:
    def test_snr_with_dependencies(self) -> None:
        state = _snr_ready_state()
        assert can_compute("snr", state) is True

    def test_snr_without_frame(self) -> None:
        state = _minimal_state()
        state = state.with_noise(
            NoiseTerm(
                name="n",
                value_e=1.0,
                origin_frame="photoelectrons",
                physical_basis="test",
            )
        )
        assert can_compute("snr", state) is False

    def test_snr_without_noise(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        frame = RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            in_band_value=10000.0,
            in_band_unit="e-",
        )
        state = state.with_frame(frame)
        assert can_compute("snr", state) is False

    def test_unknown_metric_raises(self) -> None:
        with pytest.raises(KeyError):
            can_compute("nonexistent_metric", _minimal_state())

    def test_contrast_snr_needs_contrast_e(self) -> None:
        state = _snr_ready_state()
        assert can_compute("contrast_snr", state) is False
        state = state.with_stage_output(
            "spectral_integration",
            "contrast_e",
            500.0,
        )
        assert can_compute("contrast_snr", state) is True

    def test_saturation_margin(self) -> None:
        state = _minimal_state()
        assert can_compute("saturation_margin", state) is False
        state = state.with_stage_output("readout", "well_status", "ok")
        state = state.with_stage_output("readout", "signal_dn_pre_coadd", 1000.0)
        assert can_compute("saturation_margin", state) is True

    def test_dynamic_range(self) -> None:
        state = _minimal_state()
        assert can_compute("dynamic_range", state) is False
        state = state.with_noise(
            NoiseTerm(
                name="n",
                value_e=5.0,
                origin_frame="photoelectrons",
                physical_basis="test",
            )
        )
        assert can_compute("dynamic_range", state) is True

    def test_nedl_requires_snr_metric(self) -> None:
        state = _snr_ready_state()
        assert can_compute("nedl", state) is False
        state = state.with_metric("snr", 100.0)
        assert can_compute("nedl", state) is True


class TestAvailableMetrics:
    def test_empty_state(self) -> None:
        state = _minimal_state()
        available = available_metrics(state)
        assert len(available) == 0

    def test_snr_ready(self) -> None:
        state = _snr_ready_state()
        available = available_metrics(state)
        assert "snr" in available
        assert "dynamic_range" in available

    def test_with_snr_computed(self) -> None:
        state = _snr_ready_state()
        state = state.with_metric("snr", 100.0)
        available = available_metrics(state)
        assert "nedl" in available
        assert "nedr" in available


class TestMissingFor:
    def test_nothing_missing(self) -> None:
        state = _snr_ready_state()
        missing = missing_for("snr", state)
        assert missing == {}

    def test_missing_frame(self) -> None:
        state = _minimal_state()
        state = state.with_noise(
            NoiseTerm(
                name="n",
                value_e=1.0,
                origin_frame="photoelectrons",
                physical_basis="test",
            )
        )
        missing = missing_for("snr", state)
        assert "frames" in missing
        assert "photoelectrons" in missing["frames"]

    def test_missing_noise(self) -> None:
        wl = np.linspace(3.5, 5.0, 10)
        state = ChainState(wavelength_um=wl)
        frame = RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            in_band_value=10000.0,
            in_band_unit="e-",
        )
        state = state.with_frame(frame)
        missing = missing_for("snr", state)
        assert "noise_terms" in missing


class TestRegistryCompleteness:
    def test_all_14_metrics_registered(self) -> None:
        """All 14 metrics from docs/RADIANT_Metrics.md §4 are registered."""
        expected = {
            "snr",
            "contrast_snr",
            "nedt",
            "nedl",
            "nedr",
            "csnr",
            "niirs",
            "rer",
            "edge_slope",
            "mtf_at_nyquist",
            "ee",
            "strehl",
            "detection_range",
            "saturation_margin",
            "dynamic_range",
        }
        assert expected == set(METRIC_SPECS.keys())
