"""Complete noise model — 16 independent noise sources.

Implements all noise terms from ``docs/RADIANT_Detector_Complete.md`` §4.
Each function computes a single noise source in electrons RMS. All are
pure functions with no cross-stage imports.

Noise families:
    Photon-shot (4):  signal_shot, background_shot, nearfield_shot, straylight_shot
    Detector (4):     dark_shot, gr_noise, johnson_noise, flicker_1f
    ROIC (3):         read_noise, ktc_reset, quantization
    Fixed-pattern (3): prnu, dsnu, clutter
    Other (2):        persistence, glow_shot

The ``NoiseBudget`` aggregator collects all 16 terms and computes
temporal/spatial RSS separation per §5 of the detector document.
"""

from __future__ import annotations

import math

from radiant.core.constants import k_B, q
from radiant.core.noise_budget import (
    ALL_NOISE_TERMS,
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)

# Re-export for backward compatibility.
__all__ = [
    "ALL_NOISE_TERMS",
    "SPATIAL_TERMS",
    "TEMPORAL_TERMS",
    "NoiseBudget",
]

# ---------------------------------------------------------------------------
# Photon-shot family (§4, terms 1-4)
# ---------------------------------------------------------------------------


def signal_shot_noise(signal_e: float) -> float:
    """Signal photon-shot noise: ``√S`` [e- RMS]."""
    if signal_e < 0.0:
        raise ValueError(f"signal_shot_noise: signal_e = {signal_e} < 0.")
    return math.sqrt(signal_e)


def background_shot_noise(background_e: float) -> float:
    """Background photon-shot noise: ``√S_bg`` [e- RMS]."""
    if background_e < 0.0:
        raise ValueError(f"background_shot_noise: background_e = {background_e} < 0.")
    return math.sqrt(background_e)


def nearfield_shot_noise(nearfield_e: float) -> float:
    """Nearfield (warm-optics) shot noise: ``√S_nf`` [e- RMS]."""
    if nearfield_e < 0.0:
        raise ValueError(f"nearfield_shot_noise: nearfield_e = {nearfield_e} < 0.")
    return math.sqrt(nearfield_e)


def straylight_shot_noise(stray_e: float) -> float:
    """Stray-light shot noise: ``√S_stray`` [e- RMS]."""
    if stray_e < 0.0:
        raise ValueError(f"straylight_shot_noise: stray_e = {stray_e} < 0.")
    return math.sqrt(stray_e)


# ---------------------------------------------------------------------------
# Detector-material family (§4, terms 5-8)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ROIC family (§4, terms 9-11)
# ---------------------------------------------------------------------------


def read_noise_term(sigma_rms: float) -> float:
    """Read noise passthrough [e- RMS].

    The stored value is the effective per-frame read noise. CDS
    convention is handled by the readout stage.
    """
    if sigma_rms < 0.0:
        raise ValueError(f"read_noise_term: sigma_rms = {sigma_rms} < 0.")
    return sigma_rms


def ktc_reset_noise(node_capacitance_F: float, temp_K: float, cds_enabled: bool) -> float:
    """kTC reset noise: ``√(kT·C) / q`` [e- RMS].

    When CDS is enabled, kTC noise is fully suppressed (returns 0).

    Parameters
    ----------
    node_capacitance_F:
        Sense-node capacitance [F]. Zero disables.
    temp_K:
        Detector temperature [K].
    cds_enabled:
        If True, CDS suppresses kTC entirely.
    """
    if cds_enabled:
        return 0.0
    if node_capacitance_F <= 0.0:
        return 0.0
    if temp_K <= 0.0:
        return 0.0
    # σ_charge = √(kTC) in coulombs → divide by q for electrons
    return math.sqrt(k_B * temp_K * node_capacitance_F) / q


def quantization_noise(gain_e_per_dn: float) -> float:
    """ADC quantization noise: ``LSB / √12`` [e- RMS]."""
    if gain_e_per_dn <= 0.0:
        raise ValueError(f"quantization_noise: gain_e_per_dn = {gain_e_per_dn} must be > 0.")
    return gain_e_per_dn / math.sqrt(12.0)


# ---------------------------------------------------------------------------
# Fixed-pattern / spatial family (§4, terms 12-14)
# ---------------------------------------------------------------------------


def prnu_noise(signal_e: float, prnu_pct: float) -> float:
    """Photo-response non-uniformity: ``prnu_pct/100 · S`` [e- RMS].

    Parameters
    ----------
    signal_e:
        Signal electrons per pixel.
    prnu_pct:
        PRNU as a percentage (e.g. 1.0 = 1%). Zero disables.
    """
    if prnu_pct < 0.0:
        raise ValueError(f"prnu_noise: prnu_pct = {prnu_pct} < 0.")
    if signal_e < 0.0:
        raise ValueError(f"prnu_noise: signal_e = {signal_e} < 0.")
    return (prnu_pct / 100.0) * signal_e


def dsnu_noise(dsnu_e_rms: float) -> float:
    """Dark-signal non-uniformity passthrough [e- RMS]."""
    if dsnu_e_rms < 0.0:
        raise ValueError(f"dsnu_noise: dsnu_e_rms = {dsnu_e_rms} < 0.")
    return dsnu_e_rms


