"""Cal-temperature → cal-signal mapping (Gap 120 plan §3.1).

Cal points are declared as blackbody source temperatures (over-specification
guard: fluxes are never independent inputs). The stage runs post-integration
(Rule 8 — only scalars are available), so the mapping to signal electrons
uses the band photon-radiance ratio anchored at the scene:

    S(T_cal) = S_scene · Bq(T_cal) / Bq(T_scene)

with ``Bq(T) = ∫ B(λ,T)/E_photon(λ) dλ`` over the sensing band (photon
weighting — signal electrons count photons, not energy).

Assumption (plan §14): the spectral response shape (QE·τ) varies slowly
enough across the band that the flat-weighted photon-radiance ratio
approximates the response-weighted signal ratio. Good for thermal bands with
flat-ish QE; degrades for strongly sloped response curves — documented
fragility, not silently wrong (the ratio, not the absolute level, is what
enters, so the first-order response slope cancels between numerator and
denominator anchored at nearby temperatures).
"""

from __future__ import annotations

import math

import numpy as np

from radiant.calibration.errors import CalibrationValidationError
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import c, h

_N_GRID = 2001


def _band_photon_radiance(t_K: float, lam_min_um: float, lam_max_um: float) -> float:
    """Band-integrated photon radiance [photon/s/m²/sr]."""
    lam_um = np.linspace(lam_min_um, lam_max_um, _N_GRID)
    b = planck_spectral_radiance(lam_um, t_K)  # W/m²/sr/µm
    e_photon = h * c / (lam_um * 1e-6)  # J
    return float(np.trapezoid(b / e_photon, lam_um))


def band_thermal_photon_fraction(t_K: float, lam_min_um: float, lam_max_um: float) -> float:
    """Fraction of a ``t_K`` blackbody's photon exitance inside the sensing band.

    The CU-346 guard's quantity: when this is vanishingly small, a physical
    blackbody at the declared scene temperature delivers essentially nothing
    in-band, so a signal the chain nonetheless collected there is non-thermal
    (solar-reflected) and the Planck cal-point anchor is a stand-in. At 300 K
    the fraction is ~1e-20 for a 0.5–0.85 µm VNIR band and ~1e-2 for a 3–5 µm
    MWIR band. The total integrates 0.05–1000 µm on a log grid — wide enough
    that the tail truncation is far below any threshold this feeds.
    """
    lam_total_um = np.geomspace(0.05, 1000.0, 4001)
    b = planck_spectral_radiance(lam_total_um, t_K)
    e_photon = h * c / (lam_total_um * 1e-6)
    total = float(np.trapezoid(b / e_photon, lam_total_um))
    if total <= 0.0:
        return 0.0
    return _band_photon_radiance(t_K, lam_min_um, lam_max_um) / total


def cal_point_signal_e(
    *,
    t_cal_K: float,
    scene_temp_K: float,
    scene_signal_e: float,
    lam_min_um: float,
    lam_max_um: float,
) -> float:
    """Signal electrons the chain would collect viewing the cal source at ``t_cal_K``."""
    for name, t in (("t_cal_K", t_cal_K), ("scene_temp_K", scene_temp_K)):
        if not math.isfinite(t) or t <= 0.0:
            raise CalibrationValidationError(
                f"{name} = {t} K is not a valid absolute temperature.\n"
                "  Why: the Planck band ratio is undefined at T <= 0.\n"
                f"  Action: supply {name} > 0 K."
            )
    if not (0.0 < lam_min_um < lam_max_um):
        raise CalibrationValidationError(
            f"band [{lam_min_um}, {lam_max_um}] µm is invalid.\n"
            "  Why: the band integral needs 0 < lam_min < lam_max.\n"
            "  Action: check spectral_integration.filter_min_um / filter_max_um."
        )
    if not math.isfinite(scene_signal_e) or scene_signal_e <= 0.0:
        raise CalibrationValidationError(
            f"scene_signal_e = {scene_signal_e} must be positive.\n"
            "  Why: the mapping anchors the cal signal to the scene signal by "
            "radiance ratio; a zero anchor carries no scale.\n"
            "  Action: evaluate a scene with non-zero thermal signal, or use "
            "calibration.scheme = 'none'."
        )
    ratio = _band_photon_radiance(t_cal_K, lam_min_um, lam_max_um) / _band_photon_radiance(
        scene_temp_K, lam_min_um, lam_max_um
    )
    return scene_signal_e * ratio
