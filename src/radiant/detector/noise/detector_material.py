"""Detector-material noise sources (§4, terms 5–8).

Each function computes a single detector-material noise source in
electrons RMS. All are pure functions with no shared state.

Sources:
    dark_shot_noise   — Dark-current shot noise: sqrt(J·t)
    gr_noise          — Generation-recombination noise (Burstein form)
    johnson_noise     — Johnson (thermal) noise from detector R₀A
    (1/f flicker noise moved to radiant.readout.flicker_transfer — CU-381:
     the band is set by the measurement's transfer function, which needs the
     readout timing this stage does not have.)

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q
from radiant.detector.errors import DetectorValidationError


def dark_shot_noise(dark_e: float) -> float:
    """Dark-current shot noise: ``√(J·t)`` [e- RMS].

    Parameters
    ----------
    dark_e:
        Accumulated dark electrons ``J_dark × t_int``. Non-negative.
    """
    if dark_e < 0.0:
        raise DetectorValidationError(f"dark_shot_noise: dark_e = {dark_e} < 0.")
    return math.sqrt(dark_e)


def gr_noise(dark_e: float, gr_factor: float) -> float:
    """Generation-recombination noise (Burstein form).

    ``σ = √(2 · gr_factor · J · t)`` [e- RMS].

    For ``gr_factor = 0`` this returns 0. For ``gr_factor = 1`` the
    variance is 2× the dark shot variance (the classic G-R result for
    HgCdTe photovoltaic detectors).
    """
    if dark_e < 0.0:
        raise DetectorValidationError(f"gr_noise: dark_e = {dark_e} < 0.")
    if gr_factor < 0.0:
        raise DetectorValidationError(f"gr_noise: gr_factor = {gr_factor} < 0.")
    return math.sqrt(2.0 * gr_factor * dark_e)


def johnson_noise(
    r0a_ohm_cm2: float,
    pixel_area_m2: float,
    temp_K: float,
    t_int_s: float,
) -> float:
    """Johnson (thermal) noise from detector R₀A.

    ``σ² = 4·k_B·T · A_pixel / R₀A · t_int / q²`` [e-² RMS²]

    Parameters
    ----------
    r0a_ohm_cm2:
        Detector R₀A product [Ω·cm²]. Zero disables this term.
    pixel_area_m2:
        Pixel photosensitive area [m²].
    temp_K:
        Detector operating temperature [K].
    t_int_s:
        Integration time [s].

    Returns
    -------
    float
        Johnson noise in electrons RMS.
    """
    if r0a_ohm_cm2 <= 0.0:
        return 0.0
    if pixel_area_m2 <= 0.0 or temp_K <= 0.0 or t_int_s <= 0.0:
        return 0.0
    # Convert R₀A from Ω·cm² to Ω·m² (datasheet-unit argument, at this boundary)
    r0a_ohm_m2 = r0a_ohm_cm2 * 1.0e-4  # units-ok: datasheet Ω·cm² arg
    # Current noise PSD: S_I = 4kT/R [A²/Hz] where R = R₀A/A.
    # Charge variance: σ_Q² = S_I × t_int [C²] (white noise × integration).
    # In electrons: σ² = 4kT·A/(R₀A)·t / q².
    #
    # Note: the factor of 4 (not 2) assumes the noise equivalent bandwidth
    # is Δf = 1/t_int rather than the ideal boxcar 1/(2·t_int). This is
    # the convention used by Rogalski (*Infrared Detectors*, 3rd ed.) and
    # accounts for non-ideal integrator roll-off in practical ROIC designs.
    variance_e2 = 4.0 * k_B * temp_K * pixel_area_m2 / r0a_ohm_m2 * t_int_s / (q * q)
    return math.sqrt(variance_e2)
