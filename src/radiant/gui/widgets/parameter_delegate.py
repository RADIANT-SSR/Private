"""The parameter-tree edit delegate: the right editor per :class:`ParameterDef` dtype.

:class:`ParameterEditDelegate` is the Value-column delegate for the schema-driven
parameter tree (arch doc §4.3, GUI plan Phase 2 Task B). It opens the editor the
parameter's schema calls for — a combo box for an enum (choices read from
``ParameterDef.enum_values``, never hardcoded), a checkbox for a bool, a spin box for
an int, a line edit for a float or free string — and, on commit, hands the raw value
to the owning panel through a single callback (which calls ``sensor.set`` — one API
call per edit, §4.1). It never writes the value into the model itself: the panel
re-reads the sensor and refreshes the row, so a rejected value cannot leak into the
display.

The delegate also paints a themed error tint on any row the panel has flagged as
rejected (the ``ERROR_ROLE`` item-data flag), reading the colour from the active theme
so no colour literal lives in this file (GUI plan §4.9).

One widget class per file (Rule 19): the dialogs this flow raises live in their own
modules (:mod:`~radiant.gui.widgets.actionable_error_dialog`,
:mod:`~radiant.gui.widgets.unexpected_error_dialog`,
:mod:`~radiant.gui.widgets.explain_dialog`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from radiant.core.parameters import ParameterDef
from radiant.gui.themes import active_theme

# Item-data role (column 0) carrying each leaf row's full dot-path. Must match
# ``parameter_panel._DOTPATH_ROLE`` — the delegate reads it to find the schema
# entry for the row being edited.
DOTPATH_ROLE = int(Qt.ItemDataRole.UserRole)

# Item-data role (column 1) the panel sets to ``True`` on a row whose last edit was
# rejected, so this delegate tints it with the themed error colour.
ERROR_ROLE = int(Qt.ItemDataRole.UserRole) + 1

# Bounds are numeric; a QSpinBox needs int limits. Fall back to these when the
# schema declares no bounds for an int parameter (layout geometry, not a design
# token).
_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1


class ParameterEditDelegate(QStyledItemDelegate):
    """Value-column editor for the schema-driven parameter tree (§4.3, Task B).

    Parameters
    ----------
    pdef_for:
        ``dotpath -> ParameterDef`` — the schema entry for a row, used to choose
        the editor and (for enums) its choices.
    input_value_for:
        ``dotpath -> value`` — the row's current resolved value in input units, or
        ``None`` if unresolved; seeds the editor.
    commit:
        ``(dotpath, value) -> None`` — the panel's commit handler, invoked once per
        edit. It owns the ``sensor.set`` call, validation, and row refresh.
    parent:
        The owning widget (the tree), if any.
    """

    def __init__(
        self,
        pdef_for: Callable[[str], ParameterDef],
        input_value_for: Callable[[str], Any],
        commit: Callable[[str, Any], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pdef_for = pdef_for
        self._input_value_for = input_value_for
        self._commit = commit

    # -- editor lifecycle ---------------------------------------------------

    def createEditor(  # noqa: N802 (Qt override name)
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QWidget:
        """Build the editor the parameter's dtype/enum calls for."""
        pdef = self._pdef_for(self._dotpath(index))
        if pdef.enum_values is not None:
            combo = QComboBox(parent)
            combo.addItems(list(pdef.enum_values))  # choices are schema-sourced
            return combo
        if pdef.dtype is bool:
            return QCheckBox(parent)
        if pdef.dtype is int:
            spin = QSpinBox(parent)
            if pdef.bounds is not None:
                lo, hi = pdef.bounds
                spin.setRange(int(lo), int(hi))
            else:
                spin.setRange(_INT_MIN, _INT_MAX)
            return spin
        # float or free string: a line edit. Bounds/type validation is the API's
        # job (surfaced on commit), so the editor stays permissive.
        return QLineEdit(parent)

    def setEditorData(  # noqa: N802 (Qt override name)
        self,
        editor: QWidget,
        index: QModelIndex,
    ) -> None:
        """Seed *editor* with the row's current input value (not the display text)."""
        value = self._input_value_for(self._dotpath(index))
        if isinstance(editor, QComboBox):
            pos = editor.findText("" if value is None else str(value))
            editor.setCurrentIndex(max(pos, 0))
        elif isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(value) if value is not None else 0)
        elif isinstance(editor, QLineEdit):
            editor.setText("" if value is None else str(value))

    def setModelData(  # noqa: N802 (Qt override name)
        self,
        editor: QWidget,
        model: Any,
        index: QModelIndex,
    ) -> None:
        """Hand the edited value to the panel's commit handler (one ``sensor.set``).

        The value is deliberately **not** written into the model here: the panel
        commits it to the sensor, and — only if accepted — refreshes the row from
        the resolved set. A rejected value therefore never reaches the display.
        """
        self._commit(self._dotpath(index), self._editor_value(editor))

    # -- error-row tint -----------------------------------------------------

    def initStyleOption(  # noqa: N802 (Qt override name)
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Tint a rejected row with the themed error colours (tokens, not literals)."""
        super().initStyleOption(option, index)
        if bool(index.data(ERROR_ROLE)):
            theme = active_theme()
            option.backgroundBrush = QColor(theme.err_soft)
            option.palette.setColor(option.palette.ColorRole.Text, QColor(theme.err))

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _dotpath(index: QModelIndex) -> str:
        """The full dot-path stored on the row (column 0 carries ``DOTPATH_ROLE``)."""
        return str(index.sibling(index.row(), 0).data(DOTPATH_ROLE))

    @staticmethod
    def _editor_value(editor: QWidget) -> Any:
        """Extract the native Python value from an editor widget."""
        if isinstance(editor, QComboBox):
            return editor.currentText()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QSpinBox):
            return editor.value()
        if isinstance(editor, QLineEdit):
            return editor.text()
        return None


__all__ = ["ParameterEditDelegate", "DOTPATH_ROLE", "ERROR_ROLE"]
