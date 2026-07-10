"""Off-chip (digital) binning — signal and noise scaling.

Per ``docs/architecture/RADIANT_Detector_Complete.md`` §8:

Off-chip binning sums P_x × P_y independently-read pixels in the
digital domain after readout.

    Signal:     × P_x × P_y
    Shot noise: × √(P_x × P_y)
    Read noise: × √(P_x × P_y)  (each pixel read independently)
    FPN:        × P_x × P_y  (correlated systematic → scales with signal)
"""

from __future__ import annotations

import math

from radiant.readout.errors import ReadoutValidationError


def _validate_bin(px: int, py: int, label: str) -> None:
    if px < 1 or py < 1:
        raise ReadoutValidationError(f"{label}: binning factors must be >= 1, got ({px}, {py}).")


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
