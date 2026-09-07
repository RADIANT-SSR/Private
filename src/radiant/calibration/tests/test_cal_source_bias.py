"""Level 0 — cal-source bias terms (plan §3.4).

Truth anchor 4 (plan §13.4): the photon-weighted band Planck log-derivative
at 300 K over 8–12 µm is ≈1.5–1.7 %/K (classic LWIR result). The reference
here is an independent trapezoid integral with literal CODATA constants.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration.cal_source_bias import (
    source_emissivity_bias_frac,
    source_temp_bias_frac,
)
from radiant.calibration.errors import CalibrationValidationError

_H = 6.62607015e-34
_C = 2.99792458e8
_KB = 1.380649e-23


def _log_derivative_ref(t_K: float, lam_lo_um: float, lam_hi_um: float) -> float:
    """(1/Bq)·dBq/dT for band-integrated photon radiance — independent integral."""
    lam_um = np.linspace(lam_lo_um, lam_hi_um, 4001)
    lam_m = lam_um * 1e-6
    x = _H * _C / (lam_m * _KB * t_K)
    b = (2.0 * _H * _C**2 / lam_m**5) / np.expm1(x) * 1e-6
    bq = b / (_H * _C / lam_m)  # photon radiance
    dbq = bq * (x / t_K) * np.exp(x) / np.expm1(x)  # dB/dT = B·(x/T)·e^x/(e^x−1)
    return float(np.trapezoid(dbq, lam_um) / np.trapezoid(bq, lam_um))


class TestSourceTempBias:
    def test_lwir_300K_is_the_classic_1p5_to_1p7_pct_per_K(self) -> None:
        frac = source_temp_bias_frac(delta_t_K=1.0, t_cal_K=300.0, lam_min_um=8.0, lam_max_um=12.0)
        assert 0.014 <= frac <= 0.018  # literature band, photon-weighted

    def test_matches_independent_integral_lwir(self) -> None:
        ref = _log_derivative_ref(300.0, 8.0, 12.0) * 0.5
        frac = source_temp_bias_frac(delta_t_K=0.5, t_cal_K=300.0, lam_min_um=8.0, lam_max_um=12.0)
        assert frac == pytest.approx(ref, rel=1e-3)

    def test_matches_independent_integral_mwir(self) -> None:
        # MWIR log-derivative at 300 K is far steeper (~4 %/K class).
        ref = _log_derivative_ref(300.0, 3.5, 5.0)
        frac = source_temp_bias_frac(delta_t_K=1.0, t_cal_K=300.0, lam_min_um=3.5, lam_max_um=5.0)
        assert frac == pytest.approx(ref, rel=1e-3)
        assert frac > 0.03

    def test_linear_in_delta_t(self) -> None:
        one = source_temp_bias_frac(delta_t_K=0.25, t_cal_K=300.0, lam_min_um=8.0, lam_max_um=12.0)
        four = source_temp_bias_frac(delta_t_K=1.0, t_cal_K=300.0, lam_min_um=8.0, lam_max_um=12.0)
        assert four == pytest.approx(4.0 * one, rel=1e-12)

    def test_zero_uncertainty_is_zero(self) -> None:
        assert (
            source_temp_bias_frac(delta_t_K=0.0, t_cal_K=300.0, lam_min_um=8.0, lam_max_um=12.0)
            == 0.0
        )

    def test_nonpositive_cal_temp_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="temperature"):
            source_temp_bias_frac(delta_t_K=1.0, t_cal_K=0.0, lam_min_um=8.0, lam_max_um=12.0)


class TestSourceEmissivityBias:
    def test_hand_value(self) -> None:
        # Δε/ε = 0.005/0.98 ≈ 0.005102 (hand).
        frac = source_emissivity_bias_frac(delta_eps=0.005, eps_source=0.98)
        assert frac == pytest.approx(0.005 / 0.98, rel=1e-12)

    def test_zero_uncertainty_is_zero(self) -> None:
        assert source_emissivity_bias_frac(delta_eps=0.0, eps_source=0.95) == 0.0

    def test_zero_emissivity_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="emissivity"):
            source_emissivity_bias_frac(delta_eps=0.005, eps_source=0.0)

    def test_negative_uncertainty_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="uncertainty"):
            source_emissivity_bias_frac(delta_eps=-0.005, eps_source=0.98)
