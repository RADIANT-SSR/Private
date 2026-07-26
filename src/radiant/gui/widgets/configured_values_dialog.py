"""The per-parameter all-configurations table editor (ADR-0010 D-2, Phase 4b).

The owner's second half of the "configured parameter" spec: having marked a
parameter as configured, the analyst needs *"a way to set the value for that
parameter for all configurations"*. :class:`ConfiguredValuesDialog` is that compact
table — **one row per configuration**, in set order, each carrying:

* the configuration's stable accent chip (the same
  :attr:`~radiant.gui.themes.tokens.Theme.config_accents` hue, assigned by position,
  that the master selector paints — §4.2b) and its name;
* a value editor built from the parameter's own schema entry (enum → combo, bool →
  check box, int → bounded spin box, float/str → line edit), exactly as the
  single-value :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`
  builds it;
* the parameter's unit, on every row (R-UNITS — no unrendered number anywhere).

**Units.** The table works in the **parameter row's display unit** — whatever unit
the analyst last chose for that dot-path in the Parameter Editor (the session
``ParameterPanel.display_units`` store), falling back to the schema ``input_unit``
when they never chose one. The unit is labelled on every row and the table is
symmetric: what a row displays is what typing into it means, and it is the same unit
the tree shows for the same parameter, so crossing from the tree to the table never
changes the unit under the reader (owner's display-unit rule; CU-211).

The conversion happens **once, at the API boundary**: the whole column still commits
as a single dense ``ConfigurationSet.set_values(..., unit=<display unit>)`` call, so
atomicity is untouched (the API converts and validates every value before replacing
the column) and no unit arithmetic happens in this file (Rule 2). A unit the public
registry cannot soundly convert (an unregistered or offset unit) makes the table fall
back to the schema input unit for every row rather than inventing a conversion.

**Atomicity.** The dialog never half-commits. It hands the whole column to its
``commit`` callback, which makes the single ``set_values`` call; the API validates
every value *before* replacing the column, so a rejected value leaves the set exactly
as it was. The rejection — which names the offending configuration, because the API
raises it that way — renders inline and the dialog stays open (Rules 15/17). Cancel
touches nothing.

One widget class per file (Rule 19). All colour/typography comes from the QSS theme
via the object names below (GUI plan §4.9); the only colour named here is the accent
token tuple read from the active theme.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.param_format import display_in_unit
from radiant.gui.themes import active_theme

if TYPE_CHECKING:
    from radiant.core.parameters import ParameterDef

# Spin-box fallback range when an int parameter declares no bounds (Qt needs one).
_INT_MIN = -2_147_483_648
_INT_MAX = 2_147_483_647

# Accent-chip side in device-independent px — layout geometry, matching the master
# selector's chip so the two surfaces read as one identity system (§4.2b).
_CHIP_PX = 10


class ConfiguredValuesDialog(QDialog):
    """Edit one configured parameter's value in **every** configuration, in one place.

    Parameters
    ----------
    dotpath:
        The configured parameter's dot-path.
    pdef:
        Its schema entry — the single source of the editor kind, bounds, enum
        choices, and unit (never a transcribed list, Gap 70).
    names:
        The configuration names, in set order.
    values:
        The current per-configuration values, in set order and in the parameter's
        input unit (i.e. ``ConfigurationSet.configured()[dotpath]``).
    commit:
        ``(values, unit) -> RadiantError | None`` — called once with the full column
        and the unit those values are expressed in (``None`` when they are already
        in the schema input unit). The host makes the single ``set_values`` API
        call and records the undo command; returning the API's rejection keeps the
        dialog open with the error rendered, returning ``None`` closes it.
    display_unit:
        The unit the analyst chose for this dot-path elsewhere in the window
        (``ParameterPanel.display_unit``). ``None`` — or a unit the registry cannot
        soundly convert — leaves the table in the schema input unit.
    parent:
        The owning widget, if any.
    """

    def __init__(
        self,
        dotpath: str,
        pdef: ParameterDef,
        names: Sequence[str],
        values: Sequence[Any],
        commit: Callable[[list[Any], str | None], RadiantError | None],
        display_unit: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dotpath = dotpath
        self._pdef = pdef
        self._names = list(names)
        self._commit = commit
        self._editors: list[QWidget] = []
        # Incoming values are in the parameter's input unit (what the configured table
        # stores); the rows show and accept the analyst's chosen display unit (CU-211).
        self._unit, row_values = self._in_display_unit(values, display_unit)

        self.setObjectName("configuredValuesDialog")
        self.setWindowTitle(f"Configured values — {dotpath}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        self._build_header(layout)
        self._build_table(layout, row_values)
        self._build_error_area(layout)
        self._build_buttons(layout)

    # -- units --------------------------------------------------------------

    def _in_display_unit(
        self, values: Sequence[Any], display_unit: str | None
    ) -> tuple[str, list[Any]]:
        """The unit this table works in, plus *values* re-expressed in it.

        Conversion routes through the public registry seam
        (:func:`~radiant.gui.param_format.display_in_unit`) — no unit arithmetic
        lives here (Rule 2). The whole table converts or none of it does: a unit the
        registry cannot invert (unregistered, or one needing an additive offset)
        drops the table back to the schema input unit rather than showing a mixture.
        """
        source = self._pdef.input_unit or ""
        target = display_unit or source
        if not source or target == source:
            return source, list(values)
        try:
            return target, [
                display_in_unit(value, source, target, self._pdef.canonical_unit)
                for value in values
            ]
        except KeyError:
            return source, list(values)

    def _write_unit(self) -> str | None:
        """The unit to hand the API, or ``None`` when the table is in input units."""
        return self._unit if self._unit != (self._pdef.input_unit or "") else None

    # -- construction -------------------------------------------------------

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Dot-path + description + the "one value per configuration" reminder."""
        path = QLabel(self._dotpath, self)
        path.setObjectName("paramEditorPath")
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path)

        description = self._pdef.description or ""
        desc = QLabel(description, self)
        desc.setObjectName("paramEditorDescription")
        desc.setWordWrap(True)
        desc.setVisible(bool(description))
        layout.addWidget(desc)
        self._description_label = desc

    def _build_table(self, layout: QVBoxLayout, values: Sequence[Any]) -> None:
        """One row per configuration: accent chip + name, value editor, unit."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        accents = active_theme().config_accents
        unit = self._unit
        for row, name in enumerate(self._names):
            label = QLabel(name, self)
            label.setObjectName("configuredValuesName")
            chip = QLabel(self)
            chip.setObjectName("configuredValuesChip")
            chip.setPixmap(self._accent_chip(accents[row % len(accents)]))
            editor = self._make_value_editor(values[row] if row < len(values) else None)
            self._editors.append(editor)
            unit_label = QLabel(unit, self)
            unit_label.setObjectName("configuredValuesUnit")

            grid.addWidget(chip, row, 0)
            grid.addWidget(label, row, 1)
            grid.addWidget(editor, row, 2)
            grid.addWidget(unit_label, row, 3)
        layout.addLayout(grid)

    @staticmethod
    def _accent_chip(colour: str) -> QPixmap:
        """A small solid square of *colour* — the configuration's identity chip."""
        pixmap = QPixmap(_CHIP_PX, _CHIP_PX)
        pixmap.fill(QColor(colour))
        return pixmap

    def _make_value_editor(self, current: Any) -> QWidget:
        """The editor this parameter's dtype/enum/bounds call for, seeded with *current*.

        Deliberately the same set of editors, chosen by the same schema rules, as the
        single-value parameter editor — a configured value is an ordinary value that
        happens to have N of them, and must not acquire a second entry idiom.
        """
        pdef = self._pdef
        if pdef.enum_values is not None:
            combo = QComboBox(self)
            combo.addItems(list(pdef.enum_values))
            combo.setCurrentIndex(max(combo.findText("" if current is None else str(current)), 0))
            return combo
        if pdef.dtype is bool:
            check = QCheckBox(self)
            check.setChecked(bool(current))
            return check
        if pdef.dtype is int:
            spin = QSpinBox(self)
            if pdef.bounds is not None:
                lo, hi = pdef.bounds
                spin.setRange(int(lo), int(hi))
            else:
                spin.setRange(_INT_MIN, _INT_MAX)
            spin.setValue(int(current) if current is not None else 0)
            return spin
        line = QLineEdit(self)
        line.setText("" if current is None else str(current))
        return line

    def _build_error_area(self, layout: QVBoxLayout) -> None:
        """The inline, themed what/why/action area (hidden until a rejected commit)."""
        frame = QFrame(self)
        frame.setObjectName("paramEditorError")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(6)

        header = QLabel("Rejected", frame)
        header.setObjectName("errorDialogHeader")
        header.setWordWrap(True)
        frame_layout.addWidget(header)

        self._error_form = QFormLayout()
        self._error_form.setSpacing(4)
        frame_layout.addLayout(self._error_form)

        frame.setVisible(False)
        layout.addWidget(frame)
        self._error_frame = frame

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        """OK (commit the whole column) / Cancel (touch nothing)."""
        buttons = QDialogButtonBox(self)
        cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.clicked.connect(self.reject)
        ok = buttons.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.clicked.connect(self.apply_values)
        layout.addWidget(buttons)
        self._buttons = buttons

    # -- commit -------------------------------------------------------------

    def apply_values(self) -> None:
        """Hand the whole column to the host; close on acceptance, stay open on rejection.

        One call, one column: the API replaces the parameter's values only after every
        one of them validates, so a rejection leaves the set untouched and the dialog
        open with the offending configuration named (Rule 17 — never a half-commit,
        never a silent drop).
        """
        rejection = self._commit(self.values(), self._write_unit())
        if rejection is not None:
            self._show_error(rejection)
            return
        self._clear_error()
        self.accept()

    def values(self) -> list[Any]:
        """The current editor values, in set order and in :attr:`unit`.

        Raw as typed — the API validates and converts them (Rule 2).
        """
        return [self._editor_value(editor) for editor in self._editors]

    @property
    def unit(self) -> str:
        """The unit every row displays in and is typed in (may be the input unit)."""
        return self._unit

    @staticmethod
    def _editor_value(editor: QWidget) -> Any:
        """Extract the native Python value from one row's editor."""
        if isinstance(editor, QComboBox):
            return editor.currentText()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QSpinBox):
            return editor.value()
        if isinstance(editor, QLineEdit):
            return editor.text()
        return None

    def _show_error(self, exc: RadiantError) -> None:
        """Render the rejection's what/why/action inline; keep the dialog open."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        what = str(getattr(exc, "what", "") or exc)
        why = str(getattr(exc, "why", "") or "")
        action = str(getattr(exc, "action", "") or "")
        self._add_row("What", what)
        if why:
            self._add_row("Why", why)
        if action:
            self._add_row("Action", action)
        self._error_frame.setVisible(True)

    def _add_row(self, label: str, text: str) -> None:
        """One what/why/action line in the inline error area."""
        caption = QLabel(label, self._error_frame)
        caption.setObjectName("errorDialogLabel")
        value = QLabel(text, self._error_frame)
        value.setObjectName("errorDialogValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._error_form.addRow(caption, value)

    def _clear_error(self) -> None:
        """Hide the inline error area and drop its fields."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        self._error_frame.setVisible(False)

    # -- accessors (tests / host) ------------------------------------------

    @property
    def dotpath(self) -> str:
        """The configured parameter this dialog edits."""
        return self._dotpath

    @property
    def names(self) -> tuple[str, ...]:
        """The configuration names, in set order (one row each)."""
        return tuple(self._names)

    def editor(self, index: int) -> QWidget:
        """The value editor for configuration *index* (tests drive these)."""
        return self._editors[index]

    @property
    def error_frame(self) -> QFrame:
        """The inline rejection area (visible only after a refused commit)."""
        return self._error_frame

    @property
    def buttons(self) -> QDialogButtonBox:
        """The OK / Cancel box."""
        return self._buttons


__all__ = ["ConfiguredValuesDialog"]
