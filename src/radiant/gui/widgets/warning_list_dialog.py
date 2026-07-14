"""Modal dialog listing the chain warnings captured during an evaluation (§4.4).

:class:`WarningListDialog` is the expanded view behind the right-rail Messages panel
(:class:`~radiant.gui.widgets.messages_panel.MessagesPanel`). The panel lists each warning
as a clickable row; clicking any opens this dialog, which lists **every** captured warning
verbatim (saturation clip, NIIRS extrapolation, …) so the owner reads them in-window rather
than hunting the terminal (owner feedback 2026-07-13, Rule 17 — warnings surfaced, never
swallowed).

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via object names (GUI plan §4.9); this file sets structure and text only.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class WarningListDialog(QDialog):
    """Modal list of every warning a chain evaluation emitted (§4.4, warn token).

    Parameters
    ----------
    messages:
        The captured warning strings, in emission order. Rendered verbatim.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        messages: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._messages = list(messages)
        self.setObjectName("warningListDialog")
        count = len(self._messages)
        self.setWindowTitle(f"Warnings — {count}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(
            f"{count} warning{'s' if count != 1 else ''} from the last evaluation", self
        )
        header.setObjectName("warningDialogHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        self._body = QPlainTextEdit(self)
        self._body.setObjectName("warningDialogBody")
        self._body.setReadOnly(True)
        # One warning per line, verbatim — the owner reads the full text, not a summary.
        self._body.setPlainText("\n\n".join(self._messages))
        layout.addWidget(self._body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @property
    def body(self) -> QPlainTextEdit:
        """The read-only pane holding the verbatim warning list."""
        return self._body

    @property
    def messages(self) -> list[str]:
        """The warnings this dialog lists."""
        return list(self._messages)


__all__ = ["WarningListDialog"]
