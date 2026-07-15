"""Stage-0 input-mode forms for the Geometry screen (GUI plan Phase 5, §4.4).

:class:`GeometryModeForm` is the **Inputs** section of the Geometry stage's
contextual center (arch doc §4.4, section 1). It renders the three stage-0 input
families — viewing, solar, kinematics (:data:`radiant.gui.geometry_modes`) — each
as a **mode selector** over schema-driven field rows. Only the **active** mode's
fields are editable; the other modes' fields are shown disabled, so the user sees
the full structure but can drive exactly one door per family (ADR-0006 rule 1).

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built
from the live :meth:`Sensor.parameter_def` — value, unit, bounds, description, and
editor kind all come from the schema, never a transcribed list. Editing a field
opens the shared :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`,
so a commit is exactly one ``sensor.set`` validated on a throwaway clone first (a
rejected value never touches the live sensor; the actionable what/why/action shows
inline) — the identical edit+reject discipline as the parameter tree (Phase 2). The
value shows in the row's **display unit**, sharing the parameter panel's session
display-unit store so a unit chosen in either surface agrees.

**Conflict highlight (Phase 5 task 3).** When an evaluation raises the stage's
over-/under-specification error, :meth:`highlight_error` tints the offending
family's selector (:func:`radiant.gui.geometry_modes.implicated_families`) so the
user sees which mode's inputs conflict. The error text itself is shown by the
window's actionable-error dialog and the Messages panel — this screen adds only the
in-place locator; it invents **no** GUI-side geometry validation.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9);
this module sets structure and text only. One widget class per file (Rule 19); the
private field/selector rows are its internal parts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.geometry_modes import (
    MODE_FAMILIES,
    GeometryModeFamily,
    active_mode_key,
    all_mode_params,
    implicated_families,
)
from radiant.gui.param_format import (
    display_in_unit,
    format_value,
    provenance_from_explain,
)
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_TITLE = "Geometry inputs — pick one mode per family"

# The value shown for a mode-entry field the user has not provided (inert default):
# a visible "not set via this door" state, not a swallowed value.
_UNSET = "—"


class _ElidingLabel(QLabel):
    """A field label that elides with an ellipsis instead of forcing its full text width.

    The geometry field labels are raw dot-path leaves (e.g. ``sensor_off_nadir_rad``); a
    plain :class:`QLabel` demands its full text width as a hard minimum, which pushed the
    field row past the right-column accordion and tripped its horizontal scrollbar (owner
    bug 2026-07-14). This label reports a *small* minimum width (so the row shrinks to the
    column and the value field stays fully visible), keeps its full width as the *preferred*
    hint (so a wide column still shows the whole name), and elides the displayed text to the
    available width — the full name stays available as a hover tooltip. QSS styling is
    preserved (the base :class:`QLabel` still paints the text, only the string is elided).
    """

    _MIN_CHARS = 4

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = text
        self.setToolTip(text)
        super().setText(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """A few characters wide, so the row can shrink to the column (value stays visible)."""
        fm = QFontMetrics(self.font())
        return QSize(fm.averageCharWidth() * self._MIN_CHARS, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        """The full label width when the column has room (elides only when it does not)."""
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self._full), super().sizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 — Qt override
        super().resizeEvent(event)
        fm = QFontMetrics(self.font())
        super().setText(fm.elidedText(self._full, Qt.TextElideMode.ElideRight, self.width()))


class _FieldRow(QWidget):
    """One schema-driven parameter field: a label + a value button that opens the editor.

    The value button carries the resolved value in the row's display unit (R-UNITS)
    and, when enabled, opens the full :class:`ParameterEditorDialog` on click — the
    same value+unit+reject path the parameter tree uses. Disabled (a non-active
    mode's field) it is greyed and inert.
    """

    def __init__(self, dotpath: str, label: str, on_edit: Callable[[str], None]) -> None:
        super().__init__(None)
        self._dotpath = dotpath
        self._on_edit = on_edit
        self.setObjectName("geoModeFieldRow")

        row = QGridLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(10)
        # The value field takes the slack (column 1 stretches); the label keeps its natural
        # width (column 0). This makes the field editors *expand to the available column
        # width* rather than forcing a fixed too-wide row that overflows the right-column
        # accordion and trips its horizontal scrollbar (owner bug 2026-07-14).
        row.setColumnStretch(0, 0)
        row.setColumnStretch(1, 1)

        self._label = _ElidingLabel(label, self)
        self._label.setObjectName("geoModeFieldLabel")
        self._label.setWordWrap(False)

        self._value = QPushButton(_UNSET, self)
        self._value.setObjectName("geoModeFieldValue")
        self._value.setCursor(Qt.CursorShape.PointingHandCursor)
        # Expand horizontally to fill the column (shrinking to a modest minimum) so a long
        # value never pushes the row wider than its column — no horizontal clip/scrollbar.
        self._value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._value.setMinimumWidth(64)
        self._value.clicked.connect(lambda: self._on_edit(self._dotpath))

        row.addWidget(self._label, 0, 0)
        row.addWidget(self._value, 0, 1)

    @property
    def dotpath(self) -> str:
        """The parameter this row edits."""
        return self._dotpath

    def set_value_text(self, text: str) -> None:
        """Set the displayed value+unit text."""
        self._value.setText(text)

    def value_text(self) -> str:
        """The displayed value+unit text (for tests)."""
        return self._value.text()

    def set_editable(self, editable: bool) -> None:
        """Enable/disable the field (only the active mode's fields are editable)."""
        self.setEnabled(editable)
        self._value.setEnabled(editable)

    @property
    def value_button(self) -> QPushButton:
        """The clickable value button (opens the editor)."""
        return self._value


class _FamilyBlock(QWidget):
    """One family selector: a heading, a mode combo, anchor rows, and per-mode rows."""

    def __init__(
        self,
        family: GeometryModeFamily,
        field_row: Callable[[str], _FieldRow],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._family = family
        self.setObjectName("geoModeFamily")
        # A bare QWidget paints no QSS background/border unless styled-background is on;
        # the family card's panel fill and the conflict tint need it (Qt gotcha).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("state", "normal")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._title = QLabel(family.title, self)
        self._title.setObjectName("geoModeFamilyTitle")
        layout.addWidget(self._title)

        self._selector = QComboBox(self)
        self._selector.setObjectName("geoModeSelector")
        # Size the combo to the available column width, not to its longest item: a mode label
        # like "Path zenith θ_o (V1)" is wide, and adjusting-to-contents made the combo (and so
        # the whole form) demand more width than the accordion column, tripping its horizontal
        # scrollbar (owner bug 2026-07-14). Minimum-contents sizing + an Expanding policy lets
        # the closed combo elide its display text and shrink to the column.
        self._selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._selector.setMinimumContentsLength(6)
        self._selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for mode in family.modes:
            self._selector.addItem(mode.label, mode.key)
        self._selector.currentIndexChanged.connect(self._apply_active_mode)
        layout.addWidget(self._selector)

        # Anchor rows (always editable) then every mode's field rows (built once;
        # enabled/disabled by the active mode). Kept keyed by dot-path for refresh.
        self._rows: dict[str, _FieldRow] = {}
        self._mode_of_row: dict[str, str | None] = {}  # dotpath -> mode key (None = anchor)
        for dotpath in family.anchor_params:
            row = field_row(dotpath)
            self._rows[dotpath] = row
            self._mode_of_row[dotpath] = None
            layout.addWidget(row)
        for mode in family.modes:
            for dotpath in mode.params:
                row = field_row(dotpath)
                self._rows[dotpath] = row
                self._mode_of_row[dotpath] = mode.key
                layout.addWidget(row)

    @property
    def family(self) -> GeometryModeFamily:
        """The family this block represents."""
        return self._family

    @property
    def rows(self) -> dict[str, _FieldRow]:
        """Field rows keyed by dot-path."""
        return self._rows

    @property
    def selector(self) -> QComboBox:
        """The mode selector combo."""
        return self._selector

    def active_mode(self) -> str:
        """The selected mode key."""
        return str(self._selector.currentData())

    def set_active_mode(self, mode_key: str) -> None:
        """Select *mode_key* and update which rows are editable."""
        index = self._selector.findData(mode_key)
        if index >= 0:
            self._selector.setCurrentIndex(index)
        self._apply_active_mode()

    def _apply_active_mode(self) -> None:
        """Enable the active mode's rows (and anchors); disable the rest."""
        active = self.active_mode()
        for dotpath, row in self._rows.items():
            owner = self._mode_of_row[dotpath]
            row.set_editable(owner is None or owner == active)

    def set_conflict(self, on: bool) -> None:
        """Tint the selector as conflicting (Phase 5 task 3) or clear it."""
        self.setProperty("state", "conflict" if on else "normal")
        # Re-polish so the property-based QSS rule repaints.
        style = self.style()
        style.unpolish(self)
        style.polish(self)


class GeometryModeForm(QWidget):
    """The Geometry stage's Inputs section: mode selectors + schema-driven forms.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can
        refresh the parameter tree, this form, and mark results stale (a
        re-evaluation is due) — the same contract as
        :attr:`ParameterPanel.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryModeForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._title = QLabel(_TITLE, self)
        self._title.setObjectName("geoModeFormTitle")
        # Wrap rather than force the full title width — a long single-line title otherwise
        # set the form's minimum width wider than the accordion column (owner bug 2026-07-14).
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._blocks: dict[str, _FamilyBlock] = {}
        for family in MODE_FAMILIES:
            block = _FamilyBlock(family, self._make_row, self)
            layout.addWidget(block)
            self._blocks[family.key] = block
        layout.addStretch(1)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the parameter panel's session display-unit dict (shared by
        reference), so a unit chosen in either surface reflects in both. A ``None``
        sensor blanks every field (the pre-config state).
        """
        self._sensor = sensor
        self._display_units = display_units
        if sensor is not None:
            self._assert_schema_present(sensor)
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field's value and re-detect the active mode per family.

        Does **not** touch the conflict tint — the window owns that lifecycle (set on a
        failed evaluate, cleared on a clean run or an edit), so a value re-sync during a
        conflict does not wipe the highlight the user needs to see.
        """
        sensor = self._sensor
        for block in self._blocks.values():
            if sensor is not None:
                block.set_active_mode(self._detect_active_mode(sensor, block.family))
            for dotpath, row in block.rows.items():
                row.set_value_text(self._value_text(dotpath))
            block._apply_active_mode()

    def _assert_schema_present(self, sensor: Sensor) -> None:
        """Fail loudly if a named dot-path vanished from the schema (drift guard)."""
        defs = sensor.parameter_defs()
        missing = [p for p in all_mode_params() if p not in defs]
        assert not missing, f"geometry mode-form dot-paths not in schema: {missing}"

    # -- active-mode detection ---------------------------------------------

    def _detect_active_mode(self, sensor: Sensor, family: GeometryModeFamily) -> str:
        """Which mode *family* sits in, from provenance (mirrors geometry.modes)."""
        return active_mode_key(
            family,
            lambda dotpath: self._is_provided(sensor, dotpath),
            lambda dotpath: self._input_value(sensor, dotpath),
        )

    @staticmethod
    def _is_provided(sensor: Sensor, dotpath: str) -> bool:
        """True when *dotpath* resolved from an explicit input (not its schema default)."""
        provenance = provenance_from_explain(sensor.explain(dotpath))
        return provenance is not None and provenance != "default"

    @staticmethod
    def _input_value(sensor: Sensor, dotpath: str) -> Any:
        """The resolved input value, or ``None`` if unset."""
        try:
            return sensor.get_input(dotpath)
        except KeyError:
            return None

    # -- value formatting (display unit, R-UNITS) ---------------------------

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        pdef = sensor.parameter_def(dotpath)
        value = self._input_value(sensor, dotpath)
        target = self._display_units.get(dotpath)
        if target is None or target == pdef.input_unit:
            return format_value(value, pdef.input_unit)
        try:
            shown = display_in_unit(value, pdef.input_unit, target, pdef.canonical_unit)
        except KeyError:
            return format_value(value, pdef.input_unit)
        return format_value(shown, target)

    # -- editing (reuses the Parameter Editor dialog + reject discipline) ----

    def _make_row(self, dotpath: str) -> _FieldRow:
        """Build a field row bound to the editor-dialog open handler."""
        leaf = dotpath.split(".", 1)[1] if "." in dotpath else dotpath
        return _FieldRow(dotpath, leaf, self._open_editor)

    def _open_editor(self, dotpath: str) -> None:
        """Open the full Parameter Editor for *dotpath* (one API call on commit)."""
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_commit,
            self,
            display_unit=self._display_units.get(dotpath),
        )
        dialog.exec()

    def _after_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the chosen display unit, refresh, and signal the edit upstream."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)

    # -- conflict highlight (Phase 5 task 3) --------------------------------

    def highlight_error(self, what: str, context: dict[str, Any] | None) -> set[str]:
        """Tint the family selector(s) a geometry over/under-spec error names.

        Returns the set of highlighted family keys (empty when the error does not
        localise to a family — then the window's actionable dialog still shows it).
        """
        families = implicated_families(what, context)
        for key, block in self._blocks.items():
            block.set_conflict(key in families)
        return families

    def clear_highlight(self) -> None:
        """Clear any conflict tint from every selector."""
        for block in self._blocks.values():
            block.set_conflict(False)

    # -- accessors (tests) --------------------------------------------------

    def active_mode(self, family_key: str) -> str:
        """The selected mode key for *family_key*."""
        return self._blocks[family_key].active_mode()

    def select_mode(self, family_key: str, mode_key: str) -> None:
        """Programmatically select *mode_key* in *family_key* (updates editability)."""
        self._blocks[family_key].set_active_mode(mode_key)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the field for *dotpath*."""
        return self._row(dotpath).value_text()

    def is_field_editable(self, dotpath: str) -> bool:
        """True when the field for *dotpath* is currently editable."""
        return self._row(dotpath).value_button.isEnabled()

    def is_conflicting(self, family_key: str) -> bool:
        """True when *family_key*'s selector is showing the conflict tint."""
        return self._blocks[family_key].property("state") == "conflict"

    def selector(self, family_key: str) -> QComboBox:
        """The mode selector combo for *family_key*."""
        return self._blocks[family_key].selector

    def _row(self, dotpath: str) -> _FieldRow:
        for block in self._blocks.values():
            if dotpath in block.rows:
                return block.rows[dotpath]
        raise KeyError(dotpath)


__all__ = ["GeometryModeForm"]
