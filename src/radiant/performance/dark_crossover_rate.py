"""Dark-current crossover rate — where dark shot noise equals read noise.

Below this dark rate the detector is read-noise-limited; above it,
dark-shot-noise-limited. Setting dark shot noise ``√(rate · t_int)`` equal
to the read noise ``σ_read`` gives the crossover dark rate:

    rate_crossover = σ_read² / t_int          [e⁻/s]

Feeding this into a measured dark-current-vs-temperature curve
(``DarkCurrentCurve.temperature_at_rate``) yields the crossover
temperature — the cooler set-point above which dark shot noise dominates.

Gap 45 (Phase T3): scenario 2.1 computed this script-side for the
InSb-vs-HgCdTe cooler-budget trade.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["DarkCrossoverError", "dark_shot_crossover_rate_e_per_s"]


class DarkCrossoverError(RadiantError):
    """Raised for out-of-range dark-crossover inputs."""


def dark_shot_crossover_rate_e_per_s(read_noise_e: float, integration_time_s: float) -> float:
    """Dark rate [e⁻/s] where dark shot noise equals the read noise.

    ``rate = σ_read² / t_int``.
    """
    if read_noise_e < 0.0:
        raise DarkCrossoverError(f"read_noise_e must be ≥ 0, got {read_noise_e}.")
    if integration_time_s <= 0.0:
        raise DarkCrossoverError(f"integration_time_s must be positive, got {integration_time_s}.")
    return read_noise_e * read_noise_e / integration_time_s
