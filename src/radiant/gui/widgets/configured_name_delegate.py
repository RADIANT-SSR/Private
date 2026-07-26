"""The parameter tree's name column — text, then the red "C" (§4.2c, owner 2026-07-26).

Phase 4b marked a configured tree row with ``QTreeWidgetItem.setIcon(0, …)``, which Qt
paints in the item's **decoration** slot: to the *left* of the name. The owner's
2026-07-26 feedback is explicit — *"move the red C just to the right of the variable
name"* — and a decoration slot cannot do that. This delegate can: it paints the row
normally and then draws the badge immediately after the name's text advance, so the
marker reads as a suffix of the parameter it marks, matching the per-stage form rows
(where the badge sits between the label and the value box).

It extends :class:`~radiant.gui.widgets.parameter_delegate.ReadOnlyCellDelegate`, so the
Parameter column keeps its existing contract of never opening an in-place editor (a
double-click there opens the full Parameter Editor instead, §4.3).

:meth:`ConfiguredNameDelegate.badge_rect` is the placement decision, factored out of
:meth:`paint` so it is assertable without a rendered window (the tests check that the
badge lands to the *right* of the text and inside the cell).

The glyph and its colour come from
:func:`~radiant.gui.widgets.configured_badge.configured_badge_icon` — the one painted
"C", themed from the ``err`` token (GUI plan §4.9). No colour literal lives here; the
only numbers are layout geometry.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRect, Qt
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from radiant.gui.widgets.configured_badge import configured_badge_icon
from radiant.gui.widgets.parameter_delegate import ReadOnlyCellDelegate

# Item-data role marking a row as configured (one value per configuration). Lives here,
# next to the delegate that reads it, so the painter and the panel that sets it cannot
# drift; the panel re-exports it.
CONFIGURED_ROLE = int(Qt.ItemDataRole.UserRole) + 2

# Badge side and the gap between the name text and the badge, in device-independent
# px — layout geometry, not design tokens (colour stays in themes/).
BADGE_PX = 12
_TEXT_GAP_PX = 6


class ConfiguredNameDelegate(ReadOnlyCellDelegate):
    """Paints the Parameter column, then the red "C" just right of the name text."""

    def badge_rect(self, option: QStyleOptionViewItem, index: QModelIndex) -> QRect | None:
        """Where the badge is drawn for *index*, or ``None`` when the row is shared.

        The origin is the cell's text origin plus the name's own text advance plus a
        small gap — i.e. immediately right of the variable name. It is clamped to the
        cell's right edge so a long, elided name pushes the badge to the column edge
        rather than out of the row.
        """
        if not bool(index.data(CONFIGURED_ROLE)):
            return None
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        cell = styled.rect  # type: ignore[attr-defined]
        if cell.width() < BADGE_PX:
            return None
        widget = styled.widget  # type: ignore[attr-defined]
        style = widget.style() if widget is not None else None
        margin = (
            style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, styled, widget) + 1
            if style is not None
            else 1
        )
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        advance = QFontMetrics(styled.font).horizontalAdvance(text)  # type: ignore[attr-defined]
        left = min(
            cell.left() + margin + advance + _TEXT_GAP_PX,
            cell.right() - BADGE_PX + 1,
        )
        top = cell.top() + max((cell.height() - BADGE_PX) // 2, 0)
        return QRect(left, top, BADGE_PX, BADGE_PX)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Draw the row as usual, then the configured badge after the name text."""
        super().paint(painter, option, index)
        rect = self.badge_rect(option, index)
        if rect is None:
            return
        configured_badge_icon().paint(painter, rect)


__all__ = ["BADGE_PX", "CONFIGURED_ROLE", "ConfiguredNameDelegate"]
