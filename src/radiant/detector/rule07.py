"""Rule 07 — empirical HgCdTe dark-current-density law (Gap 123).

Predicts the dark current density J_dark [A/cm²] of state-of-the-art
(2007-era) Teledyne p-on-n double-layer planar heterojunction MBE HgCdTe
photodiodes from cutoff wavelength and operating temperature alone:

    J_dark = J0 · exp(C · 1.24 · q / (k_B · λe · T))

with the effective cutoff λe = λc for λc ≥ λ_threshold and

    λe = λc / (1 − (λ_scale/λc − λ_scale/λ_threshold)^Pwr)

below it. Published fit range: λe·T ∈ [400, 1700] µm·K and T > 77 K.

Source: W.E. Tennant, D. Lee, M. Zandian, E. Piquette, M. Carmody,
"MBE HgCdTe Technology: A Very General Solution to IR Detection,
Described by 'Rule 07', a Very Convenient Heuristic",
J. Electron. Mater. 37(9), 1406-1410 (2008). Coefficients cross-checked
against Materials 17, 4522 (2024) eqs. (1)-(2) and the MCT row of the
"GeSn Rule-23" comparison table (Photonics 2023).

The law is specific to p-on-n HgCdTe limited by Auger-1 diffusion at
~1e15 cm⁻³ absorber doping. It says nothing about InSb, InGaAs, Si, or
microbolometers, and modern low-doped devices beat it — see
:mod:`radiant.detector.rule22` for the 2022 update.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q
from radiant.detector.errors import DetectorValidationError

# Published fit coefficients (Tennant 2008, Table at eq. (2)). These are
# empirical fit constants, not physical constants — they live with the law
# they parameterize, cited above, and must not be "corrected": the 1.24
# factor is the paper's rounded hc/q in µm·eV and the C value was fitted
# against exactly that rounding, so substituting the exact 1.2398 µm·eV
# would misreproduce the published curve by ~4%.
_J0_A_PER_CM2: float = 8367.0
_C: float = -1.162972237
_LAMBDA_SCALE_UM: float = 0.200847413
_LAMBDA_THRESHOLD_UM: float = 4.635136423
_PWR: float = 0.544071282
_HC_OVER_Q_UM_EV: float = 1.24

# Published validity limits.
_LAMBDA_T_MIN_UM_K: float = 400.0
_LAMBDA_T_MAX_UM_K: float = 1700.0
_T_MIN_K: float = 77.0


def _validate(cutoff_um: float, temperature_K: float) -> None:
    if not math.isfinite(cutoff_um) or cutoff_um <= 0.0:
        raise DetectorValidationError(
            f"rule07: cutoff_um = {cutoff_um} is invalid. The cutoff wavelength "
            "must be a positive finite number in µm (Rule 07 is fitted for "
            "HgCdTe cutoffs of roughly 2-19 µm)."
        )
    if not math.isfinite(temperature_K) or temperature_K <= 0.0:
        raise DetectorValidationError(
            f"rule07: temperature_K = {temperature_K} is invalid. The operating "
            "temperature must be a positive finite number in K."
        )


def rule07_effective_cutoff_um(cutoff_um: float) -> float:
    """Effective cutoff wavelength λe [µm] of the Rule 07 law.

    Identity above λ_threshold = 4.635136423 µm; below it the published
    correction lengthens the effective cutoff. Raises when the correction
    denominator is non-positive (λc ≲ 0.1926 µm — outside the law's domain).
    """
    _validate(cutoff_um, 300.0)
    if cutoff_um >= _LAMBDA_THRESHOLD_UM:
        return cutoff_um
    denom = 1.0 - (_LAMBDA_SCALE_UM / cutoff_um - _LAMBDA_SCALE_UM / _LAMBDA_THRESHOLD_UM) ** _PWR
    if denom <= 0.0:
        raise DetectorValidationError(
            f"rule07: cutoff_um = {cutoff_um} µm is below the domain of the "
            "short-wavelength correction (effective cutoff undefined for "
            "λc ≲ 0.193 µm). Rule 07 describes IR HgCdTe photodiodes; use a "
            "measured dark rate for detectors this far outside its domain."
        )
    return cutoff_um / denom


def rule07_dark_current_density_a_per_cm2(cutoff_um: float, temperature_K: float) -> float:
    """Rule 07 dark current density [A/cm²] at ``cutoff_um`` [µm], ``temperature_K`` [K]."""
    _validate(cutoff_um, temperature_K)
    lam_e_um = rule07_effective_cutoff_um(cutoff_um)
    exponent = _C * _HC_OVER_Q_UM_EV * (q / k_B) / (lam_e_um * temperature_K)
    return _J0_A_PER_CM2 * math.exp(exponent)


def rule07_fit_range_note(cutoff_um: float, temperature_K: float) -> str:
    """Empty string inside the published fit range, else an advisory note.

    The law extrapolates smoothly, so out-of-range use is permitted but
    flagged: the caller (DetectorStage) surfaces this as a structured
    status note, not a per-evaluate warning (CU-081 pattern).
    """
    _validate(cutoff_um, temperature_K)
    lam_e_t = rule07_effective_cutoff_um(cutoff_um) * temperature_K
    notes: list[str] = []
    if lam_e_t < _LAMBDA_T_MIN_UM_K:
        notes.append(
            f"λe·T = {lam_e_t:.0f} µm·K is below the published Rule 07 fit floor "
            f"of {_LAMBDA_T_MIN_UM_K:.0f} µm·K — real devices bottom out on trap "
            "and background-flux floors the single-exponential law ignores "
            "(Rule 07 will be optimistic here; consider dark_model = 'rule22')"
        )
    if lam_e_t > _LAMBDA_T_MAX_UM_K:
        notes.append(
            f"λe·T = {lam_e_t:.0f} µm·K is above the published Rule 07 fit "
            f"ceiling of {_LAMBDA_T_MAX_UM_K:.0f} µm·K"
        )
    if temperature_K < _T_MIN_K:
        # Boundary-inclusive: 77.0 K (LN₂) is the canonical fit-floor operating
        # point and is treated as inside the published range.
        notes.append(
            f"T = {temperature_K:.1f} K is below the published Rule 07 "
            f"validity floor of {_T_MIN_K:.0f} K"
        )
    return "; ".join(notes)
