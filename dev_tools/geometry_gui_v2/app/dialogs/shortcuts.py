"""Keyboard-shortcuts help dialog.

Phase 5 originally inlined this in ``main.py``; Phase 6 (PLAN_v2.md §14
step 2 — Help → Keyboard shortcuts menu item) splits it into its own
file per Rule 19. The binding table is the single source of truth for
both the dialog and the eventual README shortcut listing.

Rule 19: own file.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# Shown verbatim in the dialog and (Phase 7) in the README.
SHORTCUT_BINDINGS: Final[tuple[tuple[str, str], ...]] = (
    ("R", "Reset camera"),
    ("1", "Front view"),
    ("2", "Back view"),
    ("3", "Left view"),
    ("4", "Right view"),
    ("5", "Top view"),
    ("6", "Bottom view"),
    ("?", "This dialog"),
    ("Ctrl+Q", "Quit"),
)


class ShortcutsDialog(QDialog):
    """Modal dialog listing every Phase-5/6 keyboard binding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shortcuts_dialog")
        self.setWindowTitle("Keyboard shortcuts")
        layout = QVBoxLayout(self)

        rows = "".join(
            f"<tr><td><b>{key}</b></td><td>{action}</td></tr>"
            for key, action in SHORTCUT_BINDINGS
        )
        body = QLabel(f"<table cellspacing='6'>{rows}</table>")
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
