"""One value editor **per configuration** — the shared column-editing block (§4.2c).

The owner's multi-configuration requirement, restated after the 2026-07-26 walkthrough:
*"when you click on a parameter that is configured you should be able to set the value
for all the configurations at one time — this should have two boxes, one for MWIR and
one for LWIR."* This widget is that block of boxes, and it is the **one** implementation
of it: the Parameter Editor embeds it both for a parameter that is already configured
and for the *stage-a-configure* expansion of a shared one (§4.2c). The stand-alone
``ConfiguredValuesDialog`` that Phase 4b shipped is retired — it was a second dialog
around this same table (Rule 27, one canonical version).

Each row carries, in set order:

* the configuration's stable accent chip (the same
  :attr:`~radiant.gui.themes.tokens.Theme.config_accents` hue, assigned by position,
  that the master selector and the Performance columns paint — §4.2b/§4.2e) and its name;
* a value editor built from the parameter's own schema entry (enum → combo, bool →
  check box, int → bounded spin box, float/str → line edit) — deliberately the same
  editors, chosen by the same schema rules, the single-value editor builds, because a
  configured value is an ordinary value that happens to have N of them;
* the unit, on every row (R-UNITS — no unrendered number anywhere).

**Units.** The block works in the **display unit** its host passes (the analyst's chosen
unit for that dot-path, ``ParameterPanel.display_units``), falling back to the schema
``input_unit``. Incoming values arrive in the input unit — what
:meth:`~radiant.api.config_set.ConfigurationSet.configured` stores — and are re-expressed
through the public registry seam (:func:`~radiant.gui.param_format.display_in_unit`); no
unit arithmetic lives here (Rule 2). The whole block converts or none of it does: a unit
the registry cannot invert drops every row back to the input unit rather than showing a
mixture. Writing is the host's job and happens once, at the API boundary, via a single
``configure(..., unit=)`` / ``set_values(..., unit=)`` call.

The widget makes **no** API call and holds no ``ConfigurationSet``: it renders values and
reports what is typed. One widget class per file (Rule 19); all colour/typography comes
from the QSS theme via the object names below (GUI plan §4.9), the only colour named
here being the accent token tuple read from the active theme.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

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


class PerConfigurationValues(QWidget):
    """A grid of one seeded value editor per configuration, in set order.

    Parameters
    ----------
    pdef:
        The parameter's schema entry — the single source of the editor kind, bounds,
        enum choices, and unit (never a transcribed list, Gap 70).
    names:
        The configuration names, in set order (one row each).
    values:
        The seed values, in set order, expressed in *source_unit*.
    source_unit:
        The unit *values* arrive in. ``None`` means the parameter's schema
        ``input_unit`` — what :meth:`~radiant.api.config_set.ConfigurationSet.configured`
        stores. A host seeding from a value it already re-expressed (the Parameter
        Editor staging a configure from its own display-unit editor) passes that unit
        instead, so the block never converts twice.
    display_unit:
        The unit every row should display and accept. ``None`` — or a unit the public
        registry cannot soundly invert — leaves the block in the schema input unit.
    parent:
        The owning widget, if any.

    Signals
    -------
    valueChanged():
        Emitted whenever any row's editor changes, so a host can refresh a preview.
    """

    valueChanged = Signal()

    def __init__(
        self,
        pdef: ParameterDef,
        names: Sequence[str],
        values: Sequence[Any],
        display_unit: str | None = None,
        parent: QWidget | None = None,
        source_unit: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._pdef = pdef
        self._names = list(names)
        self._editors: list[QWidget] = []
        self._unit_labels: list[QLabel] = []
        self._unit, row_values = self._in_display_unit(values, display_unit, source_unit)

        self.setObjectName("perConfigurationValues")
        self._build(row_values)

    # -- units --------------------------------------------------------------

    def _in_display_unit(
        self,
        values: Sequence[Any],
        display_unit: str | None,
        source_unit: str | None,
    ) -> tuple[str, list[Any]]:
        """The unit this block works in, plus *values* re-expressed in it.

        Conversion routes through the public registry seam
        (:func:`~radiant.gui.param_format.display_in_unit`) — no unit arithmetic lives
        here (Rule 2). A unit the registry cannot invert (unregistered, or one needing
        an additive offset) drops every row back to the schema input unit rather than
        showing a mixture.
        """
        source = source_unit if source_unit is not None else (self._pdef.input_unit or "")
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

    def write_unit(self) -> str | None:
        """The unit to hand the API, or ``None`` when the rows are in input units."""
        return self._unit if self._unit != (self._pdef.input_unit or "") else None

    # -- construction -------------------------------------------------------

    def _build(self, values: Sequence[Any]) -> None:
        """One row per configuration: accent chip + name, value editor, unit."""
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        accents = active_theme().config_accents
        for row, name in enumerate(self._names):
            chip = QLabel(self)
            chip.setObjectName("configuredValuesChip")
            chip.setPixmap(self._accent_chip(accents[row % len(accents)]))
            label = QLabel(name, self)
            label.setObjectName("configuredValuesName")
            editor = self._make_value_editor(values[row] if row < len(values) else None)
            self._editors.append(editor)
            unit_label = QLabel(self._unit, self)
            unit_label.setObjectName("configuredValuesUnit")
            self._unit_labels.append(unit_label)

            grid.addWidget(chip, row, 0)
            grid.addWidget(label, row, 1)
            grid.addWidget(editor, row, 2)
            grid.addWidget(unit_label, row, 3)

    @staticmethod
    def _accent_chip(colour: str) -> QPixmap:
        """A small solid square of *colour* — the configuration's identity chip."""
        pixmap = QPixmap(_CHIP_PX, _CHIP_PX)
        pixmap.fill(QColor(colour))
        return pixmap

    def _make_value_editor(self, current: Any) -> QWidget:
        """The editor this parameter's dtype/enum/bounds call for, seeded with *current*."""
        pdef = self._pdef
        if pdef.enum_values is not None:
            combo = QComboBox(self)
            combo.addItems(list(pdef.enum_values))
            combo.setCurrentIndex(max(combo.findText("" if current is None else str(current)), 0))
            combo.currentIndexChanged.connect(self.valueChanged)
            return combo
        if pdef.dtype is bool:
            check = QCheckBox(self)
            check.setChecked(bool(current))
            check.toggled.connect(self.valueChanged)
            return check
        if pdef.dtype is int:
            spin = QSpinBox(self)
            if pdef.bounds is not None:
                lo, hi = pdef.bounds
                spin.setRange(int(lo), int(hi))
            else:
                spin.setRange(_INT_MIN, _INT_MAX)
            spin.setValue(int(current) if current is not None else 0)
            spin.valueChanged.connect(self.valueChanged)
            return spin
        line = QLineEdit(self)
        line.setText("" if current is None else str(current))
        line.textChanged.connect(self.valueChanged)
        return line

    # -- read side ----------------------------------------------------------

    def values(self) -> list[Any]:
        """The current editor values, in set order and in :attr:`unit`.

        Raw as typed — the API validates and converts them (Rule 2).
        """
        return [self._editor_value(editor) for editor in self._editors]

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

    def set_unit(self, unit: str) -> None:
        """Adopt *unit* as the rows' unit and relabel every row.

        The typed numbers are **reinterpreted**, never converted — exactly what
        changing the unit selector does in the single-value editor, so the two entry
        idioms behave identically. The conversion still happens once, at the API
        boundary, from the unit this reports.
        """
        self._unit = unit
        for label in self._unit_labels:
            label.setText(unit)
        self.valueChanged.emit()

    @property
    def unit(self) -> str:
        """The unit every row displays in and is typed in (may be the input unit)."""
        return self._unit

    @property
    def names(self) -> tuple[str, ...]:
        """The configuration names, in set order (one row each)."""
        return tuple(self._names)

    def editor(self, index: int) -> QWidget:
        """The value editor for configuration *index* (tests drive these)."""
        return self._editors[index]


__all__ = ["PerConfigurationValues"]
