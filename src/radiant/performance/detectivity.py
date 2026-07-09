"""Specific detectivity D* ⇄ noise-equivalent power (NEP).

Specific detectivity normalises a detector's NEP to unit area and unit
noise bandwidth so detectors of different sizes can be compared:

    D* = √(A_d · Δf) / NEP        [cm·Hz^½·W⁻¹, "Jones"]

with A_d the detector area [cm²], Δf the noise-equivalent bandwidth [Hz],
and NEP the noise-equivalent power [W] (the incident optical power that
produces SNR = 1). Higher D* is a more sensitive detector.

Scenario 6.1 (Dr. Chen) converts published datasheet D* into the NEP and,
via :mod:`radiant.performance.nep_electrons`, the electron-domain noise the
chain models.
"""

from __future__ import annotations

import math

from radiant.core.exceptions import RadiantError

__all__ = ["DetectivityError", "dstar_from_nep", "nep_from_dstar"]


class DetectivityError(RadiantError):
    """Raised for out-of-range detectivity inputs."""


def _validate(area_cm2: float, bandwidth_hz: float) -> None:
    if area_cm2 <= 0.0:
        raise DetectivityError(f"area_cm2 must be positive, got {area_cm2}.")
    if bandwidth_hz <= 0.0:
        raise DetectivityError(f"bandwidth_hz must be positive, got {bandwidth_hz}.")


def nep_from_dstar(d_star_jones: float, area_cm2: float, bandwidth_hz: float) -> float:
    """Noise-equivalent power [W] from D* [Jones].

    ``NEP = √(A_d · Δf) / D*``.
    """
    _validate(area_cm2, bandwidth_hz)
    if d_star_jones <= 0.0:
        raise DetectivityError(f"d_star_jones must be positive, got {d_star_jones}.")
    return math.sqrt(area_cm2 * bandwidth_hz) / d_star_jones


def dstar_from_nep(nep_w: float, area_cm2: float, bandwidth_hz: float) -> float:
    """Specific detectivity D* [Jones] from NEP [W].

    ``D* = √(A_d · Δf) / NEP``.
    """
    _validate(area_cm2, bandwidth_hz)
    if nep_w <= 0.0:
        raise DetectivityError(f"nep_w must be positive, got {nep_w}.")
    return math.sqrt(area_cm2 * bandwidth_hz) / nep_w
