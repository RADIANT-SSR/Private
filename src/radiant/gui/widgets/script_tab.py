"""One editable Python-script tab for the multi-tab Editor (arch doc §4.6.1, Pass 2).

:class:`ScriptTab` is the code pane of a single Editor tab — a mono-font
:class:`~PySide6.QtWidgets.QPlainTextEdit` that tracks the file it came from (``None`` for an
unsaved *untitled* buffer) and whether it carries unsaved edits (its **dirty** marker). The
owning :class:`~radiant.gui.widgets.script_editor.ScriptEditor` shows the tab's
:meth:`tab_title` (file name + a trailing ``*`` when dirty) on the tab and reacts to
:attr:`dirtyChanged` to keep that label live.

The tab owns a :class:`~radiant.gui.widgets.python_highlighter.PythonHighlighter` so the source
is coloured from the active theme; :meth:`set_theme` re-applies it on a light/dark toggle. One
widget class per file (Rule 19); all colour/typography comes from the QSS theme via the
``scriptEditorArea`` object name (GUI plan §4.9) — this module holds no visual literal.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from radiant.gui.themes import Theme
from radiant.gui.widgets.python_highlighter import PythonHighlighter

# The tab label shown for a buffer that has never been saved to a file.
_UNTITLED: str = "untitled"


class ScriptTab(QPlainTextEdit):
    """A single script buffer: mono-font text + a file path + a dirty flag.

    Parameters
    ----------
    path:
        The file this tab was opened from, or ``None`` for a fresh *untitled* buffer.
    text:
        The initial contents (empty for a New tab; the file's text for an Open).
    theme:
        The theme to colour the source in (``None`` → the active theme).
    parent:
        The owning widget, if any.

    Signals
    -------
    dirtyChanged(bool):
        The unsaved-edits state changed (the Editor updates the tab's ``*`` marker).
    """

    dirtyChanged = Signal(bool)

    def __init__(
        self,
        path: Path | None = None,
        text: str = "",
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("scriptEditorArea")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # A real code pane uses spaces-for-tab and a modest tab width; the visual size comes
        # from the mono font the QSS installs, so this is a behaviour setting, not a style one.
        self.setTabChangesFocus(False)

        self._path: Path | None = path
        self._dirty: bool = False
        # Guard so programmatic (re)loads of the buffer text do not flip the dirty flag — only
        # a user edit does. Set while we call setPlainText ourselves.
        self._loading: bool = False

        self._highlighter = PythonHighlighter(self.document(), theme)

        self.set_text(text)
        self.textChanged.connect(self._on_text_changed)

    # -- text / dirty -------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Replace the buffer contents without marking the tab dirty (a load, not an edit)."""
        self._loading = True
        try:
            self.setPlainText(text)
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_text_changed(self) -> None:
        if not self._loading:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirtyChanged.emit(dirty)

    @property
    def is_dirty(self) -> bool:
        """True when the buffer carries edits not yet written to its file."""
        return self._dirty

    # -- file identity ------------------------------------------------------

    @property
    def path(self) -> Path | None:
        """The file this tab is bound to, or ``None`` for an unsaved *untitled* buffer."""
        return self._path

    @property
    def display_name(self) -> str:
        """The base file name (or ``untitled``) — the un-marked tab label."""
        return self._path.name if self._path is not None else _UNTITLED

    def tab_title(self) -> str:
        """The tab label: the display name with a leading ``*`` when there are unsaved edits."""
        return f"*{self.display_name}" if self._dirty else self.display_name

    def mark_saved(self, path: Path) -> None:
        """Record that the buffer was just written to *path*: adopt it and clear the dirty flag."""
        self._path = path
        self._set_dirty(False)

    # -- theme --------------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Re-colour the source for *theme* (the app light/dark toggle re-applies it)."""
        self._highlighter.set_theme(theme)


__all__ = ["ScriptTab"]
