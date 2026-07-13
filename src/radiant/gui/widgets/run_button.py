"""The accent Run / Evaluate button (mockup ``.runbtn``; QSS hook ``#runButton``).

:class:`RunButton` is the terracotta-accent primary action from the mockup's KPI
strip. GUI plan Phase 1 ships it **disabled** — there is nothing to evaluate until the
Phase 3 evaluate loop and a loaded config exist. Its accent styling comes from the
existing ``QPushButton#runButton`` QSS rule (GUI plan §4.9); this file only sets the
object name, label, and disabled state.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

# The label pairs the action with its shortcut (Run ▸ Evaluate, F5 — arch doc §10).
_LABEL: str = "Evaluate  F5"


class RunButton(QPushButton):
    """The accent Evaluate button, disabled in the Phase 1 shell.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_LABEL, parent)
        self.setObjectName("runButton")
        # Phase 1 is behaviour-free: present, accent-styled, but not clickable.
        self.setEnabled(False)
        self.setToolTip("Evaluate the full chain (F5) — available once a config is loaded")
