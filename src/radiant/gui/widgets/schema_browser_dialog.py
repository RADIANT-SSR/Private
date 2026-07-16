"""Modal browser over the live parameter schema (Tools → Parameter Schema Browser).

:class:`SchemaBrowserDialog` renders every :class:`~radiant.core.parameters.ParameterDef`
from the public ``Sensor.parameter_defs()`` introspection surface (Gap 70) as a
namespace-grouped tree: name, dtype, input unit, default, bounds/choices, and the
description as a tooltip + detail row. It is a **read-only** view — editing stays with
the All-Parameters tree and the per-stage Inputs forms; this dialog answers "what
parameters exist, in what units, with what defaults" without leaving the app (GUI
Capability Expansion plan GX-1; the schema is never transcribed — the dialog reads the
live registry).

One widget class per file (Rule 19). Styling entirely from the design-system QSS via
object names; no colour/font literal here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_HEADERS = ("Parameter", "Type", "Unit", "Default", "Bounds / choices")


class SchemaBrowserDialog(QDialog):
    """Read-only, filterable tree of the full parameter schema (Gap 70 surface)."""

    def __init__(self, sensor: Sensor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("schemaBrowserDialog")
        self.setWindowTitle("Parameter Schema Browser")
        self.resize(820, 560)

        layout = QVBoxLayout(self)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("schemaFilterEdit")
        self._filter.setPlaceholderText("Filter parameters… (name or description)")
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("schemaTree")
        self._tree.setColumnCount(len(_HEADERS))
        self._tree.setHeaderLabels(list(_HEADERS))
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._populate(sensor)

    def _populate(self, sensor: Sensor) -> None:
        """Fill the tree from the live schema, grouped by top-level namespace."""
        groups: dict[str, QTreeWidgetItem] = {}
        for name, pdef in sorted(sensor.parameter_defs().items()):
            namespace = name.split(".")[0]
            group = groups.get(namespace)
            if group is None:
                group = QTreeWidgetItem(self._tree, [namespace])
                group.setFirstColumnSpanned(True)
                groups[namespace] = group

            if pdef.enum_values:
                constraint = " | ".join(pdef.enum_values)
            elif pdef.bounds is not None:
                constraint = f"[{pdef.bounds[0]:g}, {pdef.bounds[1]:g}]"
            else:
                constraint = ""
            default = "" if pdef.default is None else str(pdef.default)
            item = QTreeWidgetItem(
                group,
                [name, pdef.dtype.__name__, pdef.input_unit, default, constraint],
            )
            # The description rides as tooltip on every column (R-UNITS text included).
            for col in range(len(_HEADERS)):
                item.setToolTip(col, pdef.description)
            item.setData(0, Qt.ItemDataRole.UserRole, pdef.description.lower())
        self._tree.expandAll()
        for col in range(len(_HEADERS) - 1):
            self._tree.resizeColumnToContents(col)

    def _apply_filter(self, text: str) -> None:
        """Show only rows whose name or description contains *text* (case-insensitive)."""
        needle = text.strip().lower()
        for g in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(g)
            any_visible = False
            for i in range(group.childCount()):
                item = group.child(i)
                description = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
                match = not needle or needle in item.text(0).lower() or needle in description
                item.setHidden(not match)
                any_visible = any_visible or match
            group.setHidden(not any_visible)

    @property
    def tree(self) -> QTreeWidget:
        """The schema tree (tests)."""
        return self._tree

    @property
    def filter_edit(self) -> QLineEdit:
        """The filter box (tests)."""
        return self._filter


__all__ = ["SchemaBrowserDialog"]
