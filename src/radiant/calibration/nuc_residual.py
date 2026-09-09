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


def three_point_residual_e(
    *,
    signal_e: float,
    s1_e: float,
    s2_e: float,
    s3_e: float,
    nonlinearity_frac: float,
    full_well_e: float,
) -> float:
    """Residual FPN after three-point NUC [e- RMS] (Gap 122 item 2).

    Piecewise gain+offset correction through three cal signals: within each
    bracketing segment the correction is exactly the two-point solve of that
    pair, so the residual is **that segment's parabola** —
    ``sigma(S) = beta * |(S - S_a)(S - S_b)| / S_ref`` with ``(S_a, S_b)`` the
    bracketing cal points — vanishing at all three points and peaking inside
    each segment at a quarter of that segment's span squared (vs the full
    span squared for two-point: the mid point is what buys the shrink).
    Outside the calibrated span the nearest segment's correction extrapolates,
    exactly as the two-point model extrapolates past its own span. Owner
    scoping (2026-09-07): three points only — beyond that is rarely done.
    """
    for name, s in (("s1_e", s1_e), ("s2_e", s2_e), ("s3_e", s3_e)):
        _require_finite_nonneg(name, s)
    if not (s1_e < s2_e < s3_e):
        raise CalibrationValidationError(
            f"three-point cal signals must be strictly increasing, got "
            f"s1_e = {s1_e}, s2_e = {s2_e}, s3_e = {s3_e} [e-].\n"
            "  Why: the piecewise correction needs ordered, distinct segments; "
            "coincident or unordered points make it ill-conditioned (plan §15).\n"
            "  Action: order the cal temperatures so the band maps them to "
            "strictly increasing signals (t_low < t_mid < t_high on a thermal "
            "band)."
        )
    seg = (s1_e, s2_e) if signal_e <= s2_e else (s2_e, s3_e)
    return two_point_residual_e(
        signal_e=signal_e,
        s1_e=seg[0],
        s2_e=seg[1],
        nonlinearity_frac=nonlinearity_frac,
        full_well_e=full_well_e,
    )


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
