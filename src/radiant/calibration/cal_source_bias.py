"""Cal-source uncertainty → radiance-scale bias (Gap 120 plan §3.4).

The calibration source's own uncertainty does not disperse pixel-to-pixel —
it moves the whole array's radiometric scale. These are BIAS terms
(``BiasTerm``, accuracy budget only, ratified D3): never RSS'd into noise.

Temperature: fractional radiance bias via the photon-weighted band Planck
log-derivative at the cal temperature,

    ΔL/L = [∫ (dBq/dT) dλ / ∫ Bq dλ] · ΔT_src

(photon weighting — the chain counts photons). Emissivity: a pure scale,
ΔL/L = Δε / ε_src. The direct gain-uncertainty input needs no computation
(the parameter is already the fraction) and is consumed by the stage as-is.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.calibration.errors import CalibrationValidationError
from radiant.core.blackbody import planck_spectral_radiance, planck_spectral_radiance_dT
from radiant.core.constants import c, h

_N_GRID = 2001


def source_temp_bias_frac(
    *,
    delta_t_K: float,
    t_cal_K: float,
    lam_min_um: float,
    lam_max_um: float,
) -> float:
    """Fractional radiance bias (1-sigma) from cal-source temperature uncertainty."""
    if not math.isfinite(delta_t_K) or delta_t_K < 0.0:
        raise CalibrationValidationError(
            f"delta_t_K = {delta_t_K} K must be finite and non-negative.\n"
            "  Why: the uncertainty is a 1-sigma magnitude.\n"
            "  Action: supply calibration.source_temp_uncertainty_K >= 0."
        )
    if not math.isfinite(t_cal_K) or t_cal_K <= 0.0:
        raise CalibrationValidationError(
            f"t_cal_K = {t_cal_K} K is not a valid absolute temperature.\n"
            "  Why: the Planck log-derivative is undefined at T <= 0.\n"
            "  Action: supply a cal temperature > 0 K."
        )
    if not (0.0 < lam_min_um < lam_max_um):
        raise CalibrationValidationError(
            f"band [{lam_min_um}, {lam_max_um}] µm is invalid.\n"
            "  Why: the band integral needs 0 < lam_min < lam_max.\n"
            "  Action: check spectral_integration.filter_min_um / filter_max_um."
        )
    if delta_t_K == 0.0:
        return 0.0
    lam_um = np.linspace(lam_min_um, lam_max_um, _N_GRID)
    inv_e = (lam_um * 1e-6) / (h * c)  # 1/E_photon
    bq = planck_spectral_radiance(lam_um, t_cal_K) * inv_e
    dbq = planck_spectral_radiance_dT(lam_um, t_cal_K) * inv_e
    log_deriv = float(np.trapezoid(dbq, lam_um) / np.trapezoid(bq, lam_um))  # 1/K
    return log_deriv * delta_t_K


def source_emissivity_bias_frac(*, delta_eps: float, eps_source: float) -> float:
    """Fractional radiance bias (1-sigma) from cal-source emissivity uncertainty."""
    if not math.isfinite(delta_eps) or delta_eps < 0.0:
        raise CalibrationValidationError(
            f"emissivity uncertainty = {delta_eps} must be finite and non-negative.\n"
            "  Why: the uncertainty is a 1-sigma magnitude.\n"
            "  Action: supply calibration.source_emissivity_uncertainty >= 0."
        )
    if not math.isfinite(eps_source) or eps_source <= 0.0 or eps_source > 1.0:
        raise CalibrationValidationError(
            f"cal-source emissivity = {eps_source} must lie in (0, 1].\n"
            "  Why: the bias is the relative scale error delta_eps/eps_src.\n"
            "  Action: supply calibration.source_emissivity in (0, 1]."
        )
    return delta_eps / eps_source
