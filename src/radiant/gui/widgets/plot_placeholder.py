"""The empty-canvas placeholder shown before the first plot (§4.4).

:class:`PlotPlaceholder` is the themed panel that occupies the visualization area
until the Phase 3 evaluate loop renders a matplotlib figure into it. It shows a
single centred, muted prompt. Behaviour-free; colour/typography is themed via the
``#plotPlaceholder`` / ``#plotPlaceholderMsg`` object names (GUI plan §4.9).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

#: No document open at all.
_PROMPT: str = "Open a configuration and run Evaluate (F5)"
#: A (possibly blank) configuration IS open — invite the edit, name the gesture
#: (live review 2026-09-07: on a blank File -> New the old prompt told the
#: operator to open a config while one was open, reading as "editing blocked").
_EDIT_PROMPT: str = (
    "New configuration — double-click a parameter row (or any stage input "
    "field) to edit, then Evaluate (F5)"
)


class PlotPlaceholder(QFrame):
    """A themed panel with a centred muted prompt (Phase 1 empty canvas).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("plotPlaceholder")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        message = QLabel(_PROMPT, self)
        message.setObjectName("plotPlaceholderMsg")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)

        layout.addStretch(1)
        layout.addWidget(message)
        layout.addStretch(1)
        self._message = message

    def show_edit_prompt(self, editing: bool) -> None:
        """Switch between the no-document prompt and the config-open edit invite."""
        self._message.setText(_EDIT_PROMPT if editing else _PROMPT)
