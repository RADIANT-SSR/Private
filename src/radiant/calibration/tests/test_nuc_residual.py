"""Level 0 — post-NUC residual FPN (plan §3.2, ratified D1).

The two-point result under test (derived by exact linear-correction algebra
on the per-pixel quadratic response ``y = g·(S + β·S²/S_ref) + o``)::

    ΔS = β · (S − S₁)(S − S₂) / S_ref        (per pixel, small β)
    σ_NUC(S) = σ_β · |(S − S₁)(S − S₂)| / S_ref   (RMS over the array)

Anchors: hand values, the vanishing-at-cal-points property, and a
Monte-Carlo pixel ensemble with the two-point correction applied
numerically (deterministic seed) — the analytic RMS must match.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration.errors import CalibrationValidationError
from radiant.calibration.nuc_residual import one_point_residual_e, two_point_residual_e


class TestTwoPointResidual:
    def test_zero_at_both_cal_points(self) -> None:
        for s in (1.0e4, 5.0e4):
            assert two_point_residual_e(
                signal_e=s, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
            ) == pytest.approx(0.0, abs=1e-12)

    def test_hand_value_at_midpoint(self) -> None:
        # σ_β=0.01, S1=1e4, S2=5e4, S=3e4, S_ref=1e5:
        # 0.01 · (2e4 · 2e4) / 1e5 = 40 e- RMS (hand calculation).
        sigma = two_point_residual_e(
            signal_e=3.0e4, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
        )
        assert sigma == pytest.approx(40.0, rel=1e-12)

    def test_grows_outside_cal_span(self) -> None:
        inside = two_point_residual_e(
            signal_e=3.0e4, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
        )
        outside = two_point_residual_e(
            signal_e=9.0e4, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
        )
        # (9e4−1e4)(9e4−5e4)/1e5 · 0.01 = 320 e- — quadratic growth outside.
        assert outside == pytest.approx(320.0, rel=1e-12)
        assert outside > inside

    def test_zero_nonlinearity_is_zero_everywhere(self) -> None:
        assert (
            two_point_residual_e(
                signal_e=3.0e4, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.0, full_well_e=1.0e5
            )
            == 0.0
        )

    def test_monte_carlo_ensemble_matches_analytic(self) -> None:
        """Truth anchor 2 (plan §13.2): exact numeric two-point correction of a
        quadratic pixel ensemble reproduces the analytic RMS within 1%."""
        rng = np.random.default_rng(20260906)  # deterministic (Category C traceability)
        n_pix = 200_000
        s1, s2, s_ref = 1.0e4, 5.0e4, 1.0e5
        sigma_beta = 0.005
        beta = rng.normal(0.0, sigma_beta, n_pix)
        gain = rng.normal(1.0, 0.02, n_pix)  # PRNU — removed exactly by 2-pt correction
        offset = rng.normal(0.0, 50.0, n_pix)  # DSNU — removed exactly by 2-pt correction

        def respond(s: float) -> np.ndarray:
            return gain * (s + beta * s**2 / s_ref) + offset

        y1, y2 = respond(s1), respond(s2)
        a = (y2 - y1) / (s2 - s1)
        b = y1 - a * s1
        for s in (2.0e4, 3.0e4, 4.5e4):
            s_hat = (respond(s) - b) / a
            rms_numeric = float(np.std(s_hat - s))
            rms_analytic = two_point_residual_e(
                signal_e=s, s1_e=s1, s2_e=s2, nonlinearity_frac=sigma_beta, full_well_e=s_ref
            )
            assert rms_numeric == pytest.approx(rms_analytic, rel=0.01)

    def test_equal_cal_points_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="cal points"):
            two_point_residual_e(
                signal_e=3.0e4, s1_e=2.0e4, s2_e=2.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
            )

    def test_nonpositive_full_well_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="full_well"):
            two_point_residual_e(
                signal_e=3.0e4, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=0.0
            )

    def test_negative_signal_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="signal_e"):
            two_point_residual_e(
                signal_e=-1.0, s1_e=1.0e4, s2_e=5.0e4, nonlinearity_frac=0.01, full_well_e=1.0e5
            )


class TestOnePointResidual:
    def test_zero_at_cal_point(self) -> None:
        assert one_point_residual_e(signal_e=2.0e4, s1_e=2.0e4, prnu_frac=0.02) == pytest.approx(
            0.0, abs=1e-12
        )

    def test_hand_value(self) -> None:
        # Gain dispersion uncorrected: 0.02 · |3e4 − 1e4| = 400 e- RMS.
        assert one_point_residual_e(signal_e=3.0e4, s1_e=1.0e4, prnu_frac=0.02) == pytest.approx(
            400.0, rel=1e-12
        )

    def test_symmetric_about_cal_point(self) -> None:
        lo = one_point_residual_e(signal_e=1.0e4, s1_e=2.0e4, prnu_frac=0.02)
        hi = one_point_residual_e(signal_e=3.0e4, s1_e=2.0e4, prnu_frac=0.02)
        assert lo == pytest.approx(hi, rel=1e-12)

    def test_monte_carlo_matches(self) -> None:
        """One-point offset correction leaves gain dispersion on the departure."""
        rng = np.random.default_rng(20260907)
        n_pix = 200_000
        s1, prnu = 1.0e4, 0.015
        gain = rng.normal(1.0, prnu, n_pix)
        offset = rng.normal(0.0, 80.0, n_pix)
        y1 = gain * s1 + offset
        for s in (2.0e4, 4.0e4):
            s_hat = (gain * s + offset - y1) + s1  # subtract cal reading, nominal gain 1
            rms_numeric = float(np.std(s_hat - s))
            rms_analytic = one_point_residual_e(signal_e=s, s1_e=s1, prnu_frac=prnu)
            assert rms_numeric == pytest.approx(rms_analytic, rel=0.01)

    def test_negative_prnu_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="prnu"):
            one_point_residual_e(signal_e=3.0e4, s1_e=1.0e4, prnu_frac=-0.01)
