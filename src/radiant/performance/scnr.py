"""SCNR — Signal-to-Clutter-plus-Noise Ratio (Gap 77).

The detection figure of merit for a target against a structured
background. Unlike ``snr`` and ``contrast_snr`` — whose denominator is
``sigma_total_e`` and therefore respects ``detector.noise_regime`` (which
may be temporal-only) — SCNR **always** includes the spatial (clutter,
PRNU, DSNU) noise, because clutter is the defining term of the metric::

    SCNR = ΔS / √(σ_temporal² + σ_spatial²)

where ``ΔS`` is the target-vs-background contrast (``contrast_e``) and the
spatial RSS carries the clutter term ``clutter_sigma · background_e``.

See ``contrast_snr.py`` for the noise-regime-respecting contrast SNR and
``snr.py`` for absolute SNR.
"""

from __future__ import annotations

import math

from radiant.core.chain import ChainState
from radiant.performance.snr import SNRResult


def compute_scnr(state: ChainState) -> SNRResult:
    """Compute SCNR = ΔS / √(σ_temporal² + σ_spatial²) from a chain state.

    Reads the post-readout contrast and the temporal/spatial noise RSS
    stored by ``ReadoutStage``. Returns a result-typed failure (Rule 17
    metric-layer carve-out) when the required quantities are missing.

    Returns
    -------
    SNRResult
        ``value`` may be negative (cold target). ``signal_e`` is the
        contrast ΔS; ``noise_e`` is the clutter-inclusive total noise.
    """
    ro_out = state.stage_outputs.get("readout", {})

    contrast_e = ro_out.get("contrast_e_final")
    if contrast_e is None:
        si_out = state.stage_outputs.get("spectral_integration", {})
        contrast_e = si_out.get("contrast_e")
    if contrast_e is None:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason=(
                "No contrast_e available for SCNR. Run SpectralIntegrationStage "
                "and ReadoutStage first."
            ),
        )

    sigma_temporal = ro_out.get("sigma_temporal_e")
    sigma_spatial = ro_out.get("sigma_spatial_e")
    if sigma_temporal is None or sigma_spatial is None:
        return SNRResult(
            value=float("nan"),
            signal_e=contrast_e,
            noise_e=0.0,
            failure_reason=(
                "SCNR needs sigma_temporal_e and sigma_spatial_e from "
                "ReadoutStage (clutter-inclusive noise split)."
            ),
        )

    noise_e = math.sqrt(sigma_temporal**2 + sigma_spatial**2)
    if noise_e == 0.0:
        return SNRResult(
            value=float("inf") if contrast_e >= 0 else float("-inf"),
            signal_e=contrast_e,
            noise_e=0.0,
            failure_reason="noiseless configuration",
        )

    return SNRResult(
        value=contrast_e / noise_e,
        signal_e=contrast_e,
        noise_e=noise_e,
    )
