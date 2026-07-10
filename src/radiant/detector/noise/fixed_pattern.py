"""Fixed-pattern / spatial noise sources (§4, terms 12–14).

Each function computes a single fixed-pattern noise source in electrons
RMS. All are pure functions with no shared state.

Sources:
    prnu_noise    — Photo-response non-uniformity: (prnu_pct/100) · S
    dsnu_noise    — Dark-signal non-uniformity passthrough
    clutter_noise — Scene clutter noise: clutter_sigma · S_bg

See ``docs/architecture/RADIANT_Detector_Complete.md`` §4.
"""

from __future__ import annotations

from radiant.detector.errors import DetectorValidationError


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
        raise DetectorValidationError(f"prnu_noise: prnu_pct = {prnu_pct} < 0.")
    if signal_e < 0.0:
        raise DetectorValidationError(f"prnu_noise: signal_e = {signal_e} < 0.")
    return (prnu_pct / 100.0) * signal_e


def dsnu_noise(dsnu_e_rms: float) -> float:
    """Dark-signal non-uniformity passthrough [e- RMS]."""
    if dsnu_e_rms < 0.0:
        raise DetectorValidationError(f"dsnu_noise: dsnu_e_rms = {dsnu_e_rms} < 0.")
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
        raise DetectorValidationError(f"clutter_noise: clutter_sigma = {clutter_sigma} < 0.")
    if background_e < 0.0:
        raise DetectorValidationError(f"clutter_noise: background_e = {background_e} < 0.")
    return clutter_sigma * background_e
