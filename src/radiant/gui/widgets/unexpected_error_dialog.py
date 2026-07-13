"""Modal dialog for an *unexpected* exception: message plus a traceback fold.

:class:`UnexpectedErrorDialog` is the catch-all surface for anything that is **not** a
:class:`~radiant.core.exceptions.RadiantError` — a genuine bug rather than a rejected
input (arch doc §3.2, §11; Rules 15/17). It shows the exception's message and hides the
full traceback behind a "Show details" fold so the common case stays calm while the
detail is one click away. Nothing is swallowed: an exception the GUI cannot classify
still reaches the user in full.

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via object names (GUI plan §4.9).
"""

from __future__ import annotations

import traceback

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class UnexpectedErrorDialog(QDialog):
    """Modal error dialog with a collapsible traceback (Rules 15/17).

    Parameters
    ----------
    exc:
        The unexpected exception.
    context:
        A short line naming what the app was doing (e.g. the parameter edited),
        shown above the message.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        exc: BaseException,
        context: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("unexpectedErrorDialog")
        self.setWindowTitle("Unexpected Error")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(context, self)
        header.setObjectName("errorDialogHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        message = QLabel(f"{type(exc).__name__}: {exc}", self)
        message.setObjectName("errorDialogValue")
        message.setWordWrap(True)
        message.setTextInteractionFlags(message.textInteractionFlags().TextSelectableByMouse)
        layout.addWidget(message)

        self._details = QPlainTextEdit(self)
        self._details.setObjectName("errorDialogTraceback")
        self._details.setReadOnly(True)
        self._details.setPlainText("".join(traceback.format_exception(exc)))
        self._details.setVisible(False)
        layout.addWidget(self._details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        self._toggle = buttons.addButton("Show details", QDialogButtonBox.ButtonRole.ActionRole)
        self._toggle.setCheckable(True)
        self._toggle.toggled.connect(self._on_toggle_details)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @property
    def details(self) -> QPlainTextEdit:
        """The traceback pane (hidden until the fold is expanded)."""
        return self._details

    def _on_toggle_details(self, shown: bool) -> None:
        """Show/hide the traceback fold and adjust the button label."""
        self._details.setVisible(shown)
        self._toggle.setText("Hide details" if shown else "Show details")
        self.adjustSize()


__all__ = ["UnexpectedErrorDialog"]
