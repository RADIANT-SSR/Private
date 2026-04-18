"""SNR — Signal-to-Noise Ratio.

Implements §4.1 of ``docs/RADIANT_Metrics.md``::

    SNR = S / σ_total

where ``S`` is the signal in photoelectrons and ``σ_total`` is the
RSS of all noise terms.

Failure modes (per the metrics doc):
- ``σ_total = 0`` → returns ``float('inf')`` with reason
  ``"noiseless configuration"``.
- ``signal = 0`` → returns ``0.0`` (zero signal, finite noise).
- Negative signal → ``NaN`` with reason ``"negative signal"``.

See also ``contrast_snr.py`` for contrast SNR.
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
    # Read signal.  Prefer post-readout signal (accounts for TDI, binning,
    # coadds) when available; fall back to pre-readout photoelectrons.
    ro_out = state.stage_outputs.get("readout", {})
    signal_e_final = ro_out.get("signal_e_final")
    if signal_e_final is not None:
        signal_e = signal_e_final
    elif "photoelectrons" in state.frames:
        pe_frame = state.frames["photoelectrons"]
        signal_e = pe_frame.in_band_value
    else:
        signal_e = None

    if signal_e is None:
        return SNRResult(
            value=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            failure_reason=(
                "No signal source: neither readout.signal_e_final nor "
                "'photoelectrons' frame is available."
            ),
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

    # Compute total noise.  Prefer sigma_total_e from ReadoutStage
    # (respects noise_regime: temporal-only for "imaging", all for
    # "detection").  Fall back to RSS of all noise terms.
    noise_e: float | None = ro_out.get("sigma_total_e")

    if noise_e is None:
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
