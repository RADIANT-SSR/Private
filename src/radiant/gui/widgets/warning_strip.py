"""The in-window chain-warning strip (arch doc §4.4; owner feedback 2026-07-13).

:class:`WarningStrip` is a themed, clickable strip shown **between the KPI badge row
and the plot canvas** whenever a chain evaluation emits ``UserWarning``s (saturation
clip, NIIRS extrapolation, …). It carries the **warn** design token — deliberately
distinct from the red, non-dismissible saturation banner — and reads ``⚠ N warnings``
with the first message inline. Clicking it opens the full
:class:`~radiant.gui.widgets.warning_list_dialog.WarningListDialog`. It clears (hides)
on a warning-free evaluation.

Before this strip existed the warnings printed to the terminal, invisible to a GUI user
(owner feedback 2026-07-13); surfacing them in-window satisfies Rule 17 (warnings are
never swallowed — the worker also re-logs them).

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via the ``#warningStrip`` object name (GUI plan §4.9); this file holds no
colour/font/size literal.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget

from radiant.gui.widgets.warning_list_dialog import WarningListDialog

# Leading marker for the strip. A glyph, not a style token.
_MARKER = "⚠"


def _format_strip_text(messages: Sequence[str]) -> str:
    """``⚠ N warnings — <first message>`` (count + first line inline)."""
    count = len(messages)
    noun = "warning" if count == 1 else "warnings"
    head = f"{_MARKER} {count} {noun}"
    if messages:
        return f"{head} — {messages[0]}  (click to see all)"
    return head


class WarningStrip(QLabel):
    """A clickable warn-token strip listing chain warnings; hidden when there are none.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("warningStrip")
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._messages: list[str] = []
        self.setVisible(False)

    # -- update -------------------------------------------------------------

    def update_from_warnings(self, messages: Sequence[str]) -> None:
        """Show the count + first message, or hide the strip when *messages* is empty.

        Called after every evaluation: a warning-free run clears it (owner feedback
        2026-07-13).
        """
        self._messages = list(messages)
        if self._messages:
            self.setText(_format_strip_text(self._messages))
            self.setVisible(True)
        else:
            self.clear()
            self.setVisible(False)

    # -- interaction --------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Open the full warning list on a left click (when there are warnings)."""
        if event.button() == Qt.MouseButton.LeftButton and self._messages:
            self.open_list_dialog()
        super().mousePressEvent(event)

    def open_list_dialog(self) -> WarningListDialog:
        """Open (exec) the themed list dialog with every captured warning verbatim.

        Returns the dialog so tests can drive it without blocking on ``exec``.
        """
        dialog = WarningListDialog(self._messages, self)
        dialog.exec()
        return dialog

    # -- accessors ----------------------------------------------------------

    @property
    def messages(self) -> list[str]:
        """The warnings currently represented by the strip."""
        return list(self._messages)

    @property
    def warning_count(self) -> int:
        """How many warnings the strip currently represents."""
        return len(self._messages)


__all__ = ["WarningStrip"]
