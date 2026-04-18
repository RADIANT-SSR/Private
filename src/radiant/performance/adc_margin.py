"""ADC saturation margin.

Implements §4.13 of ``docs/RADIANT_Metrics.md``::

    margin_adc = 20 · log10(max_dn / S_dn)  [dB]
"""

from __future__ import annotations

import math

from radiant.performance.saturation_metrics import MarginResult


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
