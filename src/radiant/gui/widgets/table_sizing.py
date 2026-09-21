"""Size a table to its rows so it never becomes a five-row scroll box (CU-371).

One computation, one module (Rule 19). The MTF-budget and element-train tables
used to carry a fixed minimum height and no stretch, so they showed five or six
rows whatever the window height and scrolled inside themselves — the manual's
``flagship_mtf_budget`` figure could not show the ``mtf_pixel_aperture`` row the
prose quotes. A table's height is now its content: header plus every row plus
frame, with the stage pane's own scroll area handling overflow. The floor keeps
an empty or one-row table from collapsing into a sliver.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

__all__ = ["content_height", "fit_height_to_rows"]


def content_height(table: QTableWidget) -> int:
    """The height that shows every row of *table* without an inner scrollbar."""
    header = table.horizontalHeader()
    header_h = header.sizeHint().height() if not header.isHidden() else 0
    rows_h = sum(table.rowHeight(row) for row in range(table.rowCount()))
    frame_h = 2 * table.frameWidth()
    return header_h + rows_h + frame_h


def fit_height_to_rows(table: QTableWidget, *, floor: int = 0) -> int:
    """Pin *table*'s minimum height to its content (at least *floor*); return it.

    Called after the rows change. Only the minimum is set, so a layout may still
    give the table more room; it can never give it less than its rows need.
    """
    height = max(floor, content_height(table))
    table.setMinimumHeight(height)
    return height
