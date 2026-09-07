"""Post-NUC residual fixed-pattern noise (Gap 120 plan §3.2, ratified D1).

Two-point NUC corrects each pixel's gain and offset exactly at the two cal
signals ``S₁, S₂``; what survives is the per-pixel *nonlinearity* dispersion.
For the v1 quadratic response model ``y = g·(S + β·S²/S_ref) + o`` with
``β ~ N(0, σ_β)``, exact linear-correction algebra gives the per-pixel error

    ΔS = β · (S − S₁)(S − S₂) / S_ref            (small-β limit)

so the array RMS is

    σ_NUC(S) = σ_β · |(S − S₁)(S − S₂)| / S_ref     [e- RMS]

— a parabola vanishing at both cal points, peaking between them, growing
quadratically outside (the classical two-point correctability shape;
Schulz & Caldwell 1995). Gain (PRNU) and offset (DSNU) dispersions are
removed exactly by the correction and re-enter only through drift
(``gain_drift.py`` / ``offset_drift.py``).

One-point NUC corrects offset only: gain dispersion survives on the
*departure* from the cal point,

    σ_1pt(S) = prnu_frac · |S − S₁|                  [e- RMS].

Validity: the quadratic model holds over roughly the cal span and its
extension; far outside (deep saturation approach) the response is not
polynomial and the number is a lower bound (plan §14/§15).
"""

from __future__ import annotations

import math

from radiant.calibration.errors import CalibrationValidationError


def _require_finite_nonneg(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise CalibrationValidationError(
            f"{name} = {value} must be a finite, non-negative number.\n"
            "  Why: signals and dispersions are magnitudes in this model.\n"
            f"  Action: supply {name} >= 0."
        )


def two_point_residual_e(
    *,
    signal_e: float,
    s1_e: float,
    s2_e: float,
    nonlinearity_frac: float,
    full_well_e: float,
) -> float:
    """Residual FPN after two-point NUC [e- RMS] at scene signal ``signal_e``."""
    _require_finite_nonneg("signal_e", signal_e)
    _require_finite_nonneg("s1_e", s1_e)
    _require_finite_nonneg("s2_e", s2_e)
    _require_finite_nonneg("nonlinearity_frac", nonlinearity_frac)
    if s1_e == s2_e:
        raise CalibrationValidationError(
            f"two-point cal points coincide (s1_e = s2_e = {s1_e} e-).\n"
            "  Why: the two-point correction is ill-conditioned as the cal "
            "points converge (plan §15).\n"
            "  Action: separate the cal temperatures so the cal signals differ."
        )
    if full_well_e <= 0.0 or not math.isfinite(full_well_e):
        raise CalibrationValidationError(
            f"full_well_e = {full_well_e} must be positive and finite.\n"
            "  Why: the quadratic coefficient is referenced to full scale "
            "(beta·S²/S_ref).\n"
            "  Action: supply the detector full-well capacity in electrons."
        )
    return nonlinearity_frac * abs((signal_e - s1_e) * (signal_e - s2_e)) / full_well_e


def one_point_residual_e(*, signal_e: float, s1_e: float, prnu_frac: float) -> float:
    """Residual FPN after one-point (offset-only) NUC [e- RMS]."""
    _require_finite_nonneg("signal_e", signal_e)
    _require_finite_nonneg("s1_e", s1_e)
    if not math.isfinite(prnu_frac) or prnu_frac < 0.0:
        raise CalibrationValidationError(
            f"prnu_frac = {prnu_frac} must be a finite, non-negative fraction.\n"
            "  Why: the pre-correction gain dispersion is a 1-sigma magnitude.\n"
            "  Action: supply detector.prnu_pct >= 0."
        )
    return prnu_frac * abs(signal_e - s1_e)
