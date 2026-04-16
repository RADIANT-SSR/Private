"""Tests for Strehl ratio (Marechal approximation).

Level 0: analytic formula checks on ``compute_strehl`` (pure function).
Level 1: ChainState wiring via ``_compute_strehl_metric``.

Truth anchors:
  1. Zero WFE → Strehl = 1.0 (definition)
  2. λ/14 RMS at 633 nm, operating at 633 nm → Strehl ≈ 0.8187
     (Marechal 1947; Born & Wolf §9)
  3. λ/14 RMS at 633 nm, operating at 4.0 µm → Strehl ≈ 0.9995
     (WFE becomes negligible at longer wavelength)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.performance.strehl import compute_strehl
from radiant.performance.stage import _compute_strehl_metric

from radiant.optics._schema import (
    APERTURE_DIAMETER_M,
    FOCAL_LENGTH_M,
    F_NUMBER,
    WFE_REFERENCE_WAVELENGTH_UM,
    WFE_RMS_WAVES,
)
from radiant.spectral_integration._schema import FILTER_MIN_UM, FILTER_MAX_UM


def _make_params(
    wfe_rms_waves: float = 0.0,
    wfe_ref_um: float = 0.633,
    filter_min_um: float = 3.5,
    filter_max_um: float = 5.0,
) -> ParameterSet:
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = [APERTURE_DIAMETER_M, FOCAL_LENGTH_M, F_NUMBER,
              WFE_RMS_WAVES, WFE_REFERENCE_WAVELENGTH_UM,
              FILTER_MIN_UM, FILTER_MAX_UM]
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("optics.f_number", 4.0)
    ps.set("optics.wfe_rms_waves", wfe_rms_waves)
    ps.set("optics.wfe_reference_wavelength_um", wfe_ref_um)
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


class TestStrehlFormula:
    def test_zero_wfe_gives_unity(self) -> None:
        """Truth anchor 1: perfect optics → Strehl = 1.0 exactly."""
        assert compute_strehl(0.0, 0.633, 4.25) == 1.0

    def test_lambda_over_14_at_ref_wavelength(self) -> None:
        """Truth anchor 2: λ/14 RMS at 633 nm, operating at 633 nm.

        Marechal: S = exp(-(2π/14)²) = exp(-0.2013) ≈ 0.8176.
        """
        wfe = 1.0 / 14.0  # waves
        expected = math.exp(-(2.0 * math.pi / 14.0) ** 2)
        result = compute_strehl(wfe, 0.633, 0.633)
        assert result == pytest.approx(expected, rel=1e-10)

    def test_lambda_over_14_at_mwir(self) -> None:
        """Truth anchor 3: λ/14 at 633 nm, operating at 4.0 µm.

        OPD_rms = (1/14) × 0.633 = 0.04521 µm.
        Phase variance = (2π × 0.04521 / 4.0)² = 0.00507.
        Strehl = exp(-0.00507) ≈ 0.9949.
        """
        wfe = 1.0 / 14.0
        opd_rms_um = wfe * 0.633
        expected = math.exp(-(2.0 * math.pi * opd_rms_um / 4.0) ** 2)
        result = compute_strehl(wfe, 0.633, 4.0)
        assert result == pytest.approx(expected, rel=1e-10)

    def test_strehl_decreases_with_wfe(self) -> None:
        """More WFE → lower Strehl."""
        s1 = compute_strehl(0.05, 0.633, 4.25)
        s2 = compute_strehl(0.10, 0.633, 4.25)
        s3 = compute_strehl(0.20, 0.633, 4.25)
        assert s1 > s2 > s3

    def test_strehl_increases_with_longer_wavelength(self) -> None:
        """Same WFE looks better at longer wavelengths."""
        s_short = compute_strehl(0.10, 0.633, 1.0)
        s_long = compute_strehl(0.10, 0.633, 10.0)
        assert s_long > s_short


# ---------------------------------------------------------------------------
# Level 1 — ChainState wiring
# ---------------------------------------------------------------------------


class TestStrehlMetricsWiring:
    def test_strehl_in_metrics(self) -> None:
        """Strehl appears in result.metrics."""
        state = _make_state()
        params = _make_params(wfe_rms_waves=1.0 / 14.0, wfe_ref_um=0.633)
        out = _compute_strehl_metric(state, params)

        # Operating wavelength = band center = (3.5 + 5.0) / 2 = 4.25 µm
        opd_rms_um = (1.0 / 14.0) * 0.633
        expected = math.exp(-(2.0 * math.pi * opd_rms_um / 4.25) ** 2)
        assert out.metrics["strehl"] == pytest.approx(expected, rel=1e-10)

    def test_zero_wfe_default(self) -> None:
        """Default WFE = 0 → Strehl = 1.0."""
        state = _make_state()
        params = _make_params(wfe_rms_waves=0.0)
        out = _compute_strehl_metric(state, params)
        assert out.metrics["strehl"] == 1.0
