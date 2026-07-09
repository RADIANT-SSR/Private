"""Contrast SNR — detectability against a background.

Implements contrast SNR from ``docs/architecture/RADIANT_Metrics.md`` §4.1::

    contrast_SNR = ΔS / σ_total

where ``ΔS = S_pixel − S_background`` is the signal contrast.
Positive for hot targets, negative for cold targets.

See also ``snr.py`` for absolute SNR.
"""

from __future__ import annotations

import math
import warnings

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

    # CU-061: when the pixel saturates, the readout caps the signal (and its
    # shot noise) at full well but the contrast (ΔS) is NOT re-derived from the
    # clipped signals — so contrast_snr = ΔS_uncapped / σ_capped is inflated and
    # unreliable. Detect saturation param-free: signal_e_final < signal_e_pre
    # means the readout clipped. The clipped differential is a readout-physics
    # quantity the metric layer cannot reconstruct (it lacks the reference
    # pixel's own clip), so we surface a failure_reason and warn rather than
    # report a silently-wrong contrast (Rule 17, metric-layer carve-out ADR-B).
    si_out = state.stage_outputs.get("spectral_integration", {})
    s_t_pre = si_out.get("signal_e")
    s_t_final = ro_out.get("signal_e_final")
    saturation_reason: str | None = None
    if s_t_pre and s_t_final is not None and s_t_final < s_t_pre * (1.0 - 1e-9):
        saturation_reason = (
            f"pixel saturated (signal {s_t_pre:.3e} e- clipped to full well "
            f"{s_t_final:.3e} e-); contrast_snr is unreliable — reduce integration "
            "time or raise full_well_capacity_e"
        )
        warnings.warn(saturation_reason, UserWarning, stacklevel=2)

    # ADR-0005 (Gap 52): when an extended contrast reference is configured,
    # the contrast is a two-pixel spatial differential, so its noise is the
    # combined noise of the target and reference pixels, √(N_t² + N_ref²).
    # The reference pixel's noise differs from the target's only in the
    # signal-shot term, so N_ref² = N_t² − S_t + S_ref. Exact for staring
    # sensors (no TDI/binning); first-order otherwise.
    ref_signal_e = si_out.get("contrast_reference_signal_e")
    if ref_signal_e is not None:
        s_t_raw = s_t_final if s_t_final is not None else s_t_pre
        s_t = float(s_t_raw) if s_t_raw is not None else 0.0
        scale = (s_t / s_t_pre) if s_t_pre else 1.0
        s_ref = ref_signal_e * scale
        n_ref_sq = max(0.0, noise_e**2 - s_t + s_ref)
        combined_noise = math.sqrt(noise_e**2 + n_ref_sq)
        if combined_noise > 0.0:
            return SNRResult(
                value=contrast_e / combined_noise,
                signal_e=contrast_e,
                noise_e=combined_noise,
                failure_reason=saturation_reason,
            )

    contrast_snr = contrast_e / noise_e
    return SNRResult(
        value=contrast_snr,
        signal_e=contrast_e,
        noise_e=noise_e,
        failure_reason=saturation_reason,
    )
