"""Noise budget aggregator — calls all 16 noise sources.

Individual noise sources live in family modules per Rule 19:

    noise_photon.py        — Photon-shot (terms 1–4)
    noise_detector.py      — Detector-material (terms 5–8)
    noise_roic.py          — ROIC (terms 9–11)
    noise_fixed_pattern.py — Fixed-pattern / spatial (terms 12–14)
    noise_other.py         — Other (terms 15–16)

See ``docs/RADIANT_Detector_Complete.md`` §4–§5.
"""

from __future__ import annotations

import math

from radiant.core.noise_budget import (
    ALL_NOISE_TERMS,
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)

# Import individual noise functions from canonical family modules
# (used by compute_noise_budget below)
from radiant.detector.noise_photon import (
    background_shot_noise,
    nearfield_shot_noise,
    signal_shot_noise,
    straylight_shot_noise,
)
from radiant.detector.noise_detector import (
    dark_shot_noise,
    flicker_1f_noise,
    gr_noise,
    johnson_noise,
)
from radiant.detector.noise_roic import (
    ktc_reset_noise,
    quantization_noise,
    read_noise_term,
)
from radiant.detector.noise_fixed_pattern import (
    clutter_noise,
    dsnu_noise,
    prnu_noise,
)
from radiant.detector.noise_other import (
    glow_shot_noise,
    persistence_noise,
)

__all__ = [
    "NoiseBudget",
    "compute_noise_budget",
]


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
