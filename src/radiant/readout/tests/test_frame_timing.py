"""Level 0 tests for the frame-rate / duty-cycle derivation (Conventions §4)."""

from __future__ import annotations

import logging

import pytest

from radiant.readout.errors import ReadoutValidationError
from radiant.readout.frame_timing import FrameTiming, compute_frame_timing


class TestExplicitFramePeriod:
    @pytest.mark.level0
    def test_frame_rate_and_duty_anchor(self) -> None:
        """t_int=5 ms, frame_period=20 ms → 50 Hz, duty 0.25 (Conventions §4)."""
        ft = compute_frame_timing(0.005, 0.020)
        assert ft.frame_period_s == pytest.approx(0.020, rel=1e-12)
        assert ft.frame_rate_hz == pytest.approx(50.0, rel=1e-12)
        assert ft.duty_cycle == pytest.approx(0.25, rel=1e-12)
        assert ft.frame_period_defaulted is False

    @pytest.mark.level0
    def test_duty_one_when_period_equals_t_int(self) -> None:
        ft = compute_frame_timing(0.01, 0.01)
        assert ft.duty_cycle == pytest.approx(1.0, rel=1e-12)
        assert ft.frame_rate_hz == pytest.approx(100.0, rel=1e-12)
        assert ft.frame_period_defaulted is False


class TestUnsetFramePeriod:
    @pytest.mark.level0
    def test_defaults_to_one_over_t_int(self) -> None:
        """Unset (≤0) frame period → 1/t_int, duty 1.0, defaulted flag True (§4)."""
        ft = compute_frame_timing(0.004, 0.0, warn=False)
        assert ft == FrameTiming(
            frame_period_s=0.004,
            frame_rate_hz=250.0,
            duty_cycle=1.0,
            frame_period_defaulted=True,
        )

    @pytest.mark.level0
    def test_default_logs_warning_when_warn_true(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="radiant.readout.frame_timing"):
            compute_frame_timing(0.004, 0.0, warn=True)
        assert any("frame_period_s is unset" in r.message for r in caplog.records)

    @pytest.mark.level0
    def test_default_silent_when_warn_false(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="radiant.readout.frame_timing"):
            compute_frame_timing(0.004, 0.0, warn=False)
        assert caplog.records == []


class TestValidation:
    @pytest.mark.level0
    def test_duty_over_one_raises(self) -> None:
        """Integration longer than the frame period is impossible (duty>1)."""
        with pytest.raises(ReadoutValidationError, match="duty cycle"):
            compute_frame_timing(0.02, 0.01)

    @pytest.mark.level0
    def test_nonpositive_t_int_raises(self) -> None:
        with pytest.raises(ReadoutValidationError, match="integration_time_s"):
            compute_frame_timing(0.0, 0.01)
