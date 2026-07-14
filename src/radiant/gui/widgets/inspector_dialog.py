"""The global Inspector tool: the full ``result.inspect()`` variable dump (arch doc §4.6).

:class:`InspectorDialog` is the contextual-layout **global Inspector** — the old Variable
Explorer detail tab promoted to a menu/toolbar tool (arch doc §4.6 / §4.7). It renders the
public ChainResult inspection surface — :func:`radiant.api.inspect.inspect_result` — as a
**collapsible** themed tree, one node per line of the inspector's output (metrics, noise
terms, MTF terms, frames, and every stage's outputs). The inspector already joins each
value with the unit its surface carries (e.g. a noise term reads ``… e- RMS``), so the tree
shows units wherever the surface provides them (R-UNITS) without the GUI inventing any.

It is a **non-modal** dialog (the operator can leave it open and keep working); the main
window disables the Inspector action until the first result exists (nothing to dump).

**Inspect surface (Gap 87).** Arch doc §4.6 names ``result.inspect()``, but ChainResult
carries no such convenience method; the public inspection surface is the module-level
:func:`radiant.api.inspect.inspect_result`. The GUI calls that one public function and
re-renders its indented text as a real tree — one GUI action ↔ one API call (GUI plan
§4.1), no recomputation and no stage-internal reach. The missing ChainResult convenience
accessor (``result.inspect()``) is tracked as **Gap 87**.

All colour/typography comes from the QSS theme (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api.inspect import inspect_result

if TYPE_CHECKING:
    from radiant.api import ChainResult

_HEADER: Final[str] = "Inspector — every intermediate value across the whole chain"

# The two box-drawing branch connectors the inspector emits, each 4 characters wide, and
# the 4-character indent group that precedes each nesting level ("│   " or "    ").
_BRANCHES: Final[tuple[str, ...]] = ("├── ", "└── ")
_GROUP_WIDTH: Final[int] = 4


def parse_inspect_tree(text: str) -> list[tuple[int, str]]:
    """Parse an :func:`inspect_result` string into ``(depth, label)`` rows.

    Each inspector line is either the un-prefixed root (``ChainResult``, depth 0) or a
    branch line ``<indent groups>├──/└── <label>``. The depth is the number of
    4-character indent groups before the branch connector; the label is the text after
    it. Blank lines are skipped.

    A no-connector line *after* the root is a **continuation** of the previous node's
    value — the inspector prints a multi-line NumPy array repr as wrapped continuation
    lines (CU-113). Those are folded onto the preceding node's label rather than becoming
    spurious top-level nodes, so the tree stays structural. Being pure text, this is
    unit-tested without a widget.
    """
    rows: list[list] = []  # [depth, label] — label is mutated for continuations
    for line in text.splitlines():
        if not line.strip():
            continue
        index = -1
        for branch in _BRANCHES:
            index = line.find(branch)
            if index != -1:
                break
        if index == -1:
            if not rows:
                # The un-prefixed root line (e.g. "ChainResult").
                rows.append([0, line.rstrip()])
            else:
                # A wrapped continuation of the previous node's value — fold it in.
                rows[-1][1] = f"{rows[-1][1]} {line.strip()}"
            continue
        depth = index // _GROUP_WIDTH + 1
        label = line[index + len(_BRANCHES[0]) :].rstrip()
        rows.append([depth, label])
    return [(depth, label) for depth, label in rows]


class InspectorDialog(QDialog):
    """Non-modal collapsible tree of ``inspect_result(result)`` (arch doc §4.6).

    Parameters
    ----------
    result:
        The :class:`~radiant.api.ChainResult` to inspect.
    parent:
        The owning widget, if any.
    """

    def __init__(self, result: ChainResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inspectorDialog")
        self.setWindowTitle("Inspector")
        self.setModal(False)
        self.resize(560, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QLabel(_HEADER, self)
        header.setObjectName("inspectorHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("variableTree")
        self._tree.setHeaderHidden(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._populate(result)

    # -- accessors (tests) --------------------------------------------------

    @property
    def tree(self) -> QTreeWidget:
        """The collapsible inspection tree."""
        return self._tree

    def node_count(self) -> int:
        """The total number of tree nodes currently rendered (for tests)."""
        return _count_nodes(self._tree.invisibleRootItem())

    # -- internal -----------------------------------------------------------

    def _populate(self, result: ChainResult) -> None:
        """Render ``inspect_result(result)`` as the collapsible tree."""
        self._tree.clear()
        rows = parse_inspect_tree(inspect_result(result))
        # Build parent chains from the (depth, label) rows: the parent of a row at depth
        # d is the most recent row seen at depth d-1.
        last_at_depth: dict[int, QTreeWidgetItem] = {}
        for depth, label in rows:
            item = QTreeWidgetItem([label])
            parent = last_at_depth.get(depth - 1)
            if depth == 0 or parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            last_at_depth[depth] = item
            for stale in [d for d in last_at_depth if d > depth]:
                del last_at_depth[stale]
        self._tree.expandAll()


def _count_nodes(item: QTreeWidgetItem) -> int:
    """Count *item*'s descendants (excluding the invisible root itself)."""
    total = 0
    for i in range(item.childCount()):
        child = item.child(i)
        total += 1 + _count_nodes(child)
    return total


__all__ = ["InspectorDialog", "parse_inspect_tree"]
