"""The separate MATLAB-style scripting window (Editor + Command Window + Workspace).

:class:`ScriptingWindow` is the RADIANT scripting environment (arch doc §4.6.1) — a **separate
top-level window** (title "RADIANT Scripting"), not a dock inside the main window, so the
operator can move it to a second monitor. As of Pass 2 it delivers all three of the vision's
panes in an outer vertical splitter:

* the **Editor** (top/main pane) — a multi-tab Python
  :class:`~radiant.gui.widgets.script_editor.ScriptEditor` (open / write / save / **Run**
  multiple ``.py`` scripts); and, below it in the Pass-1 horizontal splitter,
* the **Command Window** — the reused
  :class:`~radiant.gui.widgets.scripting_console.ScriptingConsole` REPL, with the live
  ``sensor`` / ``result`` / ``plot`` / ``inspect_result`` bound, history, and figure pop-out; and
* the **Workspace** — the live
  :class:`~radiant.gui.widgets.workspace_panel.WorkspacePanel` variable browser of the
  command namespace.

**Run shares the Command Window's namespace (the MATLAB core).** The Editor's **Run** /
**Run Selection** execute the active tab's text through
:meth:`~radiant.gui.widgets.scripting_console.ScriptingConsole.run_script` — the *same* shared
namespace the command line and Workspace use. A script's top-level ``x = result.snr()`` therefore
leaves ``x`` bound for the next command line and visible in the Workspace; stdout/stderr and any
traceback route into the Command Window transcript (surfaced, never swallowed — Rule 17); and a
``sensor.set(...)`` in a script marks the **main** GUI stale exactly like a typed command (the
window does not own the coherence model — it exposes its :attr:`console`, whose signals the main
window wires).

**File ops** (menu bar + toolbar) mirror the main window's Phase-9 file pattern but over plain
``.py`` text (New / Open / Open Recent / Save / Save As), with a persisted recent-scripts list
(:class:`~radiant.gui.settings_store.SettingsStore`) kept distinct from the config recent list. A
bad file load surfaces the actionable/traceback error dialog and leaves the open tabs intact.

**Theme.** The design-system stylesheet is installed app-wide on the :class:`QApplication`
(:func:`radiant.gui.themes.apply_theme`), so this window is themed automatically; the one part
QSS cannot reach — the Editor's syntax-highlight glyph colours — re-applies through
:meth:`set_theme`, which the main window's View → Dark/Light toggle calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QSplitter,
    QWidget,
)

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.settings_store import SettingsStore
from radiant.gui.themes import Theme
from radiant.gui.widgets.script_editor import ScriptEditor
from radiant.gui.widgets.script_tab import ScriptTab
from radiant.gui.widgets.scripting_console import ScriptingConsole
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog
from radiant.gui.widgets.workspace_panel import WorkspacePanel

# The Python-script file filter for the Editor's Open / Save-As dialogs.
_SCRIPT_FILTER: str = "Python script (*.py);;All files (*)"


class ScriptingWindow(QMainWindow):
    """A separate top-level window hosting the Editor + Command Window + Workspace (§4.6.1).

    Parameters
    ----------
    parent:
        The owning widget. Passed for lifetime/ownership (the window is destroyed with the
        main window, so app exit is clean) — a :class:`QMainWindow` stays a real separate
        top-level window regardless of a parent.
    settings:
        The shared preferences store (recent scripts persist through it). ``None`` opens the
        default RADIANT-scoped store; tests inject a temp-file-backed one.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings: SettingsStore | None = None,
    ) -> None:
        # Qt.Window keeps this a genuine top-level window even with a parent, so it can be
        # moved to another monitor while still being owned (and cleaned up) by the main window.
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("scriptingWindow")
        self.setWindowTitle("RADIANT Scripting")
        # A real workspace opens large enough to author + query side by side (arch doc §4.6.1).
        self.resize(1100, 760)

        self._settings: SettingsStore = settings if settings is not None else SettingsStore()
        self._actions: dict[str, QAction] = {}

        self._editor = ScriptEditor(self)
        self._console = ScriptingConsole(self)
        self._workspace = WorkspacePanel(self)

        # Bottom row: Workspace left, Command Window right (the Pass-1 horizontal splitter).
        bottom = QSplitter(self)
        bottom.setObjectName("scriptingSplitter")
        bottom.setOrientation(Qt.Orientation.Horizontal)
        bottom.addWidget(self._workspace)
        bottom.addWidget(self._console)
        bottom.setStretchFactor(0, 2)
        bottom.setStretchFactor(1, 3)
        self._bottom_splitter = bottom

        # Outer column: Editor on top (the prominent pane), the Workspace + Command Window row
        # below (arch doc §4.6.1 — the third pane occupies the top/main area).
        outer = QSplitter(self)
        outer.setObjectName("scriptingOuterSplitter")
        outer.setOrientation(Qt.Orientation.Vertical)
        outer.addWidget(self._editor)
        outer.addWidget(bottom)
        outer.setStretchFactor(0, 3)
        outer.setStretchFactor(1, 2)
        self.setCentralWidget(outer)
        self._outer_splitter = outer

        self._build_menu_and_toolbar()

        # The Workspace tracks the command namespace: refresh it after each executed command
        # (a typed command *and* an Editor Run both emit commandExecuted).
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

    @property
    def editor(self) -> ScriptEditor:
        """The multi-tab script Editor (Pass 2)."""
        return self._editor

    def action(self, key: str) -> QAction:
        """Return the Editor menu :class:`QAction` registered under *key* (e.g. ``"file.run"``)."""
        return self._actions[key]

    # -- menu / toolbar -----------------------------------------------------

    def _build_menu_and_toolbar(self) -> None:
        """Build the File / Run menus + a toolbar sharing the same actions (arch doc §4.6.1).

        Mirrors the main window's File pattern (New / Open / Open Recent / Save / Save As) but
        over plain ``.py`` text. **Run** (F5 / ⌘⏎) and **Run Selection** are the MATLAB core —
        the toolbar Run button is the safe primary affordance; the shortcuts are conveniences on
        this separate top-level window (its own F5 does not collide with the main window's
        Evaluate, which only fires when the main window has focus).
        """
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        self._add_action(
            file_menu, "file.new", "New Script", self._on_new, shortcut=QKeySequence.StandardKey.New
        )
        self._add_action(
            file_menu,
            "file.open",
            "Open Script…",
            self._on_open,
            shortcut=QKeySequence.StandardKey.Open,
        )
        self._recent_menu = file_menu.addMenu("Open Recent")
        file_menu.addSeparator()
        self._add_action(
            file_menu,
            "file.save",
            "Save",
            self._on_save,
            shortcut=QKeySequence.StandardKey.Save,
        )
        self._add_action(
            file_menu,
            "file.save_as",
            "Save As…",
            self._on_save_as,
            shortcut=QKeySequence.StandardKey.SaveAs,
        )

        run_menu = bar.addMenu("&Run")
        run_action = self._add_action(run_menu, "file.run", "Run", self._on_run)
        # F5 and Ctrl/⌘+Return both run the active script (a toolbar button is the primary).
        run_action.setShortcuts([QKeySequence("F5"), QKeySequence("Ctrl+Return")])
        sel_action = self._add_action(
            run_menu, "file.run_selection", "Run Selection", self._on_run_selection
        )
        sel_action.setShortcut(QKeySequence("Ctrl+Shift+Return"))

        # A toolbar with the discoverable primaries (the Run button is the safe primary).
        toolbar = self.addToolBar("Script")
        toolbar.setObjectName("scriptToolbar")
        toolbar.setMovable(False)
        for key in ("file.new", "file.open", "file.save", "file.run", "file.run_selection"):
            toolbar.addAction(self._actions[key])
        self._toolbar = toolbar

        self._rebuild_recent_menu()

    def _add_action(
        self,
        menu: QMenu,
        key: str,
        text: str,
        slot: Any,
        *,
        shortcut: QKeySequence.StandardKey | QKeySequence | str | None = None,
    ) -> QAction:
        """Create, register, connect, and add an Editor action to *menu*."""
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        self._actions[key] = action
        return action

    def _rebuild_recent_menu(self) -> None:
        """Repopulate File → Open Recent from the persisted recent-scripts list."""
        self._recent_menu.clear()
        recent = self._settings.recent_scripts()
        self._recent_menu.setEnabled(bool(recent))
        for entry in recent:
            action = self._recent_menu.addAction(entry)
            action.triggered.connect(lambda _checked=False, p=entry: self._open_path(p))

    # -- file ops (plain .py text — NOT Sensor.load) ------------------------

    def _on_new(self) -> None:
        """File → New: open a fresh blank *untitled* script tab."""
        self._editor.new_tab()

    def _on_open(self) -> None:
        """File → Open: pick a ``.py`` file and load it into a new tab."""
        start_dir = self._recent_dir()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Python script", start_dir, _SCRIPT_FILTER
        )
        if filename:
            self._open_path(filename)

    def _open_path(self, path: str) -> ScriptTab | None:
        """Read *path* as text and open it in a new tab; record it in the recent list.

        A missing/unreadable file (or a non-text file) surfaces the traceback dialog and leaves
        the open tabs untouched — never a blank or half-swapped Editor (Rules 15/17). Plain file
        I/O only: scripts are ``.py`` source, not RADIANT configs, so this never touches
        ``Sensor.load``.
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            exec_dialog(UnexpectedErrorDialog(exc, f"Opening {p.name}", self))
            return None
        tab = self._editor.add_file_tab(p, text)
        self._settings.add_recent_script(str(p))
        self._rebuild_recent_menu()
        return tab

    def _on_save(self) -> None:
        """File → Save: write the active tab to its file, or Save As if it has none yet."""
        tab = self._editor.current_tab()
        if tab is None:
            return
        if tab.path is None:
            self._on_save_as()
        else:
            self._save_tab_to(tab, tab.path)

    def _on_save_as(self) -> None:
        """File → Save As: pick a destination for the active tab and write it."""
        tab = self._editor.current_tab()
        if tab is None:
            return
        start = str(tab.path) if tab.path is not None else self._recent_dir()
        filename, _ = QFileDialog.getSaveFileName(self, "Save Python script", start, _SCRIPT_FILTER)
        if filename:
            self._save_tab_to(tab, Path(filename))

    def _save_tab_to(self, tab: ScriptTab, path: Path) -> None:
        """Write *tab*'s text to *path*; on success adopt it, clear the ``*``, record it.

        A write failure surfaces the traceback dialog and leaves the tab's dirty state as-is
        (Rules 15/17). Plain ``.py`` text — no serializer.
        """
        try:
            path.write_text(tab.toPlainText(), encoding="utf-8")
        except OSError as exc:
            exec_dialog(UnexpectedErrorDialog(exc, f"Saving {path.name}", self))
            return
        tab.mark_saved(path)
        self._editor.refresh_tab_title(tab)
        self._settings.add_recent_script(str(path))
        self._rebuild_recent_menu()

    def _recent_dir(self) -> str:
        """The directory of the most-recent script, for the file dialogs' start location."""
        recent = self._settings.recent_scripts()
        return str(Path(recent[0]).parent) if recent else ""

    # -- Run (the MATLAB core — executes in the shared command namespace) ---

    def _on_run(self) -> None:
        """Run the active tab's full script in the Command Window's shared namespace.

        Routes through the Command Window's :meth:`ScriptingConsole.run_script`, so the script
        runs in the *same* namespace the command line and Workspace share (a top-level
        assignment lands in the Workspace), output/errors go to the Command Window transcript,
        and a ``sensor.set(...)`` marks the main GUI stale — all reusing the one execution path.
        """
        tab = self._editor.current_tab()
        if tab is None:
            return
        self._console.run_script(tab.toPlainText(), label=tab.display_name)

    def _on_run_selection(self) -> None:
        """Run only the active tab's selected lines (falls back to the whole tab if none)."""
        tab = self._editor.current_tab()
        if tab is None:
            return
        cursor = tab.textCursor()
        if not cursor.hasSelection():
            self._on_run()
            return
        # QTextCursor.selectedText uses U+2029 (paragraph separator) for line breaks; restore
        # real newlines so the selection compiles as ordinary source.
        selection = cursor.selectedText().replace(" ", "\n")
        self._console.run_script(selection, label=f"{tab.display_name} (selection)")

    # -- workspace refresh --------------------------------------------------

    def refresh_workspace(self) -> None:
        """Rebuild the Workspace from the console's live namespace.

        Called at construction, after each executed command / Editor Run, and by the main window
        after an evaluate/refresh (when ``result`` is re-bound outside a command).
        """
        self._workspace.refresh(self._console.namespace_variables())

    def _on_command_executed(self, _source: str) -> None:
        self.refresh_workspace()

    # -- theme --------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Re-apply the Editor's syntax-highlight colours for *theme* (the app light/dark toggle).

        The window's chrome (backgrounds, borders, the Workspace/Command Window panes) re-themes
        through the app-wide QSS automatically; only the Editor's ``QSyntaxHighlighter`` glyph
        colours are outside QSS's reach, so the main window's View → Dark/Light toggle calls this
        to keep the Editor in step.
        """
        self._editor.set_theme(theme)

    # -- window management --------------------------------------------------

    def show_and_raise(self) -> None:
        """Show the window, bring it front-most, and focus the Editor.

        Idempotent: re-invoking on an already-open window raises/focuses the *same* instance
        rather than spawning a duplicate (the main window keeps the single reference).
        """
        self.show()
        self.raise_()
        self.activateWindow()
        tab = self._editor.current_tab()
        if tab is not None:
            tab.setFocus()

    # -- teardown -----------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # noqa: N802 (Qt override)
        """Close the hosted console (which closes any pop-out figure windows) on teardown.

        The window is hidden-not-destroyed on a user close (no ``WA_DeleteOnClose``), so it
        can be reopened; a real teardown (app exit) still tidies the console's figure windows.
        """
        self._console.close()
        super().closeEvent(event)


__all__ = ["ScriptingWindow"]
