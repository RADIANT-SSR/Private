"""Level 0 tests for radiant.api.calibration_analysis (Gap 46).

Truth anchors are synthetic calibration data with known fits (Rule 18):

- Perfect data: measured = predicted → gain_scale = 1.0, offset = 0.0,
  linearity residuals = 0.
- Known responsivity: DN = 100·L → dDN/dL = 100.
- Uncertainty: σ_DN = 50, dDN/dT = 25 DN/K → σ_T = 2 K single frame,
  0.2 K over 100 frames.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.calibration_analysis import (
    CalibrationAnalysisError,
    analyze_calibration,
    gain_offset_fit,
    linearity_residuals_pct_fs,
    radiance_responsivity_dn_per_radiance,
    temperature_calibration_uncertainty_k,
    temperature_responsivity_dn_per_k,
)


class TestGainOffset:
    def test_perfect_fit(self) -> None:
        dn = np.array([100.0, 200.0, 300.0, 400.0])
        a, b = gain_offset_fit(dn, dn)
        assert a == pytest.approx(1.0, abs=1e-9)
        assert b == pytest.approx(0.0, abs=1e-9)

    def test_gain_and_offset(self) -> None:
        pred = np.array([0.0, 100.0, 200.0, 300.0])
        meas = 1.1 * pred + 20.0
        a, b = gain_offset_fit(pred, meas)
        assert a == pytest.approx(1.1, rel=1e-9)
        assert b == pytest.approx(20.0, abs=1e-6)

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(CalibrationAnalysisError, match="same length"):
            gain_offset_fit(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0]))


class TestResponsivity:
    def test_radiance_slope(self) -> None:
        L = np.array([1.0, 2.0, 3.0, 4.0])
        dn = 100.0 * L + 5.0
        assert radiance_responsivity_dn_per_radiance(dn, L) == pytest.approx(100.0, rel=1e-9)

    def test_temperature_gradient(self) -> None:
        temps = np.array([250.0, 260.0, 270.0, 280.0])
        dn = 25.0 * temps  # dDN/dT = 25 everywhere
        grad = temperature_responsivity_dn_per_k(dn, temps)
        assert np.allclose(grad, 25.0, atol=1e-9)


class TestLinearity:
    def test_perfectly_linear_zero_residual(self) -> None:
        L = np.array([1.0, 2.0, 3.0, 4.0])
        dn = 100.0 * L + 5.0
        resid, max_pct = linearity_residuals_pct_fs(L, dn, full_scale_dn=4095.0)
        assert max_pct == pytest.approx(0.0, abs=1e-9)
        assert np.allclose(resid, 0.0, atol=1e-9)

    def test_bad_full_scale_raises(self) -> None:
        with pytest.raises(CalibrationAnalysisError, match="full_scale_dn"):
            linearity_residuals_pct_fs(np.array([1.0, 2.0]), np.array([1.0, 2.0]), 0.0)


class TestUncertainty:
    def test_single_and_nframe(self) -> None:
        assert temperature_calibration_uncertainty_k(50.0, 25.0) == pytest.approx(2.0, rel=1e-12)
        assert temperature_calibration_uncertainty_k(50.0, 25.0, 100) == pytest.approx(
            0.2, rel=1e-12
        )

    def test_zero_responsivity_raises(self) -> None:
        with pytest.raises(CalibrationAnalysisError, match="dn_per_k"):
            temperature_calibration_uncertainty_k(50.0, 0.0)


class TestReport:
    def test_end_to_end(self) -> None:
        temps = np.array([250.0, 260.0, 270.0, 280.0, 290.0])
        L = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        dn_pred = 100.0 * L + 10.0
        dn_meas = dn_pred.copy()
        sigma = np.full(5, 50.0)
        rep = analyze_calibration(temps, L, dn_pred, dn_meas, sigma, full_scale_dn=4095.0)
        assert rep.gain_scale == pytest.approx(1.0, abs=1e-9)
        assert rep.offset_dn == pytest.approx(0.0, abs=1e-6)
        assert rep.dn_per_radiance == pytest.approx(100.0, rel=1e-9)
        assert rep.max_linearity_pct_fs == pytest.approx(0.0, abs=1e-9)
        # 100-frame uncertainty is 1/10 the single-frame.
        assert np.allclose(rep.sigma_t_nframe_k, rep.sigma_t_single_frame_k / 10.0, rtol=1e-9)
