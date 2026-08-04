"""Delegate painting the Source column's provenance as the DESIGN pill (§8.4).

The design system specifies a **provenance pill** — 1 px ``line`` border, 9 px
radius, small mono text, ``muted`` ink — for the badge that renders the
user-set / config / derived provenance state (arch doc §8.4). Until the
2026-08-03 critique the tree's Source column was plain body text, so thirty
"default" rows shouted exactly as loudly as the one row the analyst had
actually changed. This delegate paints:

* **default** (and empty) provenance as recessive plain text in ``muted_2`` —
  the resting state should disappear;
* every other provenance ("config", "user-set", "derived", "sampled") as the
  documented pill, so changed/derived rows are scannable at a glance.

Colours come from the active theme via
:func:`~radiant.gui.themes.stylesheet.active_theme` (never a literal — GUI plan
§4.9); the pill's geometry constants are layout, not design tokens. The
delegate is read-only (the Source column was already non-editable through
:class:`ReadOnlyCellDelegate`, which it extends).

One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from radiant.gui.themes.fonts import mono_font
from radiant.gui.themes.stylesheet import active_theme
from radiant.gui.widgets.parameter_delegate import ReadOnlyCellDelegate

if TYPE_CHECKING:
    pass

# Pill geometry (layout px, not design tokens): §8.4 sets the 9 px radius and
# small mono type; padding keeps the text off the border.
_PILL_RADIUS = 9.0
_PILL_PAD_X = 7.0
_PILL_TEXT_PT = 8.0
_RECESSIVE_LABELS = frozenset({"", "default"})


class ProvenancePillDelegate(ReadOnlyCellDelegate):
    """Paint provenance labels as §8.4 pills; keep "default" recessive."""

    def paint(  # noqa: D102 — QStyledItemDelegate override
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        label = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        theme = active_theme()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Keep the row's selection/zebra background exactly as the base paints it.
        background_only = QStyleOptionViewItem(option)
        background_only.text = ""
        style = option.widget.style() if option.widget else None
        if style is not None:
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, background_only, painter, option.widget
            )

        font = mono_font(_PILL_TEXT_PT)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(label)
        pill_h = metrics.height() + 4.0
        rect = option.rect
        x = rect.x() + 4.0
        y = rect.y() + (rect.height() - pill_h) / 2.0

        if label in _RECESSIVE_LABELS:
            painter.setPen(QPen(QColor(theme.muted_2)))
            painter.drawText(
                rect.adjusted(6, 0, -2, 0),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                label,
            )
        else:
            pill = QRectF(x, y, text_w + 2 * _PILL_PAD_X, pill_h)
            painter.setPen(QPen(QColor(theme.line)))
            painter.setBrush(QColor(theme.panel_2))
            painter.drawRoundedRect(pill, _PILL_RADIUS, _PILL_RADIUS)
            painter.setPen(QPen(QColor(theme.muted)))
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), label)
        painter.restore()


__all__ = ["ProvenancePillDelegate"]
