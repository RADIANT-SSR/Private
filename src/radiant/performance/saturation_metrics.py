"""Saturation and dynamic range metrics — shared types and re-exports.

Implements §4.13–§4.14 of ``docs/architecture/RADIANT_Metrics.md``.

Individual computations have been moved to their own modules (Rule 19):
- ``well_margin.py`` — well saturation margin
- ``adc_margin.py`` — ADC saturation margin
- ``dynamic_range.py`` — dynamic range
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
