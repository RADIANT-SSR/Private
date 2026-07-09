"""BLIP rate — the photon-generated electron rate a detector must beat.

A detector is background-limited (BLIP) when its dark rate is below the
photon-generated rate. The BLIP threshold rate is simply the collected
photo-electrons per unit time:

    rate_blip = signal_e / t_int              [e⁻/s]

Feeding this into a measured dark-current-vs-temperature curve
(``DarkCurrentCurve.temperature_at_rate``) yields the BLIP temperature —
the highest cooler set-point at which the detector is still
background-limited.

Gap 45 (Phase T3): scenario 2.1 computed this script-side for the
InSb-vs-HgCdTe cooler-budget trade.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["BlipRateError", "blip_rate_e_per_s"]


class BlipRateError(RadiantError):
    """Raised for out-of-range BLIP-rate inputs."""


def blip_rate_e_per_s(photon_signal_e: float, integration_time_s: float) -> float:
    """Photon-generated electron rate [e⁻/s] = ``signal_e / t_int``."""
    if photon_signal_e < 0.0:
        raise BlipRateError(f"photon_signal_e must be ≥ 0, got {photon_signal_e}.")
    if integration_time_s <= 0.0:
        raise BlipRateError(f"integration_time_s must be positive, got {integration_time_s}.")
    return photon_signal_e / integration_time_s
