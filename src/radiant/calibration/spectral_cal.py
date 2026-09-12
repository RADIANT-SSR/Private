"""Spectral-calibration uncertainty → scene-temperature-dependent bias (Gap 122 item 3).

A band-center error δλ (filter drift, spectral-cal uncertainty) rigidly
shifts the band the radiometry is computed over. The calibration absorbs
the resulting scale error at its own source temperature — the gain is
*derived* there — so what survives on a scene is the difference of the
band-shift log-derivatives between scene and cal temperatures:

    g(T)  = [Bq(λ_max, T) − Bq(λ_min, T)] / ∫_band Bq(λ, T) dλ    [1/µm]
    ΔL/L  = |g(T_scene) − g(T_cal)| · δλ                           [fraction]

with Bq the photon-weighted Planck spectral radiance (the chain counts
photons). The bias is exactly zero at T_scene = T_cal and grows with the
scene-vs-cal separation; Wien-side (short-wave) bands are the sensitive
ones. Like its siblings in ``cal_source_bias.py`` this is a BIAS term
(``BiasTerm``, accuracy budget only, ratified D3): never RSS'd into noise.

Model scope: a rigid band-center shift. Band-*width* drift (edges moving
apart) is a distinct, typically smaller mechanism and is not modeled; δλ is
a symmetric 1-σ magnitude, so the term is reported as a magnitude.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.calibration.errors import CalibrationValidationError
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import c, h

_N_GRID = 2001


def _validate_band(lam_min_um: float, lam_max_um: float) -> None:
    if not (0.0 < lam_min_um < lam_max_um):
        raise CalibrationValidationError(
            f"band [{lam_min_um}, {lam_max_um}] µm is invalid.\n"
            "  Why: the band integral needs 0 < lam_min < lam_max.\n"
            "  Action: check spectral_integration.filter_min_um / filter_max_um."
        )


def band_shift_log_derivative(*, t_K: float, lam_min_um: float, lam_max_um: float) -> float:
    """Log-derivative of the photon-weighted band integral under a rigid shift.

    ``d ln ∫ Bq dλ / d(shift) = [Bq(λ_max) − Bq(λ_min)] / ∫ Bq dλ`` [1/µm],
    by the Leibniz rule with both edges moving together.
    """
    if not math.isfinite(t_K) or t_K <= 0.0:
        raise CalibrationValidationError(
            f"t_K = {t_K} K is not a valid absolute temperature.\n"
            "  Why: the Planck band integral is undefined at T <= 0.\n"
            "  Action: supply a temperature > 0 K."
        )
    _validate_band(lam_min_um, lam_max_um)
    lam_um = np.linspace(lam_min_um, lam_max_um, _N_GRID)
    inv_e = (lam_um * 1e-6) / (h * c)  # 1/E_photon
    bq = planck_spectral_radiance(lam_um, t_K) * inv_e
    return float((bq[-1] - bq[0]) / np.trapezoid(bq, lam_um))


def spectral_cal_bias_frac(
    *,
    delta_lam_um: float,
    t_scene_K: float,
    t_cal_K: float,
    lam_min_um: float,
    lam_max_um: float,
) -> float:
    """Fractional radiance bias (1-sigma) from band-center uncertainty.

    ``|g(T_scene) − g(T_cal)| · δλ`` — the calibration-surviving residual of
    a rigid band shift; zero when the scene sits at the cal temperature.
    """
    if not math.isfinite(delta_lam_um) or delta_lam_um < 0.0:
        raise CalibrationValidationError(
            f"delta_lam_um = {delta_lam_um} µm must be finite and non-negative.\n"
            "  Why: the uncertainty is a symmetric 1-sigma magnitude.\n"
            "  Action: supply calibration.band_center_uncertainty_um >= 0."
        )
    if delta_lam_um == 0.0:
        return 0.0
    g_scene = band_shift_log_derivative(
        t_K=t_scene_K, lam_min_um=lam_min_um, lam_max_um=lam_max_um
    )
    g_cal = band_shift_log_derivative(t_K=t_cal_K, lam_min_um=lam_min_um, lam_max_um=lam_max_um)
    return abs(g_scene - g_cal) * delta_lam_um
