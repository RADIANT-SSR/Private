"""The multi-tab Python script Editor pane (arch doc §4.6.1, Pass 2 — the third pane).

:class:`ScriptEditor` is the MATLAB-style **Editor** of the RADIANT scripting window: a
:class:`~PySide6.QtWidgets.QTabWidget` of open script buffers
(:class:`~radiant.gui.widgets.script_tab.ScriptTab`), each an editable mono-font code pane that
knows its file and its unsaved-edits (dirty) state. Several scripts can be open at once; each
tab shows its file name and a trailing ``*`` while dirty, and a close affordance removes it (the
Editor always keeps at least one tab so the pane is never empty).

The Editor owns **only** the tabs and their text. The orchestration — the File/Run menu, the
Open/Save dialogs, the persisted recent-scripts list, and executing a tab into the shared
command namespace — lives in the host
:class:`~radiant.gui.widgets.scripting_window.ScriptingWindow`,
which drives this widget's small API (:meth:`new_tab`, :meth:`add_file_tab`,
:meth:`current_tab`, :meth:`tabs`). Keeping the run/coherence path in the window means the
Editor's Run reuses the Command Window's execution primitive verbatim (one shared namespace),
never a second interpreter.

One widget class per file (Rule 19); all colour/typography comes from the QSS theme via the
``scriptEditor`` / ``scriptEditorTabs`` object names (GUI plan §4.9) — no visual literal here.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QTabWidget, QVBoxLayout, QWidget

from radiant.gui.themes import Theme, active_theme
from radiant.gui.widgets.script_tab import ScriptTab


class ScriptEditor(QWidget):
    """A tabbed, multi-buffer Python script editor (the scripting window's top pane).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    dirtyStateChanged():
        Any tab's dirty state changed (the window may reflect it in a title / status).
    """

    dirtyStateChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptEditor")
        self._theme: Theme = active_theme()
        self._build_ui()
        # Open on a single blank buffer so the pane is a usable editor from the first frame.
        self.new_tab()

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("scriptEditorTabs")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._on_close_requested)
        layout.addWidget(self._tabs)

    # -- public accessors ---------------------------------------------------

    @property
    def tab_widget(self) -> QTabWidget:
        """The underlying :class:`QTabWidget` (for tests / focus management)."""
        return self._tabs

    def tabs(self) -> list[ScriptTab]:
        """Every open script tab, left-to-right."""
        return [self._tab_at(i) for i in range(self._tabs.count())]

    def current_tab(self) -> ScriptTab | None:
        """The active script tab, or ``None`` if (transiently) none is open."""
        widget = self._tabs.currentWidget()
        return widget if isinstance(widget, ScriptTab) else None

    def tab_titles(self) -> list[str]:
        """The visible tab labels, left-to-right (for tests)."""
        return [self._tabs.tabText(i) for i in range(self._tabs.count())]

    # -- tab lifecycle ------------------------------------------------------

    def new_tab(self) -> ScriptTab:
        """Open a fresh blank *untitled* buffer, focus it, and return it (File → New)."""
        return self._add_tab(ScriptTab(None, "", self._theme, self))

    def add_file_tab(self, path: Path, text: str) -> ScriptTab:
        """Open *text* (already read from *path*) in a new tab and return it (File → Open).

        If *path* is already open, its existing tab is re-selected rather than duplicated (its
        buffer is left as-is — reopening does not clobber unsaved edits).
        """
        existing = self._tab_for_path(path)
        if existing is not None:
            self._tabs.setCurrentWidget(existing)
            return existing
        return self._add_tab(ScriptTab(path, text, self._theme, self))

    def _add_tab(self, tab: ScriptTab) -> ScriptTab:
        """Wire a freshly-built *tab* into the widget, select it, and return it."""
        index = self._tabs.addTab(tab, tab.tab_title())
        tab.dirtyChanged.connect(lambda _dirty, t=tab: self._on_tab_dirty(t))
        self._tabs.setCurrentIndex(index)
        tab.setFocus()
        return tab

    def refresh_tab_title(self, tab: ScriptTab) -> None:
        """Re-read *tab*'s label onto its tab (after a Save renames / clears the ``*``)."""
        index = self._tabs.indexOf(tab)
        if index >= 0:
            self._tabs.setTabText(index, tab.tab_title())

    def _on_tab_dirty(self, tab: ScriptTab) -> None:
        self.refresh_tab_title(tab)
        self.dirtyStateChanged.emit()

    def _on_close_requested(self, index: int) -> None:
        """Close the tab at *index*, keeping at least one buffer open.

        Closing a *dirty* tab asks Discard / Cancel first (CU-144) — the tab's own
        Save routes through the window's File → Save, so this guard only prevents
        silent loss. If the last tab is closed, a fresh blank buffer takes its
        place so the Editor is never empty.
        """
        widget = self._tabs.widget(index)
        if isinstance(widget, ScriptTab) and widget.is_dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved script",
                f"'{widget.tab_title().lstrip('* ')}' has unsaved edits — discard them?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                return
        self._tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        if self._tabs.count() == 0:
            self.new_tab()

    # -- theme --------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Re-colour every open tab's source for *theme* (the app light/dark toggle)."""
        self._theme = theme
        for tab in self.tabs():
            tab.set_theme(theme)

    # -- helpers ------------------------------------------------------------

    def _tab_at(self, index: int) -> ScriptTab:
        widget = self._tabs.widget(index)
        assert isinstance(widget, ScriptTab)  # every page is a ScriptTab by construction
        return widget

    def _tab_for_path(self, path: Path) -> ScriptTab | None:
        """The open tab bound to *path* (resolved), or ``None`` if not open."""
        target = self._resolve(path)
        for tab in self.tabs():
            if tab.path is not None and self._resolve(tab.path) == target:
                return tab
        return None

    @staticmethod
    def _resolve(path: Path) -> Path:
        """A best-effort absolute form of *path* for open-tab identity (never raises)."""
        try:
            return path.resolve()
        except OSError:
            return path.absolute()


__all__ = ["ScriptEditor"]
