"""Noise-equivalent irradiance (NEI) — the SNR = 1 focal-plane flux.

NEI is the focal-plane photon irradiance that produces a signal equal to
the total noise (SNR = 1). Inverting ``signal_e = Φ · QE · A_pixel ·
t_int`` at ``signal_e = σ_total``:

    NEI = σ_total / (QE · A_pixel · t_int)      [photons/s/cm²]

Multiplying by the photon energy ``h c / λ`` converts to W/cm² (approximate
— uses the band-center photon energy).

Gap 45 (Phase T3): scenario 2.1 computed this script-side as the detector
sensitivity floor for the InSb-vs-HgCdTe trade.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = ["NoiseEquivalentIrradianceError", "noise_equivalent_irradiance_ph_s_cm2"]


class NoiseEquivalentIrradianceError(RadiantError):
    """Raised for out-of-range NEI inputs."""


def noise_equivalent_irradiance_ph_s_cm2(
    total_noise_e: float,
    qe: float,
    pixel_area_cm2: float,
    integration_time_s: float,
) -> float:
    """Focal-plane NEI [photons/s/cm²] at SNR = 1.

    ``NEI = σ_total / (QE · A_pixel · t_int)``.
    """
    if total_noise_e < 0.0:
        raise NoiseEquivalentIrradianceError(f"total_noise_e must be ≥ 0, got {total_noise_e}.")
    if not 0.0 < qe <= 1.0:
        raise NoiseEquivalentIrradianceError(f"qe must be in (0, 1], got {qe}.")
    if pixel_area_cm2 <= 0.0:
        raise NoiseEquivalentIrradianceError(
            f"pixel_area_cm2 must be positive, got {pixel_area_cm2}."
        )
    if integration_time_s <= 0.0:
        raise NoiseEquivalentIrradianceError(
            f"integration_time_s must be positive, got {integration_time_s}."
        )
    return total_noise_e / (qe * pixel_area_cm2 * integration_time_s)
