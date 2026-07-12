"""Tests for the metric registry — metadata, can_compute, available_metrics.

The registry is reconciled with what PerformanceStage actually computes
(CU-078); the chain-level reconciliation test lives in
tests/integration/test_metric_registry_reconciliation.py.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm, RadiometricFrame
from radiant.performance.registry import (
    METRIC_SPECS,
    MetricSpec,
    available_metrics,
    can_compute,
    metric_info,
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


class TestMetadata:
    @pytest.mark.level1
    def test_every_spec_has_nonempty_unit(self) -> None:
        """Project hard rule: every displayed value carries units."""
        for name, spec in METRIC_SPECS.items():
            assert spec.unit, f"MetricSpec '{name}' has an empty unit"

    @pytest.mark.level1
    def test_every_spec_has_description(self) -> None:
        for name, spec in METRIC_SPECS.items():
            assert spec.description, f"MetricSpec '{name}' has an empty description"

    @pytest.mark.level1
    def test_spec_names_match_keys(self) -> None:
        for name, spec in METRIC_SPECS.items():
            assert spec.name == name

    @pytest.mark.level1
    def test_empty_unit_rejected(self) -> None:
        with pytest.raises(ValueError, match="unit must be a non-empty"):
            MetricSpec(name="x", unit="", description="d")

    @pytest.mark.level1
    def test_bad_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            MetricSpec(name="x", unit="m", description="d", kind="vibe")

    @pytest.mark.level1
    def test_metric_info_lookup(self) -> None:
        assert metric_info("nedt_K").unit == "K"
        assert metric_info("niirs_extrapolated").kind == "flag"
        assert metric_info("sampling_regime_code").kind == "code"

    @pytest.mark.level1
    def test_metric_info_unknown_names_known(self) -> None:
        with pytest.raises(KeyError, match="Registered metrics"):
            metric_info("nonexistent_metric")

    @pytest.mark.level1
    def test_requires_metrics_reference_registered_names(self) -> None:
        """Dependency closure: requires_metrics must name registered specs."""
        for name, spec in METRIC_SPECS.items():
            for dep in spec.requires_metrics:
                assert dep in METRIC_SPECS, f"'{name}' requires unregistered metric '{dep}'"

    @pytest.mark.level1
    def test_phantom_metrics_absent(self) -> None:
        """CU-078: the four never-computed metrics were removed; they return
        with the commits that compute them (Gaps 77/78)."""
        for phantom in ("nedl", "nedr", "edge_slope", "detection_range", "csnr", "ee", "nedt"):
            assert phantom not in METRIC_SPECS


class TestCanCompute:
    @pytest.mark.level1
    def test_snr_with_dependencies(self) -> None:
        assert can_compute("snr", _snr_ready_state()) is True

    @pytest.mark.level1
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

    @pytest.mark.level1
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

    @pytest.mark.level1
    def test_unknown_metric_raises(self) -> None:
        with pytest.raises(KeyError):
            can_compute("nonexistent_metric", _minimal_state())

    @pytest.mark.level1
    def test_contrast_snr_needs_contrast_e(self) -> None:
        state = _snr_ready_state()
        assert can_compute("contrast_snr", state) is False
        state = state.with_stage_output("spectral_integration", "contrast_e", 500.0)
        assert can_compute("contrast_snr", state) is True

    @pytest.mark.level1
    def test_well_margin_needs_readout_signal(self) -> None:
        state = _minimal_state()
        assert can_compute("well_margin_dB", state) is False
        state = state.with_stage_output("readout", "signal_e_final", 50000.0)
        assert can_compute("well_margin_dB", state) is True

    @pytest.mark.level1
    def test_dynamic_range_needs_sigma_temporal(self) -> None:
        state = _minimal_state()
        assert can_compute("dynamic_range_dB", state) is False
        state = state.with_stage_output("readout", "sigma_temporal_e", 12.0)
        assert can_compute("dynamic_range_dB", state) is True

    @pytest.mark.level1
    def test_mrt_requires_nedt_and_mtf(self) -> None:
        state = _snr_ready_state()
        assert can_compute("mrt_at_nyquist_K", state) is False
        state = state.with_metric("nedt_K", 0.05)
        state = state.with_metric("mtf_at_nyquist", 0.3)
        assert can_compute("mrt_at_nyquist_K", state) is True

    @pytest.mark.level1
    def test_mtf_product_metrics_need_terms_and_grid(self) -> None:
        state = _minimal_state()
        assert can_compute("mtf_system_at_nyquist_x", state) is False
        state = state.with_mtf("optics", np.linspace(1.0, 0.1, 8))
        assert can_compute("mtf_system_at_nyquist_x", state) is False  # grid missing
        state = state.with_spatial_freq(np.linspace(0.0, 10.0, 8))
        assert can_compute("mtf_system_at_nyquist_x", state) is True


class TestAvailableMetrics:
    @pytest.mark.level1
    def test_empty_state_offers_only_parameter_gated(self) -> None:
        """With no state, only parameter-gated (no state deps) metrics show."""
        available = available_metrics(_minimal_state())
        # These have no state-level requirements — they are parameter-gated.
        assert available <= {
            "gsd_cross_track_m",
            "gsd_along_track_m",
            "ground_range_m",
            "q_center",
            "q_min",
            "q_max",
            "diffraction_limit_angular_urad",
        }

    @pytest.mark.level1
    def test_snr_ready(self) -> None:
        assert "snr" in available_metrics(_snr_ready_state())

    @pytest.mark.level1
    def test_niirs_unlocks_with_dependencies(self) -> None:
        state = _snr_ready_state()
        assert "niirs" not in available_metrics(state)
        for dep, val in (
            ("snr", 100.0),
            ("rer", 0.5),
            ("gsd_along_track_m", 0.5),
            ("gsd_cross_track_m", 0.5),
        ):
            state = state.with_metric(dep, val)
        assert "niirs" in available_metrics(state)


class TestMissingFor:
    @pytest.mark.level1
    def test_nothing_missing(self) -> None:
        assert missing_for("snr", _snr_ready_state()) == {}

    @pytest.mark.level1
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

    @pytest.mark.level1
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
        assert "noise_terms" in missing_for("snr", state)

    @pytest.mark.level1
    def test_missing_mtf_terms(self) -> None:
        assert "mtf_terms" in missing_for("mtf_folded_at_nyquist", _minimal_state())
