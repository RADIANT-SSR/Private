"""A single clickable message row for the right-rail Messages panel (arch doc §4.5).

:class:`MessageItem` is one warning or error line in the Messages panel: a themed,
clickable label carrying the full text, tinted by its severity token (**warn** for a
chain ``UserWarning``, **err** for a ``RadiantError``). Clicking it emits
:attr:`clicked`, which the panel wires to the appropriate full-view dialog (the verbatim
warning list, or the actionable what/why/action).

One widget class per file (Rule 19). Styling is entirely themed via the ``#messageItem``
object name and a ``severity`` dynamic property (GUI plan §4.9); this file holds no
colour/font/size literal.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget

# Severity tokens (drive the QSS variant + the leading glyph).
SEVERITY_WARNING: str = "warning"
SEVERITY_ERROR: str = "error"

_GLYPH: dict[str, str] = {SEVERITY_WARNING: "⚠", SEVERITY_ERROR: "⛌"}


class MessageItem(QLabel):
    """A clickable warn/err message row; :attr:`clicked` opens its full view.

    Parameters
    ----------
    text:
        The message text (rendered inline after the severity glyph).
    severity:
        :data:`SEVERITY_WARNING` or :data:`SEVERITY_ERROR`.
    parent:
        The owning widget, if any.

    Signals
    -------
    clicked():
        Emitted on a left click, so the panel can open the full-view dialog.
    """

    clicked = Signal()

    def __init__(
        self,
        text: str,
        severity: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("messageItem")
        self.setProperty("severity", severity)
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        glyph = _GLYPH.get(severity, "")
        self.setText(f"{glyph}  {text}" if glyph else text)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Emit :attr:`clicked` on a left click (opens the full message view)."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


__all__ = ["MessageItem", "SEVERITY_WARNING", "SEVERITY_ERROR"]
