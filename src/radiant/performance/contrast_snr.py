"""Contrast SNR — detectability against a background.

Implements contrast SNR from ``docs/architecture/RADIANT_Metrics.md`` §4.1::

    contrast_SNR = ΔS / σ_total

where ``ΔS = S_pixel − S_background`` is the signal contrast.
Positive for hot targets, negative for cold targets.

See also ``snr.py`` for absolute SNR.
"""

from __future__ import annotations

import math

from radiant.core.chain import ChainState
from radiant.performance.snr import SNRResult


def compute_contrast_snr(state: ChainState) -> SNRResult:
    """Compute contrast SNR from a completed chain state.

    Contrast SNR = ΔS / σ_total where ΔS is the signal contrast
    (signal_e − background_e) stored by SpectralIntegrationStage.

    Unlike ``compute_snr``, the contrast value can be negative (cold
    target darker than background), producing a negative SNR. This is
    physically meaningful — the sign indicates whether the target is
    brighter (+) or dimmer (−) than its surroundings.

    Returns
    -------
    SNRResult
        ``value`` may be negative. ``signal_e`` is the contrast ΔS.
    """
    # Read contrast — prefer post-readout (accounts for TDI/binning/coadds).
    ro_out = state.stage_outputs.get("readout", {})
    contrast_e = ro_out.get("contrast_e_final")
    if contrast_e is None:
        # Fall back to pre-readout contrast (legacy / no ReadoutStage).
        si_out = state.stage_outputs.get("spectral_integration", {})
        contrast_e = si_out.get("contrast_e")
    if contrast_e is None:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason=(
                "No contrast_e available. Run SpectralIntegrationStage and ReadoutStage first."
            ),
        )

    # Compute total noise — prefer sigma_total_e (respects noise_regime).
    ro_out = state.stage_outputs.get("readout", {})
    noise_e: float | None = ro_out.get("sigma_total_e")

    if noise_e is None:
        if len(state.noise_terms) == 0:
            return SNRResult(
                value=float("inf") if contrast_e >= 0 else float("-inf"),
                signal_e=contrast_e,
                noise_e=0.0,
                failure_reason="noiseless configuration",
            )
        noise_sq = sum(nt.value_e**2 for nt in state.noise_terms)
        noise_e = math.sqrt(noise_sq)

    if noise_e == 0.0:
        return SNRResult(
            value=float("inf") if contrast_e >= 0 else float("-inf"),
            signal_e=contrast_e,
            noise_e=0.0,
            failure_reason="noiseless configuration",
        )

    contrast_snr = contrast_e / noise_e
    return SNRResult(
        value=contrast_snr,
        signal_e=contrast_e,
        noise_e=noise_e,
    )
