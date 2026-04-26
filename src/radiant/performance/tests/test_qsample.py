"""Tests for sampling parameter Q computation.

Level 0: analytic formula checks on ``compute_q`` (pure function).
Level 1: ChainState wiring via ``_compute_q_metrics``.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.detector._schema import PIXEL_PITCH_X, PIXEL_PITCH_Y
from radiant.optics._schema import APERTURE_DIAMETER_M, F_NUMBER, FOCAL_LENGTH_M
from radiant.performance.qsample import SamplingResult, compute_q
from radiant.performance.stage import _compute_q_metrics
from radiant.spectral_integration._schema import FILTER_MAX_UM, FILTER_MIN_UM


def _make_params(
    f_number: float = 4.0,
    pitch_x_um: float = 18.0,
    filter_min_um: float = 3.5,
    filter_max_um: float = 5.0,
) -> ParameterSet:
    """Build a minimal ParameterSet for Q computation."""
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = [
        APERTURE_DIAMETER_M,
        FOCAL_LENGTH_M,
        F_NUMBER,
        PIXEL_PITCH_X,
        PIXEL_PITCH_Y,
        FILTER_MIN_UM,
        FILTER_MAX_UM,
    ]
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.f_number", f_number)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("detector.pixel_pitch_x_um", pitch_x_um)
    ps.set("detector.pixel_pitch_y_um", pitch_x_um)
    ps.set("spectral_integration.filter_min_um", filter_min_um)
    ps.set("spectral_integration.filter_max_um", filter_max_um)
    ps.resolve()
    return ps


def _make_state() -> ChainState:
    wl = np.linspace(3.5, 5.0, 10)
    return ChainState(wavelength_um=wl)


# ---------------------------------------------------------------------------
# Level 0 — pure function formula correctness
# ---------------------------------------------------------------------------


class TestQFormula:
    """Q = λ · f/# / p."""

    @pytest.mark.level0
    def test_mwir_f4_18um(self) -> None:
        """Tom's system: f/4, 18 µm, 3.5–5.0 µm."""
        result = compute_q(
            f_number=4.0,
            pitch_m=18e-6,
            lambda_min_um=3.5,
            lambda_max_um=5.0,
        )
        # Q_center = 4.25 * 4 / 18 = 0.9444...
        assert result.q_center == pytest.approx(4.25 * 4.0 / 18.0, rel=1e-10)
        # Q_min = 3.5 * 4 / 18 = 0.7778
        assert result.q_min == pytest.approx(3.5 * 4.0 / 18.0, rel=1e-10)
        # Q_max = 5.0 * 4 / 18 = 1.1111
        assert result.q_max == pytest.approx(5.0 * 4.0 / 18.0, rel=1e-10)

    @pytest.mark.level0
    def test_vnir_f10_8um(self) -> None:
        """VNIR system: f/10, 8 µm, 0.45–0.70 µm."""
        result = compute_q(
            f_number=10.0,
            pitch_m=8e-6,
            lambda_min_um=0.45,
            lambda_max_um=0.70,
        )
        # Q_center = 0.575 * 10 / 8 = 0.71875
        assert result.q_center == pytest.approx(0.575 * 10.0 / 8.0, rel=1e-10)

    @pytest.mark.level0
    def test_oversampled_small_pixel(self) -> None:
        """8 µm pixel at f/4, MWIR → Q > 2 (oversampled)."""
        result = compute_q(
            f_number=4.0,
            pitch_m=8e-6,
            lambda_min_um=3.5,
            lambda_max_um=5.0,
        )
        assert result.q_center == pytest.approx(4.25 * 4.0 / 8.0, rel=1e-10)
        assert result.q_center > 2.0  # heavily oversampled

    @pytest.mark.level0
    def test_undersampled_large_pixel(self) -> None:
        """30 µm pixel at f/4, MWIR → Q < 0.7 (aliased)."""
        result = compute_q(
            f_number=4.0,
            pitch_m=30e-6,
            lambda_min_um=3.5,
            lambda_max_um=5.0,
        )
        assert result.q_center == pytest.approx(4.25 * 4.0 / 30.0, rel=1e-10)
        assert result.q_center < 0.7

    @pytest.mark.level0
    def test_result_is_frozen(self) -> None:
        result = compute_q(4.0, 18e-6, 3.5, 5.0)
        assert isinstance(result, SamplingResult)
        with pytest.raises(AttributeError):
            result.q_center = 999.0  # type: ignore[misc]

    @pytest.mark.level0
    def test_q_min_less_than_q_max(self) -> None:
        """Q_min (short λ) is always less than Q_max (long λ)."""
        result = compute_q(4.0, 18e-6, 3.5, 5.0)
        assert result.q_min < result.q_center < result.q_max


# ---------------------------------------------------------------------------
# Level 1 — ChainState wiring
# ---------------------------------------------------------------------------


class TestQMetricsWiring:
    @pytest.mark.level1
    def test_metrics_populated(self) -> None:
        """Q metrics appear in ChainState for standard config."""
        state = _make_state()
        params = _make_params()
        out = _compute_q_metrics(state, params)
        assert out.metrics["q_center"] == pytest.approx(4.25 * 4.0 / 18.0, rel=1e-10)
        assert out.metrics["q_min"] == pytest.approx(3.5 * 4.0 / 18.0, rel=1e-10)
        assert out.metrics["q_max"] == pytest.approx(5.0 * 4.0 / 18.0, rel=1e-10)
