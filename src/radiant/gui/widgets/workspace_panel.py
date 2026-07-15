"""The Workspace pane: a live variable browser of the command-window namespace.

:class:`WorkspacePanel` is the MATLAB-style **Workspace** of the RADIANT scripting window
(arch doc §4.6.1). It is the read-only companion to the Command Window
(:class:`~radiant.gui.widgets.scripting_console.ScriptingConsole`): a table of every live
variable in the REPL namespace — its **name**, **type**, and a short **value / size
summary** (``sensor: Sensor``, ``result: ChainResult``, ``x: ndarray (500,)``,
``snr: float 616.0``). It refreshes after each command executes and after every
evaluate/refresh, so the operator always sees the live namespace the command line sees.

Selecting a variable shows a fuller **detail** dump below the table — the full
``inspect_result`` tree for a :class:`~radiant.api.ChainResult`, else the value's ``repr``.
This is the Workspace's own inspect surface; it is *related to but distinct from* the global
Inspector tool (§4.6), which dumps one result — the Workspace lists the whole namespace.

All colour/typography comes from the QSS theme (GUI plan §4.9); this file sets object names
only and holds no colour/font/size literal.
"""

from __future__ import annotations

from typing import Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api.inspect import inspect_result

# Namespace keys that are REPL plumbing, not user-facing variables: the module dunders and
# the interpreter's last-value binding. Everything else (the bound `sensor`/`result`/`plot`
# conveniences and any user-created name) is a real workspace variable and is listed.
_HIDDEN_NAMES: Final[frozenset[str]] = frozenset(
    {"__name__", "__builtins__", "__doc__", "__loader__", "__spec__", "__package__", "_"}
)

_HEADER: Final[str] = "Workspace — the live command-window variables"

# The longest string / repr shown inline before it is elided (the detail pane holds the
# full text). Purely a display budget, not a physics quantity.
_MAX_INLINE: Final[int] = 80


def summarize_variable(value: Any) -> tuple[str, str]:
    """Return ``(type_name, value_summary)`` for one workspace variable.

    The summary mirrors a MATLAB workspace row: an array shows its shape (and dtype), a
    scalar its number, a string its (elided) quoted text, a container its length, and a
    generic object an empty value cell (its type already names it). NumPy is duck-typed via
    ``shape``/``dtype`` so this module needs no numpy import (GUI import rules).
    """
    type_name = type(value).__name__
    if value is None:
        return ("NoneType", "None")
    # ndarray-like: a `.shape` tuple (duck-typed to avoid importing numpy in the GUI layer).
    shape = getattr(value, "shape", None)
    if isinstance(shape, tuple):
        dims = ", ".join(str(dim) for dim in shape)
        summary = f"({dims},)" if len(shape) == 1 else f"({dims})"
        dtype = getattr(value, "dtype", None)
        if dtype is not None:
            summary = f"{summary} {dtype}"
        return (type_name, summary)
    if isinstance(value, bool):  # before int — bool is an int subclass
        return (type_name, str(value))
    if isinstance(value, (int, float)):
        return (type_name, repr(value))
    if isinstance(value, str):
        shown = value if len(value) <= _MAX_INLINE else value[: _MAX_INLINE - 1] + "…"
        return (type_name, repr(shown))
    if isinstance(value, (list, tuple, set, dict)):
        return (type_name, f"len {len(value)}")
    return (type_name, "")


class WorkspacePanel(QWidget):
    """A live, read-only variable browser of a REPL namespace (arch doc §4.6.1).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    variableActivated(str):
        A variable row was double-clicked (emitted with the variable name); tests use it.
    """

    variableActivated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workspacePanel")
        self._values: dict[str, Any] = {}
        self._build_ui()

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QLabel(_HEADER, self)
        header.setObjectName("workspaceHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        splitter = QSplitter(self)
        splitter.setObjectName("workspaceSplitter")
        splitter.setOrientation(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        self._tree = QTreeWidget(splitter)
        self._tree.setObjectName("workspaceTree")
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Name", "Type", "Value"])
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._on_current_changed)
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        header_view = self._tree.header()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self._detail = QPlainTextEdit(splitter)
        self._detail.setObjectName("workspaceDetail")
        self._detail.setReadOnly(True)
        self._detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    # -- public accessors (tests) ------------------------------------------

    @property
    def tree(self) -> QTreeWidget:
        """The variable table."""
        return self._tree

    @property
    def detail(self) -> QPlainTextEdit:
        """The read-only detail pane for the selected variable."""
        return self._detail

    def variable_names(self) -> list[str]:
        """The variable names currently listed, top-to-bottom (for tests)."""
        root = self._tree.invisibleRootItem()
        return [root.child(i).text(0) for i in range(root.childCount())]

    def row_text(self, name: str) -> tuple[str, str, str] | None:
        """The ``(name, type, value)`` row for *name*, or ``None`` if not listed (tests)."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == name:
                return (item.text(0), item.text(1), item.text(2))
        return None

    # -- refresh ------------------------------------------------------------

    def refresh(self, namespace: dict[str, Any]) -> None:
        """Rebuild the table from *namespace* (name → value), preserving the selection.

        Called after each command executes and after every evaluate/refresh. REPL plumbing
        (``__name__``, ``__builtins__``, ``_``) is hidden; every other binding is a listed
        variable. Names sort alphabetically so a row does not jump as the namespace grows.
        """
        selected = self._selected_name()
        self._values = {
            name: value for name, value in namespace.items() if name not in _HIDDEN_NAMES
        }
        self._tree.clear()
        for name in sorted(self._values):
            type_name, summary = summarize_variable(self._values[name])
            self._tree.addTopLevelItem(QTreeWidgetItem([name, type_name, summary]))
        self._reselect(selected)

    # -- selection / detail -------------------------------------------------

    def _selected_name(self) -> str | None:
        item = self._tree.currentItem()
        return item.text(0) if item is not None else None

    def _reselect(self, name: str | None) -> None:
        """Restore selection on *name* after a rebuild (else clear the detail pane)."""
        if name is None:
            self._detail.clear()
            return
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == name:
                self._tree.setCurrentItem(item)
                return
        self._detail.clear()

    def _on_current_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        """Show the selected variable's detail dump (inspect tree or repr)."""
        if current is None:
            self._detail.clear()
            return
        self._detail.setPlainText(self._detail_text(current.text(0)))

    def _on_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        self.variableActivated.emit(item.text(0))

    def _detail_text(self, name: str) -> str:
        """The detail text for *name*: the full inspect tree for a result, else its repr."""
        if name not in self._values:
            return ""
        value = self._values[name]
        if type(value).__name__ == "ChainResult":
            return inspect_result(value)
        return repr(value)


__all__ = ["WorkspacePanel", "summarize_variable"]
