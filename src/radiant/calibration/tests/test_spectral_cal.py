"""Level 0 tests for the spectral-calibration bias term (Gap 122 item 3).

Key equations (written before the implementation, Rule 18):

    g(T) = [Bq(λ_max, T) − Bq(λ_min, T)] / ∫_band Bq(λ, T) dλ     [1/µm]
    ΔL/L = |g(T_scene) − g(T_cal)| · δλ                            [fraction]

g is the log-derivative of the photon-weighted band integral under a rigid
band shift; the calibration absorbs the scale error at its own temperature,
so only the scene-vs-cal *difference* survives as a residual bias — zero at
T_scene = T_cal, growing with the temperature separation.

Truth anchors (hand calculation, CODATA 2018 constants, 200001-point
trapezoid — independent of RADIANT code):

    A: g(300 K, 4.0–4.1 µm)                  = 1.934725 /µm
    B: g(320 K, 3.5–5.0 µm)                  = 1.370370 /µm
       g(300 K, 3.5–5.0 µm)                  = 1.500106 /µm
       bias(320 vs 300, δλ = 0.01 µm)        = 1.297357e-3
       exact finite-shift of the same case   = 1.295258e-3 (0.16 % lin. error)
    C: LWIR 8–12 µm, |g(320) − g(300)|       = 2.738973e-2 /µm
       (flatter than MWIR — Wien-side bands are the sensitive ones)
"""

from __future__ import annotations

import pytest

from radiant.calibration.errors import CalibrationValidationError
from radiant.calibration.spectral_cal import (
    band_shift_log_derivative,
    spectral_cal_bias_frac,
)


class TestBandShiftLogDerivative:
    @pytest.mark.level0
    def test_narrow_mwir_anchor(self) -> None:
        """Truth anchor A (hand calculation)."""
        g = band_shift_log_derivative(t_K=300.0, lam_min_um=4.0, lam_max_um=4.1)
        assert g == pytest.approx(1.934725, rel=1e-4)

    @pytest.mark.level0
    def test_wide_mwir_anchors(self) -> None:
        """Truth anchor B (hand calculation), both temperatures."""
        g320 = band_shift_log_derivative(t_K=320.0, lam_min_um=3.5, lam_max_um=5.0)
        g300 = band_shift_log_derivative(t_K=300.0, lam_min_um=3.5, lam_max_um=5.0)
        assert g320 == pytest.approx(1.370370, rel=1e-4)
        assert g300 == pytest.approx(1.500106, rel=1e-4)


class TestSpectralCalBias:
    @pytest.mark.level0
    def test_mwir_bias_anchor(self) -> None:
        """Truth anchor B: 20 K scene-cal separation, 10 nm shift, MWIR."""
        bias = spectral_cal_bias_frac(
            delta_lam_um=0.01,
            t_scene_K=320.0,
            t_cal_K=300.0,
            lam_min_um=3.5,
            lam_max_um=5.0,
        )
        assert bias == pytest.approx(1.297357e-3, rel=1e-3)

    @pytest.mark.level0
    def test_zero_at_cal_temperature(self) -> None:
        """The calibration absorbs the scale error at its own temperature."""
        bias = spectral_cal_bias_frac(
            delta_lam_um=0.05,
            t_scene_K=300.0,
            t_cal_K=300.0,
            lam_min_um=3.5,
            lam_max_um=5.0,
        )
        assert bias == 0.0

    @pytest.mark.level0
    def test_lwir_less_sensitive_than_mwir(self) -> None:
        """Truth anchor C: Wien-side bands feel a band shift more strongly."""
        kwargs: dict[str, float] = {"delta_lam_um": 0.01, "t_scene_K": 320.0, "t_cal_K": 300.0}
        mwir = spectral_cal_bias_frac(lam_min_um=3.5, lam_max_um=5.0, **kwargs)
        lwir = spectral_cal_bias_frac(lam_min_um=8.0, lam_max_um=12.0, **kwargs)
        assert lwir == pytest.approx(2.738973e-4, rel=1e-3)
        assert mwir > lwir

    @pytest.mark.level0
    def test_magnitude_symmetric_in_temperature_swap(self) -> None:
        """δλ is a symmetric 1-σ uncertainty: the term is a magnitude."""
        a = spectral_cal_bias_frac(
            delta_lam_um=0.01, t_scene_K=320.0, t_cal_K=300.0, lam_min_um=3.5, lam_max_um=5.0
        )
        b = spectral_cal_bias_frac(
            delta_lam_um=0.01, t_scene_K=300.0, t_cal_K=320.0, lam_min_um=3.5, lam_max_um=5.0
        )
        assert a == pytest.approx(b, rel=1e-12)
        assert a > 0.0

    @pytest.mark.level0
    def test_zero_uncertainty_is_zero(self) -> None:
        bias = spectral_cal_bias_frac(
            delta_lam_um=0.0, t_scene_K=320.0, t_cal_K=300.0, lam_min_um=3.5, lam_max_um=5.0
        )
        assert bias == 0.0

    @pytest.mark.level0
    def test_scales_linearly_in_shift(self) -> None:
        kwargs: dict[str, float] = {
            "t_scene_K": 320.0,
            "t_cal_K": 300.0,
            "lam_min_um": 3.5,
            "lam_max_um": 5.0,
        }
        b1 = spectral_cal_bias_frac(delta_lam_um=0.01, **kwargs)
        b2 = spectral_cal_bias_frac(delta_lam_um=0.02, **kwargs)
        assert b2 == pytest.approx(2.0 * b1, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("delta_lam_um", -0.01),
            ("delta_lam_um", float("nan")),
            ("t_scene_K", 0.0),
            ("t_cal_K", -10.0),
        ],
    )
    def test_invalid_inputs_rejected(self, field: str, value: float) -> None:
        kwargs: dict[str, float] = {
            "delta_lam_um": 0.01,
            "t_scene_K": 320.0,
            "t_cal_K": 300.0,
            "lam_min_um": 3.5,
            "lam_max_um": 5.0,
        }
        kwargs[field] = value
        with pytest.raises(CalibrationValidationError):
            spectral_cal_bias_frac(**kwargs)

    @pytest.mark.level0
    def test_invalid_band_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="band"):
            spectral_cal_bias_frac(
                delta_lam_um=0.01, t_scene_K=320.0, t_cal_K=300.0, lam_min_um=5.0, lam_max_um=3.5
            )
