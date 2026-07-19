"""Tests for NIIRS dispatcher, IIRS, and stage wiring.

Level 0: dispatcher and IIRS pure function tests.
Level 1: ChainState wiring test for _compute_niirs_metric.

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.performance.iirs import compute_iirs
from radiant.performance.niirs import compute_niirs
from radiant.performance.stage import _classify_band, _compute_niirs_metric


class TestNIIRSDispatcher:
    @pytest.mark.level0
    def test_vis_uses_giqe5(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="vis")
        assert result.niirs > 0

    @pytest.mark.level0
    def test_mwir_uses_iirs(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="mwir")
        assert result.niirs > 0

    @pytest.mark.level0
    def test_lwir_uses_iirs(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="lwir")
        assert result.niirs > 0

    @pytest.mark.level0
    def test_vis_equals_giqe5_directly(self) -> None:
        """Dispatcher result for 'vis' should match direct GIQE-5."""
        from radiant.performance.giqe import compute_giqe5

        r1 = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="vis")
        r2 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert r1.niirs == r2.niirs


class TestIIRS:
    @pytest.mark.level0
    def test_basic(self) -> None:
        result = compute_iirs(1.0, 1.0, 0.7, 0.7, 50.0)
        assert result.niirs > 0

    @pytest.mark.level0
    def test_same_as_giqe5_for_v1(self) -> None:
        """For v1, IIRS uses the same GIQE-5 formula."""
        from radiant.performance.giqe import compute_giqe5

        r_iirs = compute_iirs(1.0, 1.0, 0.7, 0.7, 50.0)
        r_giqe = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert r_iirs.niirs == r_giqe.niirs


# ---------------------------------------------------------------------------
# Level 0 — band classification
# ---------------------------------------------------------------------------


class TestClassifyBand:
    @pytest.mark.level0
    def test_vis(self) -> None:
        assert _classify_band(0.55) == "vis"

    @pytest.mark.level0
    def test_nir(self) -> None:
        assert _classify_band(1.6) == "nir"

    @pytest.mark.level0
    def test_mwir(self) -> None:
        assert _classify_band(4.25) == "mwir"

    @pytest.mark.level0
    def test_lwir(self) -> None:
        assert _classify_band(10.0) == "lwir"

    @pytest.mark.level0
    def test_boundary_1um(self) -> None:
        """1.0 µm is NIR (not VIS)."""
        assert _classify_band(1.0) == "nir"

    @pytest.mark.level0
    def test_boundary_2_5um(self) -> None:
        """2.5 µm is MWIR."""
        assert _classify_band(2.5) == "mwir"

    @pytest.mark.level0
    def test_boundary_7um(self) -> None:
        """7.0 µm is LWIR."""
        assert _classify_band(7.0) == "lwir"


# ---------------------------------------------------------------------------
# Level 1 — ChainState wiring
# ---------------------------------------------------------------------------


def _make_niirs_params(
    filter_min_um: float = 0.45,
    filter_max_um: float = 0.70,
) -> ParameterSet:
    """Build a minimal ParameterSet with filter bounds for NIIRS wiring."""
    from radiant.spectral_integration._schema import FILTER_MAX_UM, FILTER_MIN_UM

    schema = [FILTER_MIN_UM, FILTER_MAX_UM]
    ps = ParameterSet(schema)
    ps.set("spectral_integration.filter_min_um", filter_min_um)
    ps.set("spectral_integration.filter_max_um", filter_max_um)
    ps.resolve()
    return ps


def _make_state_with_metrics(
    snr: float = 50.0,
    rer: float = 0.7,
    gsd_along: float = 1.0,
    gsd_cross: float = 1.0,
) -> ChainState:
    """Build a ChainState with GSD, RER, SNR in metrics."""
    wl = np.linspace(0.45, 0.70, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", snr)
    state = state.with_metric("rer", rer)
    state = state.with_metric("gsd_along_track_m", gsd_along)
    return state.with_metric("gsd_cross_track_m", gsd_cross)


class TestNIIRSMetricsWiring:
    @pytest.mark.level1
    def test_niirs_in_metrics(self) -> None:
        """NIIRS appears in metrics for a VIS orbital scenario."""
        state = _make_state_with_metrics()
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)

        assert "niirs" in out.metrics
        assert out.metrics["niirs"] > 0.0

    @pytest.mark.level1
    def test_niirs_consistent_with_pure_function(self) -> None:
        """Wiring gives same result as calling compute_niirs directly."""
        snr, rer, gsd = 100.0, 0.5, 0.8
        state = _make_state_with_metrics(snr=snr, rer=rer, gsd_along=gsd, gsd_cross=gsd)
        params = _make_niirs_params(filter_min_um=0.45, filter_max_um=0.70)
        out = _compute_niirs_metric(state, params)

        direct = compute_niirs(gsd, gsd, rer, rer, snr, band="vis")
        assert out.metrics["niirs"] == pytest.approx(direct.niirs, rel=1e-10)

    @pytest.mark.level1
    def test_mwir_band_dispatches_to_iirs(self) -> None:
        """MWIR filter bounds should dispatch to IIRS."""
        state = _make_state_with_metrics()
        params = _make_niirs_params(filter_min_um=3.5, filter_max_um=5.0)
        out = _compute_niirs_metric(state, params)

        direct = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="mwir")
        assert out.metrics["niirs"] == pytest.approx(direct.niirs, rel=1e-10)

    @pytest.mark.level1
    def test_missing_gsd_skips(self) -> None:
        """No GSD → NIIRS not computed."""
        wl = np.linspace(0.45, 0.70, 10)
        state = ChainState(wavelength_um=wl)
        state = state.with_metric("snr", 50.0)
        state = state.with_metric("rer", 0.7)
        # No GSD metrics
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)
        assert "niirs" not in out.metrics

    @pytest.mark.level1
    def test_missing_rer_skips(self) -> None:
        """No RER → NIIRS not computed."""
        wl = np.linspace(0.45, 0.70, 10)
        state = ChainState(wavelength_um=wl)
        state = state.with_metric("snr", 50.0)
        state = state.with_metric("gsd_along_track_m", 1.0)
        state = state.with_metric("gsd_cross_track_m", 1.0)
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)
        assert "niirs" not in out.metrics

    @pytest.mark.level1
    def test_zero_snr_skips(self) -> None:
        """SNR = 0 → NIIRS not computed."""
        state = _make_state_with_metrics(snr=0.0)
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)
        assert "niirs" not in out.metrics

    @pytest.mark.level1
    def test_niirs_result_in_stage_outputs(self) -> None:
        """GIQEResult stored in stage outputs."""
        state = _make_state_with_metrics()
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)

        assert "niirs_result" in out.stage_outputs["performance"]
        result = out.stage_outputs["performance"]["niirs_result"]
        assert result.niirs == out.metrics["niirs"]


class TestExtrapolationFlag:
    """Gap 22: chain surfaces GIQE-5 calibration-range extrapolation."""

    def test_in_range_flag_zero(self) -> None:
        result = compute_niirs(0.3, 0.3, 0.5, 0.5, 50.0, band="vis")
        assert result.extrapolated is False

    def test_iirs_path_also_flagged(self) -> None:
        """MWIR dispatch inherits the calibration checks."""
        result = compute_niirs(0.3, 0.3, 0.1, 0.1, 50.0, band="mwir")
        assert result.extrapolated is True
        assert any("RER" in w for w in result.warnings)

    def test_compute_niirs_emits_no_warning(self, recwarn) -> None:  # type: ignore[no-untyped-def]
        """CU-166: the calibration-range check is structured status only —
        `compute_niirs` never raises a Python warning, even out of range."""
        result = compute_niirs(100.0, 100.0, 0.1, 0.1, 1000.0, band="vis")
        assert result.extrapolated is True  # GSD, RER, SNR all out of range
        assert len(recwarn) == 0

    def test_niirs_metric_wiring_emits_no_warning(self, recwarn) -> None:  # type: ignore[no-untyped-def]
        """CU-166: an out-of-calibration NIIRS through the chain wiring flags
        `niirs_extrapolated` but emits no `UserWarning` (owner bar: a valid
        scenario evaluates warning-free)."""
        # Default GSD 1.0 m = 39.4 inch is already past the [1.18, 31.5] range.
        state = _make_state_with_metrics()
        params = _make_niirs_params()
        out = _compute_niirs_metric(state, params)
        assert out.metrics["niirs_extrapolated"] == 1.0
        assert out.stage_outputs["performance"]["niirs_result"].extrapolated is True
        assert len(recwarn) == 0
