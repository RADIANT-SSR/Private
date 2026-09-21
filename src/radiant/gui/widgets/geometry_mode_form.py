"""Stage-0 input-mode forms for the Geometry screen (GUI plan Phase 5, §4.4).

:class:`GeometryModeForm` is the **Inputs** section of the Geometry stage's
contextual center (arch doc §4.4, section 1). It renders the four stage-0 input
families — viewing, solar, kinematics, LOS rate (:data:`radiant.gui.geometry_modes`)
— each as a **mode selector** over schema-driven field rows. Only the **active**
mode's fields are editable; the other modes' fields are shown disabled, so the user
sees the full structure but can drive exactly one door per family (ADR-0006 rule 1).

**The selector is the switch (CU-377, owner-ratified 2026-09-20).** Choosing a mode
withdraws the other doors' explicit inputs and seeds the chosen door from the value
it would carry under the current scene (:meth:`Sensor.geometry_door_values`), as
**one** logical action the window records as one undo step — the switch re-expresses
the geometry, it does not change it (usability-audit F-05: the selector used to be
display-only, leaving a second door's value greyed and stuck). A door with no
inverse (site-and-time, target velocity) is left unset and becomes editable; the
form remembers that pending choice until a value lands. Inside the S3 door the two
hour-angle entries (local solar time / LTAN) are a toggle, never two live fields
(F-25). The inactive doors display their **derived** values, not their inert schema
defaults (F-48), and a blank configuration opens on the documented default door of
every family — V1 / S1 / direct / K0 (F-15, F-26) — because the active mode is
detected from **explicit** provenance only.

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built
from the live :meth:`Sensor.parameter_def` — value, unit, bounds, description, and
editor kind all come from the schema, never a transcribed list. Editing a field
opens the shared :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`,
so a commit is exactly one ``sensor.set`` validated on a throwaway clone first (a
rejected value never touches the live sensor; the actionable what/why/action shows
inline) — the identical edit+reject discipline as the parameter tree (Phase 2). A
second door entered *outside* the selector — through the dock, say — is refused at
that door by the same guard (:mod:`radiant.gui.geometry_mode_guard`). The value
shows in the row's **display unit**, sharing the parameter panel's session
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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.edit_guard import apply_mode_switch, validate_mode_switch
from radiant.gui.geometry_modes import (
    MODE_FAMILIES,
    MODE_HINTS,
    SUBDOORS,
    GeometryModeFamily,
    active_mode_key,
    all_mode_params,
    family_title,
    implicated_families,
    mode_label,
)
from radiant.gui.mode_switch import ModeSwitchPlan, plan_mode_switch, plan_subdoor_switch
from radiant.gui.param_format import (
    canonical_display_text,
    field_display_text,
)
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow as _FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_TITLE = "Geometry inputs — pick one mode per family"
_DERIVED_TOOLTIP = "Derived from the active door — pick this mode on the selector to enter it"


class _FamilyBlock(QWidget):
    """One family selector: a heading, a mode combo, anchor rows, and per-mode rows.

    Signals
    -------
    modeChosen(str, str):
        ``(family key, mode key)`` when the **user** picks a mode on the combo
        (programmatic selection from a refresh never emits it).
    subdoorChosen(str, int):
        ``(mode key, index)`` when the user flips a sub-door toggle (S3's
        local-solar-time / LTAN choice).
    """

    modeChosen = Signal(str, str)
    subdoorChosen = Signal(str, int)

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

        self._title = QLabel(family_title(family.key), self)
        self._title.setObjectName("geoModeFamilyTitle")
        layout.addWidget(self._title)

        self._selector = QComboBox(self)
        self._selector.setObjectName("geoModeSelector")
        # Size the combo to the available column width, not to its longest item: a mode label
        # like "Path zenith at lower endpoint (V1)" is wide, and adjusting-to-contents made the
        # combo (and so the whole form) demand more width than the accordion column, tripping its
        # horizontal scrollbar (owner bug 2026-07-14). Minimum-contents sizing + Expanding lets
        # the closed combo elide its display text and shrink to the column.
        self._selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._selector.setMinimumContentsLength(6)
        self._selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for index, mode in enumerate(family.modes):
            self._selector.addItem(mode_label(mode.key), mode.key)
            hint = MODE_HINTS.get(mode.key)
            if hint:
                self._selector.setItemData(index, hint, Qt.ItemDataRole.ToolTipRole)
        self._selector.currentIndexChanged.connect(self._apply_active_mode)
        # ``activated`` fires only on a user pick (never on setCurrentIndex), so a
        # refresh that re-selects the detected mode cannot trigger a switch.
        self._selector.activated.connect(self._on_user_pick)
        layout.addWidget(self._selector)

        # Anchor rows (always editable) then every mode's field rows (built once;
        # enabled/disabled by the active mode). Kept keyed by dot-path for refresh.
        self._rows: dict[str, _FieldRow] = {}
        self._mode_of_row: dict[str, str | None] = {}  # dotpath -> mode key (None = anchor)
        self._subdoor_of_row: dict[str, tuple[str, int]] = {}  # dotpath -> (mode, index)
        self._subdoor_combos: dict[str, QComboBox] = {}  # mode key -> its toggle
        for dotpath in family.anchor_params:
            row = field_row(dotpath)
            self._rows[dotpath] = row
            self._mode_of_row[dotpath] = None
            layout.addWidget(row)
        for mode in family.modes:
            subdoors = SUBDOORS.get(mode.key, ())
            subdoor_params = {p: i for i, (_label, ps) in enumerate(subdoors) for p in ps}
            for dotpath in mode.params:
                if dotpath in subdoor_params and mode.key not in self._subdoor_combos:
                    layout.addWidget(self._build_subdoor_combo(mode.key, subdoors))
                row = field_row(dotpath)
                self._rows[dotpath] = row
                self._mode_of_row[dotpath] = mode.key
                if dotpath in subdoor_params:
                    self._subdoor_of_row[dotpath] = (mode.key, subdoor_params[dotpath])
                layout.addWidget(row)

    def _build_subdoor_combo(
        self, mode_key: str, subdoors: tuple[tuple[str, tuple[str, ...]], ...]
    ) -> QComboBox:
        combo = QComboBox(self)
        combo.setObjectName("geoModeSelector")
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(6)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setToolTip("Two entries for the same quantity — choose one; the other is withdrawn")
        for label, _params in subdoors:
            combo.addItem(label)
        combo.currentIndexChanged.connect(self._apply_active_mode)
        combo.activated.connect(lambda index, key=mode_key: self.subdoorChosen.emit(key, index))
        self._subdoor_combos[mode_key] = combo
        return combo

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

    def subdoor_combo(self, mode_key: str) -> QComboBox | None:
        """The sub-door toggle of *mode_key* (``None`` when the mode has none)."""
        return self._subdoor_combos.get(mode_key)

    def mode_of_row(self, dotpath: str) -> str | None:
        """The mode key owning *dotpath*'s row (``None`` for an anchor)."""
        return self._mode_of_row[dotpath]

    def active_mode(self) -> str:
        """The selected mode key."""
        return str(self._selector.currentData())

    def active_subdoor(self, mode_key: str) -> int:
        """The selected sub-door index of *mode_key* (0 when it has none)."""
        combo = self._subdoor_combos.get(mode_key)
        return combo.currentIndex() if combo is not None else 0

    def set_active_mode(self, mode_key: str) -> None:
        """Select *mode_key* and update which rows are editable (no switch is planned)."""
        index = self._selector.findData(mode_key)
        if index >= 0:
            self._selector.setCurrentIndex(index)
        self._apply_active_mode()

    def set_active_subdoor(self, mode_key: str, index: int) -> None:
        """Select sub-door *index* of *mode_key* (no switch is planned)."""
        combo = self._subdoor_combos.get(mode_key)
        if combo is not None:
            combo.setCurrentIndex(index)
        self._apply_active_mode()

    def _on_user_pick(self, index: int) -> None:
        self.modeChosen.emit(self._family.key, str(self._selector.itemData(index)))

    def _apply_active_mode(self) -> None:
        """Enable the active mode's rows (and anchors); disable the rest."""
        active = self.active_mode()
        for dotpath, row in self._rows.items():
            owner = self._mode_of_row[dotpath]
            editable = owner is None or owner == active
            subdoor = self._subdoor_of_row.get(dotpath)
            if editable and subdoor is not None:
                editable = subdoor[1] == self.active_subdoor(subdoor[0])
            row.set_editable(editable)
        for mode_key, combo in self._subdoor_combos.items():
            combo.setVisible(mode_key == active)

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
        Emitted with the dot-path after an accepted edit — or after an accepted
        mode switch, with the dot-path it seeded or withdrew first — so the host
        window can refresh the parameter tree, this form, and mark results stale (a
        re-evaluation is due) — the same contract as
        :attr:`ParameterPanel.parameterEdited`. The window diffs the explicit
        inputs against its snapshot, so a switch that moved several inputs is
        recorded as one undo macro (CU-372 F-20).
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryModeForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}
        # A mode the user chose whose door holds no input yet (site-and-time, target
        # velocity, or a scene with no derived value to seed from): detection would
        # fall back to the family default, so the choice is held here until a value
        # lands in the chosen door — then provenance detection takes over.
        self._pending_mode: dict[str, str] = {}
        self._pending_subdoor: dict[str, int] = {}
        self._pending_peers: list[GeometryModeForm] = []

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
            block.modeChosen.connect(self.choose_mode)
            block.subdoorChosen.connect(self.choose_subdoor)
            layout.addWidget(block)
            self._blocks[family.key] = block
        layout.addStretch(1)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the parameter panel's session display-unit dict (shared by
        reference), so a unit chosen in either surface reflects in both. A ``None``
        sensor blanks every field (the pre-config state). Pending selector choices
        belong to the sensor they were made on: a re-bind of the *same* sensor (the
        window re-binds after every evaluation) keeps them, a different sensor drops
        them.
        """
        if sensor is not self._sensor:
            self._pending_mode.clear()
            self._pending_subdoor.clear()
        self._sensor = sensor
        self._display_units = display_units
        if sensor is not None:
            self._assert_schema_present(sensor)
        self.refresh()

    def share_pending_with(self, other: GeometryModeForm) -> None:
        """Let *other* show the same pending door choice as this form.

        The Inputs-tab and Schematic-tab forms are two views of one sensor; a
        no-inverse door (site-and-time, target velocity) picked on one used to
        show on the other only once a value landed (Findings Log 2026-09-20).
        The choice is one dict object shared by reference, both ways.
        """
        other._pending_mode = self._pending_mode
        other._pending_subdoor = self._pending_subdoor
        if other not in self._pending_peers:
            self._pending_peers.append(other)
        if self not in other._pending_peers:
            other._pending_peers.append(self)

    def refresh(self) -> None:
        """Re-read every field's value and re-detect the active mode per family.

        Active doors show their input; inactive doors show the value they would
        carry under the current scene (derived, F-48) or — when the scene gives none
        — unset. Does **not** touch the conflict tint — the window owns that lifecycle
        (set on a failed evaluate, cleared on a clean run or an edit), so a value
        re-sync during a conflict does not wipe the highlight the user needs to see.
        """
        sensor = self._sensor
        doors: dict[str, Any] = dict(sensor.geometry_door_values()) if sensor is not None else {}
        explicit = set(sensor.inputs()) if sensor is not None else set()
        for block in self._blocks.values():
            family = block.family
            if sensor is not None:
                block.set_active_mode(self._active_mode_for(sensor, family))
                for mode_key in SUBDOORS:
                    if block.subdoor_combo(mode_key) is not None:
                        block.set_active_subdoor(mode_key, self._active_subdoor_for(mode_key))
            active = block.active_mode()
            for dotpath, row in block.rows.items():
                owner = block.mode_of_row(dotpath)
                if sensor is None:
                    row.set_value_text(_UNSET)
                    row.setToolTip("")
                elif owner is None or owner == active or dotpath in explicit:
                    row.set_value_text(field_display_text(sensor, dotpath, self._display_units))
                    row.setToolTip("")
                else:
                    pdef = sensor.parameter_def(dotpath)
                    text = canonical_display_text(
                        pdef, doors.get(dotpath), self._display_units.get(dotpath)
                    )
                    row.set_value_text(text)
                    row.setToolTip(_DERIVED_TOOLTIP if text != _UNSET else "")
            block._apply_active_mode()

    def _assert_schema_present(self, sensor: Sensor) -> None:
        """Fail loudly if a named dot-path vanished from the schema (drift guard)."""
        defs = sensor.parameter_defs()
        missing = [p for p in all_mode_params() if p not in defs]
        assert not missing, f"geometry mode-form dot-paths not in schema: {missing}"

    # -- active-mode detection ---------------------------------------------

    def _active_mode_for(self, sensor: Sensor, family: GeometryModeFamily) -> str:
        """The detected mode, or the user's pending choice while its door is empty."""
        detected = self._detect_active_mode(sensor, family)
        pending = self._pending_mode.get(family.key)
        if pending is not None and detected == family.default_mode_key:
            return pending
        self._pending_mode.pop(family.key, None)
        return detected

    def _active_subdoor_for(self, mode_key: str) -> int:
        """The sub-door holding an input, else the pending choice, else the first."""
        sensor = self._sensor
        explicit = set(sensor.inputs()) if sensor is not None else set()
        for index, (_label, dotpaths) in enumerate(SUBDOORS[mode_key]):
            if any(dotpath in explicit for dotpath in dotpaths):
                self._pending_subdoor.pop(mode_key, None)
                return index
        return self._pending_subdoor.get(mode_key, 0)

    def _detect_active_mode(self, sensor: Sensor, family: GeometryModeFamily) -> str:
        """Which mode *family* sits in, from provenance (mirrors geometry.modes)."""
        return active_mode_key(
            family,
            lambda dotpath: self._is_provided(sensor, dotpath),
            lambda dotpath: self._input_value(sensor, dotpath),
        )

    @staticmethod
    def _is_provided(sensor: Sensor, dotpath: str) -> bool:
        """True when *dotpath* holds an explicit input (user-set / config / preset).

        Read off the inputs view, never off resolved provenance: on a configuration
        that cannot resolve yet every resolved provenance is unknown, and treating
        "unknown" as "provided" made a blank configuration open on V2 / S2 / K1
        instead of the documented default doors (CU-377 F-15 / F-26).
        """
        return dotpath in sensor.input_provenances()

    @staticmethod
    def _input_value(sensor: Sensor, dotpath: str) -> Any:
        """The resolved input value, or ``None`` if unset / not yet resolvable.

        ``RadiantError`` covers a whole config that cannot resolve (a blank
        File → New) — the field shows unset instead of crashing bind (found
        2026-07-16 with the CU-140 guard tests).
        """
        try:
            return sensor.get_input(dotpath)
        except (KeyError, RadiantError):
            return None

    # -- mode switching (CU-377 F-05 / F-25) ---------------------------------

    def choose_mode(self, family_key: str, mode_key: str) -> None:
        """Switch *family_key* to *mode_key* exactly as a user pick on the selector does.

        Plans the switch (withdraw the other doors, seed the chosen one from its
        derived value), validates it on a throwaway clone, applies it to the live
        sensor as one action and signals the edit once, so the window records one
        undo step. A refused switch shows the actionable error and leaves the live
        sensor untouched; a choice that moves nothing is simply remembered.
        """
        sensor = self._sensor
        if sensor is None:
            return
        block = self._blocks[family_key]
        plan = plan_mode_switch(sensor, block.family, mode_key)
        self._pending_mode[family_key] = mode_key
        self._run_plan(plan, family_key)

    def choose_subdoor(self, mode_key: str, index: int) -> None:
        """Flip *mode_key*'s sub-door toggle to *index*, withdrawing the other entry."""
        sensor = self._sensor
        if sensor is None:
            return
        plan = plan_subdoor_switch(sensor, mode_key, index)
        self._pending_subdoor[mode_key] = index
        # Withdrawing the other entry may empty the whole door (S3 with only its
        # hour angle set); the family must stay on this mode, not fall back to
        # its default, so the operator can enter the replacement.
        for block in self._blocks.values():
            if block.subdoor_combo(mode_key) is not None:
                self._pending_mode[block.family.key] = mode_key
        self._run_plan(plan, None)

    def _run_plan(self, plan: ModeSwitchPlan, family_key: str | None) -> None:
        sensor = self._sensor
        if sensor is None:  # pragma: no cover - callers check
            return
        if plan.is_empty:
            self.refresh()
            for peer in self._pending_peers:
                peer.refresh()
            return
        verdict = validate_mode_switch(sensor, plan)
        if verdict.unexpected is not None:
            exec_dialog(UnexpectedErrorDialog(verdict.unexpected, plan.label, self))
            self.refresh()
            return
        if verdict.rejection is not None:
            if family_key is not None:
                self._pending_mode.pop(family_key, None)
            self.refresh()
            exec_dialog(
                ActionableErrorDialog(
                    verdict.rejection,
                    plan.headline,
                    self,
                    verb="switch",
                    title="Mode Switch Refused",
                    header=f"Cannot {plan.label[0].lower()}{plan.label[1:]}",
                )
            )
            return
        apply_mode_switch(sensor, plan)
        self.refresh()
        for peer in self._pending_peers:
            peer.refresh()
        self.parameterEdited.emit(plan.headline)

    # -- value formatting (display unit, R-UNITS) ---------------------------

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, dotpath, self._display_units)

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
        exec_dialog(dialog)

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

    def active_subdoor(self, mode_key: str) -> int:
        """The selected sub-door index of *mode_key* (0 when it has none)."""
        for block in self._blocks.values():
            if block.subdoor_combo(mode_key) is not None:
                return block.active_subdoor(mode_key)
        return 0

    def select_mode(self, family_key: str, mode_key: str) -> None:
        """Programmatically select *mode_key* in *family_key* (updates editability only).

        A display-side selection — no inputs move. :meth:`choose_mode` is the switch.
        """
        self._blocks[family_key].set_active_mode(mode_key)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the field for *dotpath*."""
        return self._row(dotpath).value_text()

    def field_tooltip(self, dotpath: str) -> str:
        """The row tooltip for *dotpath* (names a derived display, F-48)."""
        return self._row(dotpath).toolTip()

    def is_field_editable(self, dotpath: str) -> bool:
        """True when the field for *dotpath* is currently editable."""
        return self._row(dotpath).value_button.isEnabled()

    def is_conflicting(self, family_key: str) -> bool:
        """True when *family_key*'s selector is showing the conflict tint."""
        return self._blocks[family_key].property("state") == "conflict"

    def selector(self, family_key: str) -> QComboBox:
        """The mode selector combo for *family_key*."""
        return self._blocks[family_key].selector

    def subdoor_selector(self, mode_key: str) -> QComboBox | None:
        """The sub-door toggle of *mode_key* (S3: local solar time / LTAN)."""
        for block in self._blocks.values():
            combo = block.subdoor_combo(mode_key)
            if combo is not None:
                return combo
        return None

    def _row(self, dotpath: str) -> _FieldRow:
        for block in self._blocks.values():
            if dotpath in block.rows:
                return block.rows[dotpath]
        raise KeyError(dotpath)


__all__ = ["GeometryModeForm"]
