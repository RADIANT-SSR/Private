"""Keep a label pill inside its viewport (CU-371 IV-031).

One computation, one module (Rule 19), Qt-free. The schematic's leader pills
(``h_s``, ``h_t``, Δh, the projected-area label) are placed at a fixed offset
from the projected marker they annotate, so a marker near the viewport edge
put its pill partly outside the widget — the ``h_s`` pill was clipped in the
manual's ``case_irst_schematic`` figure, and no capture-side fix could recover
it. The pill is now shifted back inside by the smallest translation that fits,
with a small margin; a pill wider than the viewport pins to the left edge.
"""

from __future__ import annotations

__all__ = ["clamp_rect"]


def clamp_rect(
    left: float,
    top: float,
    width: float,
    height: float,
    bounds_width: float,
    bounds_height: float,
    *,
    margin: float = 4.0,
) -> tuple[float, float]:
    """The ``(left, top)`` that keeps a ``width × height`` box inside the bounds.

    The box is moved by the smallest amount that brings it within *margin* of
    every edge; a box that does not fit pins to the top-left margin.
    """
    max_left = bounds_width - margin - width
    max_top = bounds_height - margin - height
    new_left = min(left, max_left)
    new_top = min(top, max_top)
    return max(margin, new_left), max(margin, new_top)
