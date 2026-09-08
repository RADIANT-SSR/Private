"""Cal-source spatial-uniformity residual FPN (Gap 122 item 1).

A real calibration blackbody is uniform to only ±0.01–0.05 K (1σ) across its
aperture; at cal time each pixel views a slightly different source
temperature, and the correction imprints that pattern into the coefficients.
The imprinted per-pixel signal error at cal view *j* is

    δS_j = δT · D_j,   D_j = dS/dT |_(T_cal,j)   [e-/K]

with δT the pixel's local deviation. The **same plate** is viewed at both
cal points, and a cavity gradient is temperature-independent in kelvin to
first order, so the two imprints are fully correlated (the documented
assumption — an independent-δ model would RSS the weights instead and
under-predict inside the cal span).

Propagating through the correction solve:

    one-point (offset-only):  ΔS(S) = δT · D₁                     (constant)
    two-point (gain+offset):  ΔS(S) = δT · [D₁·(S₂−S) + D₂·(S−S₁)] / (S₂−S₁)

so the array RMS values are the same expressions with ``δT → ΔT_unif``.
Unlike the NUC nonlinearity parabola, this residual does **not** vanish at
the cal points — σ(S₁) = ΔT_unif·D₁ exactly — which is why v1's
zero-residual-at-cal-point story was slightly optimistic (the Gap 122
item 1 finding).

Reflective-scene caveat: D_j comes through the same band Planck-ratio
mapping as the cal signals (``cal_points.py``), so on a scene the CU-346
guard flags, this term inherits the same stand-in semantics.
"""

from __future__ import annotations

import math

from radiant.calibration.errors import CalibrationValidationError


def _require_finite_nonneg(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise CalibrationValidationError(
            f"{name} = {value} must be a finite, non-negative number.\n"
            "  Why: signals, derivatives, and dispersions are magnitudes in "
            "this model.\n"
            f"  Action: supply {name} >= 0."
        )


def one_point_uniformity_residual_e(*, delta_t_unif_K: float, ds_dt_cal_e_per_K: float) -> float:
    """Residual FPN from source non-uniformity after one-point NUC [e- RMS].

    Offset-only correction subtracts one erroneous reference, so the imprint
    is constant in scene signal: ``sigma = delta_t_unif_K * ds_dt_cal_e_per_K``.
    """
    _require_finite_nonneg("delta_t_unif_K", delta_t_unif_K)
    _require_finite_nonneg("ds_dt_cal_e_per_K", ds_dt_cal_e_per_K)
    return delta_t_unif_K * ds_dt_cal_e_per_K


def two_point_uniformity_residual_e(
    *,
    signal_e: float,
    s1_e: float,
    s2_e: float,
    delta_t_unif_K: float,
    ds_dt_cal1_e_per_K: float,
    ds_dt_cal2_e_per_K: float,
) -> float:
    """Residual FPN from source non-uniformity after two-point NUC [e- RMS].

    The gain+offset solve interpolates linearly between the two erroneous
    references, and the correlated imprints combine linearly (module
    docstring): ``sigma(S) = dT·|D₁(S₂−S) + D₂(S−S₁)|/(S₂−S₁)``. At either
    cal point this reduces to that view's constant; with D₁ = D₂ it is
    constant everywhere (the interpolation weights sum to one).
    """
    _require_finite_nonneg("signal_e", signal_e)
    _require_finite_nonneg("s1_e", s1_e)
    _require_finite_nonneg("s2_e", s2_e)
    _require_finite_nonneg("delta_t_unif_K", delta_t_unif_K)
    _require_finite_nonneg("ds_dt_cal1_e_per_K", ds_dt_cal1_e_per_K)
    _require_finite_nonneg("ds_dt_cal2_e_per_K", ds_dt_cal2_e_per_K)
    if s1_e == s2_e:
        raise CalibrationValidationError(
            f"two-point cal points coincide (s1_e = s2_e = {s1_e} e-).\n"
            "  Why: the two-point correction is ill-conditioned as the cal "
            "points converge (plan §15), and the interpolation weights are "
            "undefined.\n"
            "  Action: separate the cal temperatures so the cal signals differ."
        )
    # The interpolation identity holds for either cal-point ordering: numerator
    # and denominator flip sign together, so the magnitude uses |span|.
    span = s2_e - s1_e
    weighted = ds_dt_cal1_e_per_K * (s2_e - signal_e) + ds_dt_cal2_e_per_K * (signal_e - s1_e)
    return delta_t_unif_K * abs(weighted) / abs(span)


def three_point_uniformity_residual_e(
    *,
    signal_e: float,
    s1_e: float,
    s2_e: float,
    s3_e: float,
    delta_t_unif_K: float,
    ds_dt_cal1_e_per_K: float,
    ds_dt_cal2_e_per_K: float,
    ds_dt_cal3_e_per_K: float,
) -> float:
    """Residual FPN from source non-uniformity after three-point NUC [e- RMS].

    Piecewise: within each bracketing segment the correction is that pair's
    two-point solve, so the imprint interpolates between that pair's
    ``delta_T x dS/dT`` constants (Gap 122 items 1+2 composed). Ordering is
    validated by the NUC residual on the same signals; here the segments just
    dispatch.
    """
    if not (s1_e < s2_e < s3_e):
        raise CalibrationValidationError(
            f"three-point cal signals must be strictly increasing, got "
            f"s1_e = {s1_e}, s2_e = {s2_e}, s3_e = {s3_e} [e-].\n"
            "  Why: the piecewise imprint interpolates within ordered segments.\n"
            "  Action: order the cal temperatures (low < mid < high)."
        )
    if signal_e <= s2_e:
        return two_point_uniformity_residual_e(
            signal_e=signal_e,
            s1_e=s1_e,
            s2_e=s2_e,
            delta_t_unif_K=delta_t_unif_K,
            ds_dt_cal1_e_per_K=ds_dt_cal1_e_per_K,
            ds_dt_cal2_e_per_K=ds_dt_cal2_e_per_K,
        )
    return two_point_uniformity_residual_e(
        signal_e=signal_e,
        s1_e=s2_e,
        s2_e=s3_e,
        delta_t_unif_K=delta_t_unif_K,
        ds_dt_cal1_e_per_K=ds_dt_cal2_e_per_K,
        ds_dt_cal2_e_per_K=ds_dt_cal3_e_per_K,
    )
