"""Canonical Unicode-subscript labels for arc annotations.

Phase 11 (PLAN.md §12). On-figure arc labels are symbol-only — the
numeric value lives in the trace `name` (legend / hover) but not on the
figure itself. Where a Unicode subscript glyph exists, prefer it over
the plain underscore form (e.g. `αₜ` rather than `alpha_t`). Where no
glyph is available (capital subscripts), fall back to ASCII.

Each entry is the on-figure text; the matching trace-name format is
held in the arc module that owns the trace.
"""

from __future__ import annotations

from typing import Final

# On-figure label text per arc (PLAN.md §12 frozen mapping).
ARC_LABELS: Final[dict[str, str]] = {
    "off_nadir": "θ_off",
    "azimuth": "az",
    "elevation": "el",
    "phase_angle": "αₜ",
    "sun_zenith": "θₛ",
    "sun_azimuth": "Δφ",
    "solar_zenith_b": "θ_sun,B",
}


def label_for(key: str) -> str:
    """Return the on-figure label for `key`. Raises KeyError on unknown keys."""
    return ARC_LABELS[key]
