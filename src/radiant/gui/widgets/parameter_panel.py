"""The parameter dock's contents: filter box + empty parameter tree (§4.3).

:class:`ParameterPanel` is the body of the left "Parameters" dock: a disabled filter
box (mockup ``.search``) above an empty two-column tree (Parameter / Value). GUI plan
Phase 1 ships it static — the tree is empty and the filter is disabled — because the
tree is built *entirely* from ``Sensor.parameter_defs()`` in Phase 2 (never transcribed,
Gap 70). This file provides the styled skeleton Phase 2 populates.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLineEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

# The two columns the mockup's parameter tree shows (§4.3). Value carries the unit
# suffix from the schema in Phase 2 (R-UNITS); Phase 1 leaves the tree empty.
_COLUMNS: tuple[str, ...] = ("Parameter", "Value")


class ParameterPanel(QWidget):
    """Filter box + empty Parameter/Value tree (Phase 1 shell).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("parameterPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("parameterSearch")
        self._filter.setPlaceholderText("Filter parameters…")
        # Disabled until Phase 2 has a tree to filter.
        self._filter.setEnabled(False)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("parameterTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)

        layout.addWidget(self._filter)
        layout.addWidget(self._tree, 1)

    @property
    def filter_box(self) -> QLineEdit:
        """The parameter filter box (disabled in Phase 1)."""
        return self._filter

    @property
    def tree(self) -> QTreeWidget:
        """The empty Parameter/Value tree (Phase 2 fills it from the schema)."""
        return self._tree
