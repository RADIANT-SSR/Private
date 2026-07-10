"""Other noise sources (§4, terms 15–16).

Each function computes a single noise source in electrons RMS.
All are pure functions with no shared state.

Sources:
    persistence_noise — Image lag / persistence noise
    glow_shot_noise   — ROIC / detector glow shot noise: sqrt(R_glow · t)

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

import math

from radiant.detector.errors import DetectorValidationError


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
        raise DetectorValidationError(
            f"persistence_noise: persistence_tau_s = {persistence_tau_s} must be > 0 "
            "when persistence_fraction > 0."
        )
    if frame_interval_s <= 0.0:
        raise DetectorValidationError(
            f"persistence_noise: frame_interval_s = {frame_interval_s} must be > 0."
        )
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
        raise DetectorValidationError(f"glow_shot_noise: glow_e = {glow_e} < 0.")
    return math.sqrt(glow_e)
