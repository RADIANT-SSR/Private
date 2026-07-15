"""The separate MATLAB-style scripting window (Command Window + Workspace).

:class:`ScriptingWindow` is the RADIANT scripting environment (arch doc §4.6.1, Pass 1,
owner-ratified 2026-07-15) — a **separate top-level window** (title "RADIANT Scripting"),
not a dock inside the main window, so the operator can move it to a second monitor. It
replaces the earlier bottom-dock console. Pass 1 delivers two of the vision's three panes:

* the **Command Window** — the reused
  :class:`~radiant.gui.widgets.scripting_console.ScriptingConsole` REPL, with the live
  ``sensor`` / ``result`` / ``plot`` / ``inspect_result`` bound, history, and figure
  pop-out; and
* the **Workspace** — the live
  :class:`~radiant.gui.widgets.workspace_panel.WorkspacePanel` variable browser of the
  command namespace.

They sit side-by-side in a horizontal splitter (Workspace left, Command Window right). The
third pane — a **multi-tab script Editor** — is **Pass 2** (CU-143), which will occupy the
top/main area above these two.

**Coherence is the main window's, unchanged.** The window does not own the coherence model:
it exposes its :attr:`console`, and the main window wires the console's ``refreshRequested``
/ ``stateMaybeChanged`` exactly as it did for the dock, so a ``sensor.set(...)`` typed here
still marks the *main* GUI stale and offers Refresh. The Workspace refreshes after each
command (the console's ``commandExecuted`` signal) and whenever the main window calls
:meth:`refresh_workspace` (after an evaluate/refresh).

**Theme.** The design-system stylesheet is installed app-wide on the :class:`QApplication`
(:func:`radiant.gui.themes.apply_theme`), so this top-level window is themed automatically
and the View-menu light/dark toggle re-themes it in step — no per-window wiring, and no
colour/font/size literal here (all panes are QSS-styled by object name).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget

from radiant.gui.widgets.scripting_console import ScriptingConsole
from radiant.gui.widgets.workspace_panel import WorkspacePanel


class ScriptingWindow(QMainWindow):
    """A separate top-level window hosting the Command Window + Workspace (arch doc §4.6.1).

    Parameters
    ----------
    parent:
        The owning widget. Passed for lifetime/ownership (the window is destroyed with the
        main window, so app exit is clean) — a :class:`QMainWindow` stays a real separate
        top-level window regardless of a parent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Qt.Window keeps this a genuine top-level window even with a parent, so it can be
        # moved to another monitor while still being owned (and cleaned up) by the main window.
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("scriptingWindow")
        self.setWindowTitle("RADIANT Scripting")
        self.resize(1040, 620)

        self._console = ScriptingConsole(self)
        self._workspace = WorkspacePanel(self)

        splitter = QSplitter(self)
        splitter.setObjectName("scriptingSplitter")
        splitter.setOrientation(Qt.Orientation.Horizontal)
        # Workspace left, Command Window right. Pass 2 adds the Editor as the top/main pane.
        splitter.addWidget(self._workspace)
        splitter.addWidget(self._console)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)
        self._splitter = splitter

        # The Workspace tracks the command namespace: refresh it after each executed command.
        self._console.commandExecuted.connect(self._on_command_executed)
        self.refresh_workspace()

    # -- public accessors ---------------------------------------------------

    @property
    def console(self) -> ScriptingConsole:
        """The Command Window REPL (the main window wires its coherence signals)."""
        return self._console

    @property
    def workspace(self) -> WorkspacePanel:
        """The live Workspace variable browser."""
        return self._workspace

    # -- workspace refresh --------------------------------------------------

    def refresh_workspace(self) -> None:
        """Rebuild the Workspace from the console's live namespace.

        Called at construction, after each executed command, and by the main window after an
        evaluate/refresh (when ``result`` is re-bound outside a command).
        """
        self._workspace.refresh(self._console.namespace_variables())

    def _on_command_executed(self, _source: str) -> None:
        self.refresh_workspace()

    # -- window management --------------------------------------------------

    def show_and_raise(self) -> None:
        """Show the window, bring it front-most, and focus the command line.

        Idempotent: re-invoking on an already-open window raises/focuses the *same* instance
        rather than spawning a duplicate (the main window keeps the single reference).
        """
        self.show()
        self.raise_()
        self.activateWindow()
        self._console.input_box.setFocus()

    # -- teardown -----------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # noqa: N802 (Qt override)
        """Close the hosted console (which closes any pop-out figure windows) on teardown.

        The window is hidden-not-destroyed on a user close (no ``WA_DeleteOnClose``), so it
        can be reopened; a real teardown (app exit) still tidies the console's figure windows.
        """
        self._console.close()
        super().closeEvent(event)


__all__ = ["ScriptingWindow"]
