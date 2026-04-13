"""SNR — Signal-to-Noise Ratio and Contrast SNR.

Implements §4.1 of ``docs/RADIANT_Metrics.md``::

    SNR = S / σ_total

where ``S`` is the signal in photoelectrons and ``σ_total`` is the
RSS of all noise terms.

Contrast SNR measures detectability against a background::

    contrast_SNR = ΔS / σ_total

where ``ΔS = S_pixel − S_background`` is the signal contrast.
Positive for hot targets, negative for cold targets.

Both are pure functions of ``ChainState``.

Failure modes (per the metrics doc):
- ``σ_total = 0`` → returns ``float('inf')`` with reason
  ``"noiseless configuration"``.
- ``signal = 0`` → returns ``0.0`` (zero signal, finite noise).
- Negative signal → ``NaN`` with reason ``"negative signal"``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.core.chain import ChainState


@dataclass(frozen=True)
class SNRResult:
    """Result of an SNR computation.

    Parameters
    ----------
    value:
        Signal-to-noise ratio (dimensionless). ``float('inf')`` if
        noiseless, ``float('nan')`` on error.
    signal_e:
        Signal in photoelectrons.
    noise_e:
        Total noise (RSS) in electrons RMS.
    failure_reason:
        ``None`` on success; a human-readable string otherwise.
    """

    value: float
    signal_e: float
    noise_e: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        """True if the result is usable (not NaN, no failure)."""
        return self.failure_reason is None and math.isfinite(self.value)


def compute_snr(state: ChainState) -> SNRResult:
    """Compute SNR from a completed chain state.

    Parameters
    ----------
    state:
        A :class:`ChainState` that has been run through at least
        ``SpectralIntegrationStage`` (so ``"photoelectrons"`` frame
        exists) and ``DetectorStage`` + ``ReadoutStage`` (so noise
        terms are populated).

    Returns
    -------
    SNRResult
        Always returns a result — never raises for physics reasons.
        Check ``.failure_reason`` for error cases.
    """
    # Read signal.
    if "photoelectrons" not in state.frames:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason=(
                "No 'photoelectrons' frame in ChainState. Run SpectralIntegrationStage first."
            ),
        )

    pe_frame = state.frames["photoelectrons"]
    signal_e = pe_frame.in_band_value
    if signal_e is None:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason="'photoelectrons' frame has no in_band_value.",
        )

    if signal_e < 0.0:
        return SNRResult(
            value=float("nan"),
            signal_e=signal_e,
            noise_e=0.0,
            failure_reason=(
                f"Negative signal ({signal_e:.2f} e-). Check the upstream "
                "signal chain for sign errors."
            ),
        )

    # Compute total noise (RSS of all noise terms).
    if len(state.noise_terms) == 0:
        return SNRResult(
            value=float("inf"),
            signal_e=signal_e,
            noise_e=0.0,
            failure_reason="noiseless configuration",
        )

    noise_sq = sum(nt.value_e**2 for nt in state.noise_terms)
    noise_e = math.sqrt(noise_sq)

    if noise_e == 0.0:
        return SNRResult(
            value=float("inf"),
            signal_e=signal_e,
            noise_e=0.0,
            failure_reason="noiseless configuration",
        )

    snr = signal_e / noise_e
    return SNRResult(value=snr, signal_e=signal_e, noise_e=noise_e)


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
    # Read contrast from spectral integration outputs.
    si_out = state.stage_outputs.get("spectral_integration", {})
    contrast_e = si_out.get("contrast_e")
    if contrast_e is None:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason=(
                "No 'contrast_e' in spectral_integration stage outputs. "
                "Run SpectralIntegrationStage first."
            ),
        )

    # Compute total noise (RSS of all noise terms).
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
