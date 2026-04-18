"""Dynamic range.

Implements §4.14 of ``docs/RADIANT_Metrics.md``::

    DR = 20 · log10(FWC / σ_dark)  [dB]
"""

from __future__ import annotations

import math
from dataclasses import dataclass


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
