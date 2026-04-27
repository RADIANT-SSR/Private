"""Anchor-keyed color palette for arc annotations.

Phase 11 (PLAN.md §12). Earlier phases assigned colors per-module, which
produced nine unrelated picks. This palette groups colors by anchor:
arcs measured at the observer share one hue, target arcs share another,
etc. Each arc module reads its color from this table; tests pin the
mapping.

Also exports the projection alpha used by every projection-companion arc
so the dashed companions render at half opacity of their parent's color.
"""

from __future__ import annotations

from typing import Final

# Anchor-keyed color palette (hex strings; PLAN.md §12 frozen mapping).
ARC_PALETTE: Final[dict[str, str]] = {
    "observer": "#1f4ea8",   # nadir reference, off-nadir, az, el
    "target": "#a83030",     # phase angle α_t, view ray
    "background": "#7a3a1a", # n_B, s_B, θ_sun,B
    "sun": "#c08020",        # θ_s, Δφ
}

# Projection-companion opacity (PLAN.md §12: parent's color, alpha 0.5).
PROJECTION_ALPHA: Final[float] = 0.5


def arc_color_for(anchor: str) -> str:
    """Return the palette color for `anchor`. Raises KeyError on unknown keys."""
    return ARC_PALETTE[anchor]
