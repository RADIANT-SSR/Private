"""On-chip and off-chip binning — signal and noise scaling.

Per ``docs/RADIANT_Detector_Complete.md`` §8:

On-chip (analog, before readout):
    Signal: × M_x × M_y
    Shot-like noise: × √(M_x × M_y)  (independent pixels sum)
    Read noise: × 1  (single readout of combined charge packet)

Off-chip (digital, after readout):
    Signal: × P_x × P_y
    Shot-like noise: × √(P_x × P_y)  (independent pixels sum)
    Read noise: × √(P_x × P_y)  (each pixel read independently)
    FPN: × P_x × P_y  (correlated systematic → scales with signal)
"""

from __future__ import annotations

import math


def _validate_bin(mx: int, my: int, label: str) -> None:
    if mx < 1 or my < 1:
        raise ValueError(f"{label}: binning factors must be >= 1, got ({mx}, {my}).")


# ---------------------------------------------------------------------------
# On-chip (analog) binning
# ---------------------------------------------------------------------------


def onchip_scale_signal(signal_e: float, mx: int, my: int) -> float:
    """Scale signal by on-chip binning factor: ``S × M_x × M_y``."""
    _validate_bin(mx, my, "onchip_scale_signal")
    return signal_e * mx * my


def onchip_scale_shot_noise(noise_e: float, mx: int, my: int) -> float:
    """Scale shot-like noise by ``√(M_x × M_y)`` (on-chip)."""
    _validate_bin(mx, my, "onchip_scale_shot_noise")
    return noise_e * math.sqrt(mx * my)


def onchip_scale_read_noise(noise_e: float) -> float:
    """Read noise unchanged by on-chip binning (single readout)."""
    return noise_e


def onchip_scale_fpn(noise_e: float, mx: int, my: int) -> float:
    """FPN scales linearly with on-chip binning: ``σ × M_x × M_y``."""
    _validate_bin(mx, my, "onchip_scale_fpn")
    return noise_e * mx * my


# ---------------------------------------------------------------------------
# Off-chip (digital) binning
# ---------------------------------------------------------------------------


def offchip_scale_signal(signal_e: float, px: int, py: int) -> float:
    """Scale signal by off-chip binning factor: ``S × P_x × P_y``."""
    _validate_bin(px, py, "offchip_scale_signal")
    return signal_e * px * py


def offchip_scale_shot_noise(noise_e: float, px: int, py: int) -> float:
    """Scale shot-like noise by ``√(P_x × P_y)`` (off-chip)."""
    _validate_bin(px, py, "offchip_scale_shot_noise")
    return noise_e * math.sqrt(px * py)


def offchip_scale_read_noise(noise_e: float, px: int, py: int) -> float:
    """Read noise scales by ``√(P_x × P_y)`` (each pixel read independently)."""
    _validate_bin(px, py, "offchip_scale_read_noise")
    return noise_e * math.sqrt(px * py)


def offchip_scale_fpn(noise_e: float, px: int, py: int) -> float:
    """FPN scales linearly with off-chip binning: ``σ × P_x × P_y``."""
    _validate_bin(px, py, "offchip_scale_fpn")
    return noise_e * px * py
