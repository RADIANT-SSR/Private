"""On-chip (analog) binning — signal and noise scaling.

Per ``docs/RADIANT_Detector_Complete.md`` §8:

On-chip binning accumulates charge from M_x × M_y pixels into a
single super-pixel before readout (single readout of the combined
charge packet).

    Signal:     × M_x × M_y
    Shot noise: × √(M_x × M_y)
    Read noise: × 1  (single readout)
    FPN:        × M_x × M_y  (correlated systematic)
"""

from __future__ import annotations

import math


def _validate_bin(mx: int, my: int, label: str) -> None:
    if mx < 1 or my < 1:
        raise ValueError(f"{label}: binning factors must be >= 1, got ({mx}, {my}).")


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
