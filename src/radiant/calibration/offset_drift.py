"""Offset-drift residual term (Gap 120 plan §3.3, ratified D4: time-linear v1).

The corrected offset re-grows after the cal event; signal-independent:

    σ_offset_drift = r_o · t_cal          [e- RMS]

Spatial and calibration-correlated (CALIBRATION_TERMS): does not average
down under TDI/coadds.
"""

from __future__ import annotations

import math

from radiant.calibration.errors import CalibrationValidationError


def offset_drift_residual_e(*, offset_drift_e_per_s: float, time_since_cal_s: float) -> float:
    """Offset-drift residual [e- RMS]."""
    if not math.isfinite(offset_drift_e_per_s) or offset_drift_e_per_s < 0.0:
        raise CalibrationValidationError(
            f"offset drift rate = {offset_drift_e_per_s} e-/s must be finite "
            "and non-negative.\n"
            "  Why: the rate is a 1-sigma magnitude (time-linear v1, D4).\n"
            "  Action: supply calibration.offset_drift_e_per_s >= 0."
        )
    if not math.isfinite(time_since_cal_s) or time_since_cal_s < 0.0:
        raise CalibrationValidationError(
            f"time_since_cal_s = {time_since_cal_s} s must be finite and "
            "non-negative.\n"
            "  Why: drift accumulates forward from the cal event.\n"
            "  Action: supply calibration.time_since_cal_s >= 0."
        )
    return offset_drift_e_per_s * time_since_cal_s
