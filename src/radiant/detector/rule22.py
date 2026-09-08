"""Rule 22 — updated empirical HgCdTe dark-current-density law (Gap 123).

The 2022 update to Rule 07 for state-of-the-art (non-Auger-suppressed)
p-on-n MBE HgCdTe photodiodes with absorber doping below 1e15 cm⁻³.
Three additive terms cover the three observed regimes in 1/(λc·T):

    J = (1e7·λc^−6.2 + 70·λc^1.08) · exp(−1.04 · (1.24/λc) · q/(k_B·T))   [diffusion]
      + 2e-10 · exp(−0.39 · (1.24/λc) · q/(k_B·T))                        [trap, E_T = 0.39·Eg]
      + 1.5e-21 · λc² · T                                                 [background-flux floor]

with J in A/cm², λc in µm, T in K. Unlike Rule 07 there is no
short-cutoff effective-wavelength correction. Published coverage:
λc ∈ [1.6, 17] µm, T ∈ [20, 330] K, spanning ~20 orders of magnitude in J.

Source: M. Zandian, "Rule-22: An Update to Rule-07", J. Electron. Mater.
52(11), 7095-7102 (2023) (2022 U.S. Workshop on the Physics and Chemistry
of II-VI Materials), as quoted in Materials 17, 4522 (2024) eq. (3);
regime structure confirmed against the paper's abstract (electron trap at
E_T = 0.39·Eg; background flux floor at 3.7 ph/cm²/s).

Like Rule 07 this is an HgCdTe-family law — it does not describe InSb,
InGaAs, Si, or microbolometer dark current.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q
from radiant.detector.errors import DetectorValidationError

# Published fit coefficients (Zandian 2023). Empirical fit constants — they
# live with the law they parameterize (see module docstring); the 1.24 µm·eV
# bandgap conversion is part of the published formula, deliberately not
# replaced by the exact hc/q (same reasoning as rule07.py).
_DIFF_A_A_PER_CM2: float = 1.0e7  # coefficient of λc^−6.2
_DIFF_A_EXP: float = -6.2
_DIFF_B_A_PER_CM2: float = 70.0  # coefficient of λc^1.08
_DIFF_B_EXP: float = 1.08
_DIFF_ACTIVATION: float = 1.04  # fraction of Eg for the diffusion term
_TRAP_J0_A_PER_CM2: float = 2.0e-10
_TRAP_ACTIVATION: float = 0.39  # E_T = 0.39·Eg
_FLUX_FLOOR_A_PER_CM2_UM2_K: float = 1.5e-21  # × λc²·T
_HC_OVER_Q_UM_EV: float = 1.24

# Published coverage limits.
_LAMBDA_MIN_UM: float = 1.6
_LAMBDA_MAX_UM: float = 17.0
_T_MIN_K: float = 20.0
_T_MAX_K: float = 330.0


def _validate(cutoff_um: float, temperature_K: float) -> None:
    if not math.isfinite(cutoff_um) or cutoff_um <= 0.0:
        raise DetectorValidationError(
            f"rule22: cutoff_um = {cutoff_um} is invalid. The cutoff wavelength "
            "must be a positive finite number in µm (Rule 22 is fitted for "
            "HgCdTe cutoffs of 1.6-17 µm)."
        )
    if not math.isfinite(temperature_K) or temperature_K <= 0.0:
        raise DetectorValidationError(
            f"rule22: temperature_K = {temperature_K} is invalid. The operating "
            "temperature must be a positive finite number in K."
        )


def rule22_dark_current_density_a_per_cm2(cutoff_um: float, temperature_K: float) -> float:
    """Rule 22 dark current density [A/cm²] at ``cutoff_um`` [µm], ``temperature_K`` [K]."""
    _validate(cutoff_um, temperature_K)
    # Eg expressed as the published 1.24/λc [eV]; q/k_B converts eV → K.
    eg_over_kt = _HC_OVER_Q_UM_EV / cutoff_um * (q / k_B) / temperature_K
    j_diffusion = (
        _DIFF_A_A_PER_CM2 * cutoff_um**_DIFF_A_EXP + _DIFF_B_A_PER_CM2 * cutoff_um**_DIFF_B_EXP
    ) * math.exp(-_DIFF_ACTIVATION * eg_over_kt)
    j_trap = _TRAP_J0_A_PER_CM2 * math.exp(-_TRAP_ACTIVATION * eg_over_kt)
    j_flux_floor = _FLUX_FLOOR_A_PER_CM2_UM2_K * cutoff_um**2 * temperature_K
    return j_diffusion + j_trap + j_flux_floor


def rule22_fit_range_note(cutoff_um: float, temperature_K: float) -> str:
    """Empty string inside the published coverage, else an advisory note.

    Same contract as :func:`radiant.detector.rule07.rule07_fit_range_note`:
    out-of-range use extrapolates and is flagged via a structured status
    note by the caller, not a per-evaluate warning (CU-081 pattern).
    """
    _validate(cutoff_um, temperature_K)
    notes: list[str] = []
    if not _LAMBDA_MIN_UM <= cutoff_um <= _LAMBDA_MAX_UM:
        notes.append(
            f"cutoff λc = {cutoff_um:.2f} µm is outside the published Rule 22 "
            f"coverage of {_LAMBDA_MIN_UM:.1f}-{_LAMBDA_MAX_UM:.0f} µm"
        )
    if not _T_MIN_K <= temperature_K <= _T_MAX_K:
        notes.append(
            f"T = {temperature_K:.1f} K is outside the published Rule 22 "
            f"coverage of {_T_MIN_K:.0f}-{_T_MAX_K:.0f} K"
        )
    return "; ".join(notes)
