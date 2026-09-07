"""Level 0 — gain and offset drift terms (plan §3.3, ratified D4: time-linear v1)."""

from __future__ import annotations

import pytest

from radiant.calibration.errors import CalibrationValidationError
from radiant.calibration.gain_drift import gain_drift_residual_e
from radiant.calibration.offset_drift import offset_drift_residual_e


class TestGainDrift:
    def test_hand_value(self) -> None:
        # 1 %/hour = (0.01/3600) 1/s; 24 h = 86400 s; S = 5e4 e-:
        # (0.01/3600) · 86400 · 5e4 = 0.24 · 5e4 = 12 000 e- RMS (hand).
        sigma = gain_drift_residual_e(
            signal_e=5.0e4, gain_drift_frac_per_s=0.01 / 3600.0, time_since_cal_s=86400.0
        )
        assert sigma == pytest.approx(12000.0, rel=1e-12)

    def test_zero_time_is_zero(self) -> None:
        assert (
            gain_drift_residual_e(signal_e=5.0e4, gain_drift_frac_per_s=1e-6, time_since_cal_s=0.0)
            == 0.0
        )

    def test_linear_in_time(self) -> None:
        one = gain_drift_residual_e(
            signal_e=5.0e4, gain_drift_frac_per_s=1e-7, time_since_cal_s=3600.0
        )
        two = gain_drift_residual_e(
            signal_e=5.0e4, gain_drift_frac_per_s=1e-7, time_since_cal_s=7200.0
        )
        assert two == pytest.approx(2.0 * one, rel=1e-12)

    def test_proportional_to_signal(self) -> None:
        base = gain_drift_residual_e(
            signal_e=1.0e4, gain_drift_frac_per_s=1e-7, time_since_cal_s=3600.0
        )
        scaled = gain_drift_residual_e(
            signal_e=3.0e4, gain_drift_frac_per_s=1e-7, time_since_cal_s=3600.0
        )
        assert scaled == pytest.approx(3.0 * base, rel=1e-12)

    def test_negative_rate_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="drift"):
            gain_drift_residual_e(
                signal_e=5.0e4, gain_drift_frac_per_s=-1e-7, time_since_cal_s=3600.0
            )


class TestOffsetDrift:
    def test_hand_value(self) -> None:
        # 3600 e-/hour = 1 e-/s; 7200 s → 7200 e- RMS (hand).
        sigma = offset_drift_residual_e(offset_drift_e_per_s=1.0, time_since_cal_s=7200.0)
        assert sigma == pytest.approx(7200.0, rel=1e-12)

    def test_zero_time_is_zero(self) -> None:
        assert offset_drift_residual_e(offset_drift_e_per_s=5.0, time_since_cal_s=0.0) == 0.0

    def test_signal_independent(self) -> None:
        # No signal argument at all — the term is an offset by construction.
        sigma = offset_drift_residual_e(offset_drift_e_per_s=0.5, time_since_cal_s=1000.0)
        assert sigma == pytest.approx(500.0, rel=1e-12)

    def test_negative_time_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="time"):
            offset_drift_residual_e(offset_drift_e_per_s=1.0, time_since_cal_s=-1.0)
