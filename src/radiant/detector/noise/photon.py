"""Photon-shot noise sources (§4, terms 1–4).

Each function computes a single photon-shot noise source in electrons RMS.
All are pure functions with no shared state or cross-stage imports.

Sources:
    signal_shot_noise     — Signal photon-shot noise: sqrt(S)
    background_shot_noise — Background photon-shot noise: sqrt(S_bg)
    nearfield_shot_noise  — Nearfield (warm-optics) shot noise: sqrt(S_nf)
    straylight_shot_noise — Stray-light shot noise: sqrt(S_stray)

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

import math


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
