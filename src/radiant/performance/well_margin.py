"""Well saturation margin.

Implements §4.13 of ``docs/RADIANT_Metrics.md``::

    margin_well = 20 · log10(FWC / S_well)  [dB]
"""

from __future__ import annotations

import math

from radiant.performance.saturation_metrics import MarginResult


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
