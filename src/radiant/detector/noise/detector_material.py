"""Detector-material noise sources (§4, terms 5–8).

Each function computes a single detector-material noise source in
electrons RMS. All are pure functions with no shared state.

Sources:
    dark_shot_noise   — Dark-current shot noise: sqrt(J·t)
    gr_noise          — Generation-recombination noise (Burstein form)
    johnson_noise     — Johnson (thermal) noise from detector R₀A
    flicker_1f_noise  — 1/f flicker noise

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q


def dark_shot_noise(dark_e: float) -> float:
    """Dark-current shot noise: ``√(J·t)`` [e- RMS].

    Parameters
    ----------
    dark_e:
        Accumulated dark electrons ``J_dark × t_int``. Non-negative.
    """
    if dark_e < 0.0:
        raise ValueError(f"dark_shot_noise: dark_e = {dark_e} < 0.")
    return math.sqrt(dark_e)


def gr_noise(dark_e: float, gr_factor: float) -> float:
    """Generation-recombination noise (Burstein form).

    ``σ = √(2 · gr_factor · J · t)`` [e- RMS].

    For ``gr_factor = 0`` this returns 0. For ``gr_factor = 1`` the
    variance is 2× the dark shot variance (the classic G-R result for
    HgCdTe photovoltaic detectors).
    """
    if dark_e < 0.0:
        raise ValueError(f"gr_noise: dark_e = {dark_e} < 0.")
    if gr_factor < 0.0:
        raise ValueError(f"gr_noise: gr_factor = {gr_factor} < 0.")
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
    # Convert R₀A from Ω·cm² to Ω·m²
    r0a_ohm_m2 = r0a_ohm_cm2 * 1.0e-4
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


def flicker_1f_noise(flicker_K: float, f_low_hz: float, f_high_hz: float) -> float:
    """1/f flicker noise.

    ``σ = √(K · ln(f_high / f_low))`` [e- RMS].

    Parameters
    ----------
    flicker_K:
        Flicker noise coefficient [e-²]. Zero disables.
    f_low_hz:
        Lower frequency bound [Hz]. Must be > 0.
    f_high_hz:
        Upper frequency bound [Hz]. Must be > f_low_hz.
    """
    if flicker_K <= 0.0:
        return 0.0
    if f_low_hz <= 0.0:
        raise ValueError(f"flicker_1f_noise: f_low_hz = {f_low_hz} must be > 0.")
    if f_high_hz <= f_low_hz:
        raise ValueError(
            f"flicker_1f_noise: f_high_hz = {f_high_hz} must be > f_low_hz = {f_low_hz}."
        )
    return math.sqrt(flicker_K * math.log(f_high_hz / f_low_hz))
