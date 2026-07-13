"""The parameter dock's contents: filter box + schema-driven parameter tree (§4.3).

:class:`ParameterPanel` is the body of the left "Parameters" dock. It builds a
three-column tree — Parameter / Value / Source — **entirely** from
``Sensor.parameter_defs()`` (never a transcribed list, Gap 70), grouped by dot-path
namespace in chain order (geometry first). Each row shows the resolved value with its
schema unit suffix (R-UNITS); derived parameters carry the ⚡ marker; the Source column
shows the provenance (user-set / config / default / derived) sourced from the resolved
set via the public :meth:`Sensor.explain` surface (see
:mod:`radiant.gui.param_format`). A live filter box narrows rows by substring across
full dot-paths.

GUI plan Phase 2 **Task A** ships this read-only: rows cannot be edited, there are no
delegates, and no ``sensor.set`` is called. Editing, inline error rendering, and the
right-click menu are Task B. Styling comes entirely from the design-system QSS theme;
this module sets structure, object names, and text only (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.param_format import (
    DERIVED_BADGE,
    format_value,
    group_by_namespace,
    is_derived,
    ordered_namespaces,
    provenance_from_explain,
    provenance_label,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The three columns of the read-only parameter tree (§4.3): the leaf parameter
# name, its value + unit suffix, and its provenance ("Source").
_COLUMNS: tuple[str, ...] = ("Parameter", "Value", "Source")

# Qt item-data role carrying each leaf row's full dot-path (for filtering and the
# both-directions schema-match test). UserRole is the first app-defined role.
_DOTPATH_ROLE = int(Qt.ItemDataRole.UserRole)

_EMPTY_MESSAGE = "No configuration loaded — open a YAML to inspect parameters"

# Compact fixed widths (px, layout geometry — not design tokens) for the Value and
# Source columns, so the stretchy Parameter column keeps the most room in the dock.
_VALUE_COL_WIDTH = 96
_SOURCE_COL_WIDTH = 68


class ParameterPanel(QWidget):
    """Filter box + schema-driven Parameter/Value/Source tree (read-only, Task A).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("parameterPanel")

        # dot-path -> leaf QTreeWidgetItem, for filtering and test introspection.
        self._items: dict[str, QTreeWidgetItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("parameterSearch")
        self._filter.setPlaceholderText("Filter parameters…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("parameterTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        # Give the (often long) parameter names the stretch space; keep the Value
        # and Source columns compact so, in the narrow dock, names truncate last.
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._tree.setColumnWidth(1, _VALUE_COL_WIDTH)
        self._tree.setColumnWidth(2, _SOURCE_COL_WIDTH)

        self._empty_msg = QLabel(_EMPTY_MESSAGE, self)
        self._empty_msg.setObjectName("parameterEmptyMsg")
        self._empty_msg.setWordWrap(True)
        self._empty_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._filter)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._empty_msg, 1)

        # A freshly constructed panel carries no sensor: show the empty state.
        self._show_empty_state()

    # -- public accessors ---------------------------------------------------

    @property
    def filter_box(self) -> QLineEdit:
        """The live parameter filter box (substring match across dot-paths)."""
        return self._filter

    @property
    def tree(self) -> QTreeWidget:
        """The Parameter/Value/Source tree built from the schema."""
        return self._tree

    def row_dotpaths(self) -> set[str]:
        """Every parameter dot-path currently rendered as a tree row."""
        return set(self._items)

    def value_text(self, dotpath: str) -> str:
        """The Value-column text (value + unit, ⚡ prefix if derived) for a row."""
        return self._items[dotpath].text(1)

    def source_text(self, dotpath: str) -> str:
        """The Source-column (provenance label) text for a row."""
        return self._items[dotpath].text(2)

    def visible_dotpaths(self) -> set[str]:
        """Dot-paths of the rows currently visible (not filtered out)."""
        return {dotpath for dotpath, item in self._items.items() if not item.isHidden()}

    # -- population ---------------------------------------------------------

    def populate(self, sensor: Sensor | None) -> None:
        """(Re)build the tree from *sensor*'s schema, or show the empty state.

        With a resolvable ``Sensor`` (the ``radiant gui CONFIG.yaml`` path) the
        tree fills from ``sensor.parameter_defs()``; ``None`` (a bare launch — a
        default ``Sensor()`` is not resolvable) leaves the themed "no configuration
        loaded" state. Read-only: rows are not editable (Task A).
        """
        self._tree.clear()
        self._items.clear()

        if sensor is None:
            self._show_empty_state()
            return

        defs = sensor.parameter_defs()
        grouped = group_by_namespace(defs)
        for namespace in ordered_namespaces(defs.keys()):
            group_item = QTreeWidgetItem([namespace, "", ""])
            self._tree.addTopLevelItem(group_item)
            for dotpath, pdef in grouped[namespace]:
                child = self._build_row(sensor, dotpath, pdef.input_unit, pdef.description)
                group_item.addChild(child)
                self._items[dotpath] = child
            group_item.setExpanded(True)

        self._show_tree()
        self._apply_filter(self._filter.text())

    def _build_row(
        self,
        sensor: Sensor,
        dotpath: str,
        unit: str,
        description: str,
    ) -> QTreeWidgetItem:
        """One leaf row: value + unit, ⚡-marked and provenance-labelled."""
        provenance = provenance_from_explain(sensor.explain(dotpath))
        value_text = format_value(self._resolved_value(sensor, dotpath), unit)
        if is_derived(provenance):
            value_text = f"{DERIVED_BADGE} {value_text}"

        # Leaf label is the dot-path remainder after the namespace prefix.
        leaf = dotpath.split(".", 1)[1] if "." in dotpath else dotpath
        item = QTreeWidgetItem([leaf, value_text, provenance_label(provenance)])
        item.setData(0, _DOTPATH_ROLE, dotpath)
        item.setToolTip(0, f"{dotpath}\n{description}" if description else dotpath)
        # Read-only (Task A): leave the default non-editable item flags untouched.
        return item

    @staticmethod
    def _resolved_value(sensor: Sensor, dotpath: str) -> object | None:
        """Resolved value in input units, or ``None`` if the parameter is unset.

        A required-unless parameter superseded by an alternative resolves to no
        value; ``Sensor.get_input`` raises ``KeyError`` for it. Rendering that as
        an explicit em-dash (``None`` here) is a visible state, not a swallowed
        error (Rule 17) — the row still appears, marked unresolved.
        """
        try:
            return sensor.get_input(dotpath)
        except KeyError:
            return None

    # -- filtering ----------------------------------------------------------

    def _apply_filter(self, text: str) -> None:
        """Show only rows whose full dot-path contains *text* (case-insensitive).

        A namespace group hides when the query excludes all its children and shows
        (expanded) otherwise; an empty query restores the full tree.
        """
        query = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            visible_children = 0
            for j in range(group.childCount()):
                child = group.child(j)
                dotpath = str(child.data(0, _DOTPATH_ROLE))
                matches = query in dotpath.lower() if query else True
                child.setHidden(not matches)
                visible_children += int(matches)
            group.setHidden(bool(query) and visible_children == 0)
            if query:
                group.setExpanded(True)

    # -- empty / populated state -------------------------------------------

    def _show_empty_state(self) -> None:
        """Show the "no configuration loaded" message; hide + disable the tree."""
        self._tree.setVisible(False)
        self._empty_msg.setVisible(True)
        self._filter.setEnabled(False)

    def _show_tree(self) -> None:
        """Show the populated tree and enable the live filter box."""
        self._empty_msg.setVisible(False)
        self._tree.setVisible(True)
        self._filter.setEnabled(True)
