"""Saturation and dynamic range metrics.

Implements §4.13–§4.14 of ``docs/RADIANT_Metrics.md``.

Well margin [dB]:
    margin_well = 20 · log10(FWC / S_well)

ADC margin [dB]:
    margin_adc = 20 · log10(max_dn / S_dn)

Dynamic range [dB]:
    DR = 20 · log10(FWC / σ_dark)

All quantities are per-pixel (post-TDI, post-binning for well margin;
post-ADC for ADC margin).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MarginResult:
    """Saturation margin result.

    Parameters
    ----------
    margin_dB:
        Margin in dB. Positive = headroom, negative = saturated.
        ``float('nan')`` on failure.
    signal:
        Signal level (electrons or DN depending on context).
    capacity:
        Full-scale capacity (FWC or max_dn).
    failure_reason:
        ``None`` on success.
    """

    margin_dB: float
    signal: float
    capacity: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.margin_dB)

    @property
    def is_saturated(self) -> bool:
        """True if signal exceeds capacity (margin < 0)."""
        return self.ok and self.margin_dB < 0.0


def compute_well_margin(signal_e: float, fwc_e: float) -> MarginResult:
    """Compute well saturation margin.

    Parameters
    ----------
    signal_e:
        Signal electrons at well check point (post-TDI, post-on-chip-bin).
    fwc_e:
        Full well capacity [e-]. Must be > 0.
    """
    if fwc_e <= 0.0:
        return MarginResult(
            margin_dB=float("nan"),
            signal=signal_e,
            capacity=fwc_e,
            failure_reason=f"FWC = {fwc_e} must be > 0.",
        )
    if signal_e <= 0.0:
        return MarginResult(
            margin_dB=float("inf"),
            signal=signal_e,
            capacity=fwc_e,
            failure_reason="Signal <= 0; margin is infinite.",
        )
    margin = 20.0 * math.log10(fwc_e / signal_e)
    return MarginResult(margin_dB=margin, signal=signal_e, capacity=fwc_e)


def compute_adc_margin(signal_dn: float, max_dn: int) -> MarginResult:
    """Compute ADC saturation margin.

    Parameters
    ----------
    signal_dn:
        Signal in digital numbers at ADC output.
    max_dn:
        Maximum ADC output (``2^n_bits - 1``). Must be > 0.
    """
    if max_dn <= 0:
        return MarginResult(
            margin_dB=float("nan"),
            signal=signal_dn,
            capacity=float(max_dn),
            failure_reason=f"max_dn = {max_dn} must be > 0.",
        )
    if signal_dn <= 0.0:
        return MarginResult(
            margin_dB=float("inf"),
            signal=signal_dn,
            capacity=float(max_dn),
            failure_reason="Signal <= 0; margin is infinite.",
        )
    margin = 20.0 * math.log10(float(max_dn) / signal_dn)
    return MarginResult(
        margin_dB=margin,
        signal=signal_dn,
        capacity=float(max_dn),
    )


@dataclass(frozen=True)
class DynamicRangeResult:
    """Dynamic range result.

    Parameters
    ----------
    value_dB:
        Dynamic range in dB. ``float('nan')`` on failure.
    fwc_e:
        Full well capacity [e-].
    noise_floor_e:
        Noise floor [e- RMS] (typically dark noise + read noise RSS).
    failure_reason:
        ``None`` on success.
    """

    value_dB: float
    fwc_e: float
    noise_floor_e: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value_dB)


def compute_dynamic_range(fwc_e: float, noise_floor_e: float) -> DynamicRangeResult:
    """Compute dynamic range = 20·log10(FWC / σ_floor).

    Parameters
    ----------
    fwc_e:
        Full well capacity [e-]. Must be > 0.
    noise_floor_e:
        Noise floor [e- RMS]. Must be > 0. Typically RSS of dark,
        read, and quantization noise.
    """
    if fwc_e <= 0.0:
        return DynamicRangeResult(
            value_dB=float("nan"),
            fwc_e=fwc_e,
            noise_floor_e=noise_floor_e,
            failure_reason=f"FWC = {fwc_e} must be > 0.",
        )
    if noise_floor_e <= 0.0:
        return DynamicRangeResult(
            value_dB=float("nan"),
            fwc_e=fwc_e,
            noise_floor_e=noise_floor_e,
            failure_reason=f"Noise floor = {noise_floor_e} must be > 0.",
        )
    dr = 20.0 * math.log10(fwc_e / noise_floor_e)
    return DynamicRangeResult(
        value_dB=dr,
        fwc_e=fwc_e,
        noise_floor_e=noise_floor_e,
    )
