"""The small red "C" that marks a configured parameter (ADR-0010 D-2, Phase 4b).

The owner's explicit visual spec for the multi-configuration GUI: a parameter that
carries one value per configuration is marked, everywhere it appears, with a small
red **C**. Its tooltip lists *every* configuration's value with units (R-UNITS) —
see :meth:`~radiant.gui.config_scope.ConfigurationScope.summary`.

Two renderings of the one marker live here because the two host surfaces take
different kinds of child:

* :class:`ConfiguredBadge` — a tiny ``QLabel`` for the per-stage input forms, where
  the badge sits inside a real widget layout (:class:`~radiant.gui.widgets.field_row.FieldRow`).
  Its colour comes from the QSS theme via the ``configuredBadge`` object name.
* :func:`configured_badge_icon` — the same glyph painted into a ``QIcon`` for the
  parameter tree, whose rows are ``QTreeWidgetItem``s and can carry a decoration but
  not a child widget. The colour is read from the active theme's ``err`` token — the
  same red the rejected-edit surfaces use — never a literal (GUI plan §4.9).

Both are driven from the one theme token set, so the marker matches in light and
dark and moves with any future palette change.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from radiant.gui.themes import active_theme

# The badge glyph. A single letter, per the owner's spec ("a small red C").
BADGE_TEXT = "C"

# Painted-icon geometry, in device-independent px (layout geometry, not a design
# token — colours and fonts stay in themes/).
_ICON_PX = 12


def configured_badge_icon(colour: str | None = None) -> QIcon:
    """A small red "C" glyph as a ``QIcon``, for tree-row decorations.

    Parameters
    ----------
    colour:
        Hex colour to paint. Defaults to the active theme's ``err`` token — the
        same red as every other "this needs your attention" surface.
    """
    ink = colour if colour is not None else active_theme().err
    pixmap = QPixmap(_ICON_PX, _ICON_PX)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(_ICON_PX)
        painter.setFont(font)
        painter.setPen(QColor(ink))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, BADGE_TEXT)
    finally:
        painter.end()
    return QIcon(pixmap)


class ConfiguredBadge(QLabel):
    """The red "C" marker for a per-stage form field (hidden unless configured).

    Presentation only: the host (:class:`~radiant.gui.widgets.field_row.FieldRow`)
    decides when to show it and what its tooltip says. Colour and weight come from
    the ``configuredBadge`` QSS rule in both themes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(BADGE_TEXT, parent)
        self.setObjectName("configuredBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """A fixed narrow footprint so showing/hiding the badge never reflows a row."""
        return QSize(_ICON_PX, super().sizeHint().height())

    def show_for(self, summary: str) -> None:
        """Show the badge with *summary* (every configuration's value) as its tooltip."""
        self.setToolTip(summary)
        self.setVisible(True)

    def clear_badge(self) -> None:
        """Hide the badge (the parameter is shared)."""
        self.setToolTip("")
        self.setVisible(False)


__all__ = ["BADGE_TEXT", "ConfiguredBadge", "configured_badge_icon"]