def clutter_noise(background_e: float, clutter_sigma: float) -> float:
    """Scene clutter noise: ``clutter_sigma · S_bg`` [e- RMS].

    Parameters
    ----------
    background_e:
        Background electrons per pixel.
    clutter_sigma:
        Fractional clutter coefficient. Zero disables.
    """
    if clutter_sigma < 0.0:
        raise ValueError(f"clutter_noise: clutter_sigma = {clutter_sigma} < 0.")
    if background_e < 0.0:
        raise ValueError(f"clutter_noise: background_e = {background_e} < 0.")
    return clutter_sigma * background_e


# ---------------------------------------------------------------------------
# Other (§4, terms 15-16)
# ---------------------------------------------------------------------------


def persistence_noise(
    prior_signal_e: float,
    persistence_fraction: float,
    persistence_tau_s: float,
    frame_interval_s: float,
) -> float:
    """Persistence (image lag) noise.

    ``σ = f_persist · S_prev · √(1 − exp(−Δt / τ_p))`` [e- RMS].

    Parameters
    ----------
    prior_signal_e:
        Signal electrons from the prior frame.
    persistence_fraction:
        Fraction of prior signal that persists (0–1). Zero disables.
    persistence_tau_s:
        Persistence time constant [s]. Must be > 0 if fraction > 0.
    frame_interval_s:
        Time between frames [s]. Must be > 0.
    """
    if persistence_fraction <= 0.0 or prior_signal_e <= 0.0:
        return 0.0
    if persistence_tau_s <= 0.0:
        raise ValueError(
            f"persistence_noise: persistence_tau_s = {persistence_tau_s} must be > 0 "
            "when persistence_fraction > 0."
        )
    if frame_interval_s <= 0.0:
        raise ValueError(f"persistence_noise: frame_interval_s = {frame_interval_s} must be > 0.")
    decay = 1.0 - math.exp(-frame_interval_s / persistence_tau_s)
    return persistence_fraction * prior_signal_e * math.sqrt(decay)


def glow_shot_noise(glow_e: float) -> float:
    """ROIC / detector glow shot noise: ``√(R_glow · t)`` [e- RMS].

    Parameters
    ----------
    glow_e:
        Accumulated glow electrons ``R_glow × t_int``. Non-negative.
    """
    if glow_e < 0.0:
        raise ValueError(f"glow_shot_noise: glow_e = {glow_e} < 0.")
    return math.sqrt(glow_e)


    # NoiseBudget is now imported from radiant.core.noise_budget.


def compute_noise_budget(
    *,
    signal_e: float = 0.0,
    background_e: float = 0.0,
    nearfield_e: float = 0.0,
    stray_e: float = 0.0,
    dark_e: float = 0.0,
    glow_e: float = 0.0,
    gr_factor: float = 0.0,
    r0a_ohm_cm2: float = 0.0,
    pixel_area_m2: float = 0.0,
    detector_temp_K: float = 77.0,
    t_int_s: float = 0.01,
    flicker_K: float = 0.0,
    flicker_f_low_hz: float = 0.01,
    flicker_f_high_hz: float = 1.0e6,
    read_noise_e_rms: float = 0.0,
    node_capacitance_F: float = 0.0,
    cds_enabled: bool = True,
    gain_e_per_dn: float = 1.0,
    prnu_pct: float = 0.0,
    dsnu_e_rms: float = 0.0,
    clutter_sigma: float = 0.0,
    prior_signal_e: float = 0.0,
    persistence_fraction: float = 0.0,
    persistence_tau_s: float = 1.0,
    frame_interval_s: float = 0.0,
) -> NoiseBudget:
    """Compute all 16 noise terms and build a NoiseBudget.

    All parameters default to zero/disabled so the caller only needs
    to supply the terms relevant to their detector configuration.
    """
    terms: dict[str, float] = {
        "signal_shot": signal_shot_noise(signal_e),
        "background_shot": background_shot_noise(background_e),
        "nearfield_shot": nearfield_shot_noise(nearfield_e),
        "straylight_shot": straylight_shot_noise(stray_e),
        "dark_shot": dark_shot_noise(dark_e),
        "gr_noise": gr_noise(dark_e, gr_factor),
        "johnson_noise": johnson_noise(r0a_ohm_cm2, pixel_area_m2, detector_temp_K, t_int_s),
        "flicker_1f": flicker_1f_noise(flicker_K, flicker_f_low_hz, flicker_f_high_hz),
        "read_noise": read_noise_term(read_noise_e_rms),
        "ktc_reset": ktc_reset_noise(node_capacitance_F, detector_temp_K, cds_enabled),
        "quantization": quantization_noise(gain_e_per_dn),
        "prnu": prnu_noise(signal_e, prnu_pct),
        "dsnu": dsnu_noise(dsnu_e_rms),
        "clutter": clutter_noise(background_e, clutter_sigma),
        "persistence_noise": persistence_noise(
            prior_signal_e,
            persistence_fraction,
            persistence_tau_s,
            frame_interval_s,
        ),
        "glow_shot": glow_shot_noise(glow_e),
    }

    temporal_var = sum(v**2 for k, v in terms.items() if k in TEMPORAL_TERMS)
    spatial_var = sum(v**2 for k, v in terms.items() if k in SPATIAL_TERMS)

    return NoiseBudget(
        terms=terms,
        sigma_temporal_e=math.sqrt(temporal_var),
        sigma_spatial_e=math.sqrt(spatial_var),
    )
