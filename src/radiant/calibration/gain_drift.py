"""Gain-drift residual term (Gap 120 plan §3.3, ratified D4: time-linear v1).

Between calibration events the corrected gain decays; the 1-sigma fractional
responsivity change accumulated over ``time_since_cal`` acts on the signal:

    σ_gain_drift = r_g · t_cal · S        [e- RMS]

Spatial and calibration-correlated (CALIBRATION_TERMS): it does not average
down under TDI/coadds. FPA-temperature-driven drift is deferred (D4).
"""

from __future__ import annotations

import math

from radiant.calibration.errors import CalibrationValidationError


def gain_drift_residual_e(
    *,
    signal_e: float,
    gain_drift_frac_per_s: float,
    time_since_cal_s: float,
) -> float:
    """Gain-drift residual [e- RMS] at scene signal ``signal_e``."""
    if not math.isfinite(signal_e) or signal_e < 0.0:
        raise CalibrationValidationError(
            f"signal_e = {signal_e} must be finite and non-negative.\n"
            "  Why: the gain-drift residual is proportional to signal.\n"
            "  Action: supply the post-integration signal in electrons."
        )
    if not math.isfinite(gain_drift_frac_per_s) or gain_drift_frac_per_s < 0.0:
        raise CalibrationValidationError(
            f"gain drift rate = {gain_drift_frac_per_s} 1/s must be finite and "
            "non-negative.\n"
            "  Why: the rate is a 1-sigma magnitude (time-linear v1, D4).\n"
            "  Action: supply calibration.gain_drift_frac_per_s >= 0."
        )
    if not math.isfinite(time_since_cal_s) or time_since_cal_s < 0.0:
        raise CalibrationValidationError(
            f"time_since_cal_s = {time_since_cal_s} s must be finite and "
            "non-negative.\n"
            "  Why: drift accumulates forward from the cal event.\n"
            "  Action: supply calibration.time_since_cal_s >= 0."
        )
    return gain_drift_frac_per_s * time_since_cal_s * signal_e
