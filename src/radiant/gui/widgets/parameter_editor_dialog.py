"""Full-detail modal editor for one parameter — the "open it up" box (§4.3).

:class:`ParameterEditorDialog` is the owner-requested Parameter Editor (Phase 3
checkpoint punch-list, 2026-07-13): a box that opens on a parameter and shows the
**full** dot-path (the tree truncates long names), the schema description, the current
value with its unit and provenance, the schema bounds, and the derived/read-only state
— and lets the user set a new value **and unit** and see the resulting canonical value
before and after applying.

**Two complementary edit paths (documented here and in arch doc §4.3).** The parameter
tree keeps its fast in-place editor on the **Value** column (double-click column 1 →
:class:`~radiant.gui.widgets.parameter_delegate.ParameterEditDelegate`, one keystroke to
a number). This dialog is the **slow, informative** path: double-click the **Parameter**
(name) or **Source** column, or pick "Edit…" from the right-click menu. The two never
overlap — Value → inline editor, everything else → this dialog.

**Units (Rule 2).** The unit selector is populated from the units the conversion
registry can actually convert to the parameter's canonical unit, read through the public
``radiant.api.units`` seam (the same surface the ``radiant convert`` CLI enumerates from)
— never a hardcoded list. Committing is exactly one
``sensor.set(dotpath, value, unit=<chosen>)`` (§4.1); the conversion happens once, inside
that call (the sanctioned Rule-2 boundary). The canonical preview is computed the same
way — on a throwaway ``sensor.clone()`` — so no unit maths is reimplemented in the view.

**Multi-configuration (§4.2c, owner feedback 2026-07-26).** In a study this dialog is
also the *per-configuration* editor — the owner's *"you should be able to set the value
for all the configurations at one time … one box for MWIR and one for LWIR"*:

* opened on a **configured** parameter it shows one seeded value box per configuration
  (:class:`~radiant.gui.widgets.per_configuration_values.PerConfigurationValues` —
  accent chip + name + editor + unit, in set order) instead of the single box, and
  Apply commits the whole column in **one** ``set_values(..., unit=)`` call recorded as
  one scoped undo step. A rejection names the offending configuration, commits nothing,
  and keeps the dialog open;
* opened on a **shared** parameter in a study it offers *Configure across
  configurations…* — the answer to the owner's *"how do you set a variable to be
  configurable?"*. Clicking **stages** the intent and expands the dialog in place into
  the same seeded boxes; nothing is configured until Apply, which commits the promotion
  and its values as the single atomic ``configure(dotpath, values, unit=)`` call — so
  Cancel leaves the parameter shared and one undo returns it there. In a
  single-configuration session the button answers with the same actionable hint the
  4b context menu gives (``SINGLE_CONFIGURATION_HINT``), never a silent no-op.

The dialog still makes no ``ConfigurationSet`` call itself: it writes through the
:class:`~radiant.gui.config_scope.ConfigurationScope`'s committer, which is the window's
own method, so the single API call and the undo command stay with the window (R-API).
The scope is passed in, or found by walking the widget's ancestors
(:func:`~radiant.gui.config_scope.scope_of`) — a parentless dialog simply gets the
single-value behaviour.

**Rejection (Rules 15/17).** A rejected value is validated on a throwaway
``sensor.clone()`` first, so the live sensor is never touched; the actionable error
(what / why / action) renders **inside** the dialog and the dialog stays open for
correction. Only a clean value reaches the live sensor, and only then is the tree
refreshed (via the ``on_committed`` callback) — Apply keeps the dialog open, Apply & Close
dismisses it. A derived (⚡) parameter opens read-only: the value/unit editors are
disabled and only a Close button is offered.

One widget class per file (Rule 19). Styling is entirely from the design-system QSS
theme via object names; this module sets structure and text only (GUI plan §4.9).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from radiant.api.units import units_for
from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterBoundsError
from radiant.core.units import convert
from radiant.gui.config_scope import scope_of
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.display_units import global_display_unit
from radiant.gui.param_format import (
    DERIVED_BADGE,
    display_in_unit,
    format_value,
    is_derived,
    provenance_label,
    safe_provenance,
)
from radiant.gui.path_picker import default_browse_dir, path_picker_kind
from radiant.gui.target_spec_guard import introduced_target_spec_conflict
from radiant.gui.tolerance_units import convert_tolerance_value, field_unit_label
from radiant.gui.widgets.configure_menu import CONFIGURE_TEXT, SINGLE_CONFIGURATION_HINT
from radiant.gui.widgets.per_configuration_values import PerConfigurationValues
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor
    from radiant.core.parameters import ParameterDef
    from radiant.gui.config_scope import ConfigurationScope

# QSpinBox needs int limits when the schema declares no bounds for an int
# parameter (layout geometry, not a design token). Mirrors the delegate's fallback.
_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1

# The canonical-preview readout when the current editor value cannot yet be resolved
# (mid-typing, or out of bounds). A visible "not-yet-known" state, not a swallowed
# error — the real, actionable error surfaces on Apply (never here).
_PREVIEW_UNSET = "= —"

# Friendly label for the dimensionless (empty-string) unit in the unit selector.
_NO_UNIT_LABEL = "(none)"

# Extra px added to the unit-combo popup width beyond the widest item's text advance,
# covering the item margins and a possible scrollbar (layout geometry, not a token).
_COMBO_POPUP_PADDING_PX = 40

# Heading above the per-configuration value boxes (§4.2c multi-configuration mode).
PER_CONFIGURATION_HEADING = "Value in each configuration"

# The tolerance section keeps its base-level meaning in a study: ADR-0010 puts the
# Monte-Carlo spread on the shared parameter, not on one configuration's column. Said
# once, next to the section, rather than redesigning it (owner note 2026-07-26).
TOLERANCE_SHARED_NOTE = "Shared by every configuration — a tolerance is not per-configuration."

# Separator between per-configuration entries in the canonical preview, matching the
# badge tooltip's ``MWIR: 3.5 um · LWIR: 8 um`` shape.
_PREVIEW_SEPARATOR = " · "


# Bundled reference-data tree, inside the package at src/radiant/data/tables/ (same
# file-relative pattern as ``radiant.data.library``): this file is
# src/radiant/gui/widgets/parameter_editor_dialog.py → the ``radiant`` package root is
# parents[2]. Ships in a wheel install; Rule 30: no repo-root path assumption.

# Where a path parameter's Browse… picker starts when the field is empty, by top-level
# namespace: the shipped data family for that stage. Anything unmapped starts at the
# data root (if present) so the picker opens on RADIANT's bundled data rather than an
# arbitrary working directory (owner bug report 2026-07-18).


def convertible_units(canonical_unit: str, input_unit: str) -> list[str]:
    """Units the registry can convert to *canonical_unit* (public-seam enumeration).

    Reads the conversion registry through the public :mod:`radiant.api.units` seam
    (the same surface the ``radiant convert`` CLI lists targets from) and returns every
    source unit ``u`` for which ``convert(x, u, canonical_unit)`` is registered — i.e.
    every unit the user may legally enter a value in for this parameter. The
    parameter's own ``input_unit`` and ``canonical_unit`` are always included (both are
    always legal), so the list is never empty even for a single-unit dimension.
    """
    units = set(units_for(canonical_unit))
    units |= {canonical_unit, input_unit}
    return sorted(units)


class ParameterEditorDialog(QDialog):
    """Full-detail modal editor for one parameter — value + unit + provenance (§4.3).

    Parameters
    ----------
    sensor:
        The live :class:`~radiant.api.sensor.Sensor`; the single committed edit is one
        ``sensor.set`` on it (validated first on a clone).
    dotpath:
        The parameter to edit (full dot-path).
    on_committed:
        ``(dotpath, chosen_unit) -> None`` — called after a value is accepted and
        written to the live sensor, so the owning panel can refresh the tree, adopt the
        chosen unit as the row's display unit, and mark results stale. ``chosen_unit``
        is the unit the user picked (``None`` for a non-numeric parameter). Not called
        on rejection or for a read-only (derived) parameter.
    parent:
        The owning widget, if any.
    display_unit:
        The unit the value should open displayed in (owner feedback 2026-07-13) — the
        row's current display unit. Defaults to the schema ``input_unit``. If it is not
        soundly convertible from the input unit it falls back to the input unit.
    scope:
        The session's :class:`~radiant.gui.config_scope.ConfigurationScope`, which turns
        this into the per-configuration editor for a configured parameter and offers the
        *Configure across configurations…* affordance for a shared one (§4.2c). Omitted,
        it is found by walking *parent*'s ancestors; ``None`` throughout leaves the
        dialog in its single-value form.
    """

    def __init__(
        self,
        sensor: Sensor,
        dotpath: str,
        on_committed: Callable[[str, str | None], None] | None = None,
        parent: QWidget | None = None,
        display_unit: str | None = None,
        scope: ConfigurationScope | None = None,
    ) -> None:
        super().__init__(parent)
        self._sensor = sensor
        self._dotpath = dotpath
        self._on_committed = on_committed
        self._pdef: ParameterDef = sensor.parameter_def(dotpath)
        # The unit the Current line / editor / bounds open displayed in. With no
        # per-row choice the global preference applies (angles in degrees by
        # default — CU-326 owner ruling), so the dialog opens in the same unit the
        # row displays wherever it was launched from. Validated for sound
        # convertibility (falls back to input_unit) so no downstream conversion
        # can raise. Only meaningful for numeric params; "" for the rest.
        self._display_unit: str = self._sound_display_unit(
            display_unit
            or global_display_unit(self._pdef.input_unit or "")
            or self._pdef.input_unit
        )

        # Read-only when the value is derived from a consistency group (⚡): the dialog
        # opens informative but the editors stay disabled (arch doc §4.3, Rule 4).
        provenance = safe_provenance(sensor, dotpath)
        self._read_only = is_derived(provenance)

        # Multi-configuration state (§4.2c). ``_per_config`` is the live block of
        # per-configuration boxes (None in single-value mode); ``_staged_configure``
        # marks the boxes as a *staged* promotion that only Apply commits.
        self._scope: ConfigurationScope | None = scope if scope is not None else scope_of(parent)
        self._per_config: PerConfigurationValues | None = None
        self._staged_configure = False
        self._opened_configured = bool(
            self._scope is not None
            and self._scope.can_commit
            and not self._read_only
            and self._scope.is_configured(dotpath)
        )

        self.setObjectName("parameterEditorDialog")
        self.setWindowTitle(f"Edit — {dotpath}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        self._build_header(layout)
        self._build_info(layout, provenance)
        self._value_editor: QWidget = self._build_editor_row(layout)
        self._build_per_configuration_section(layout)
        self._build_configure_affordance(layout)
        # GT-2 tolerance annotation — placed BELOW the main value (owner request
        # 2026-07-17): the value is the headline, the Monte-Carlo spread annotates it.
        self._tol_distribution: QComboBox | None = None
        self._tol_params: dict[str, QLineEdit] = {}
        # Per-field unit suffix labels, kept in step with the value editor's unit.
        self._tol_units: dict[str, QLabel] = {}
        self._tol_shared_note: QLabel | None = None
        if self._pdef.dtype is float and not self._read_only:
            self._build_tolerance_section(layout)
        self._build_preview(layout)
        self._build_error_area(layout)
        self._build_buttons(layout)

        if self._opened_configured and self._scope is not None:
            # Already configured: open straight into one box per configuration, seeded
            # from the stored column (input units) and shown in the display unit.
            self._enter_per_configuration(
                self._scope.values_for(dotpath), self._pdef.input_unit or ""
            )

        # Seed the canonical preview with the current resolved value (the "before").
        self._update_preview()

    # -- construction -------------------------------------------------------

    def _build_header(self, layout: QVBoxLayout) -> None:
        """The full dot-path (selectable, mono) — the truncation the box exists to fix."""
        path = QLabel(self._dotpath, self)
        path.setObjectName("paramEditorPath")
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path)
        self._path_label = path

        description = self._pdef.description or ""
        desc = QLabel(description, self)
        desc.setObjectName("paramEditorDescription")
        desc.setWordWrap(True)
        desc.setVisible(bool(description))
        layout.addWidget(desc)
        self._description_label = desc

    def _build_info(self, layout: QVBoxLayout, provenance: str | None) -> None:
        """Current value + provenance, bounds, and derived/read-only state (informative)."""
        form = QFormLayout()
        form.setSpacing(6)

        self._current_label = QLabel("", self)
        self._current_label.setObjectName("errorDialogValue")
        self._current_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._add_row(form, "Current", self._current_label)
        self._render_current(provenance)

        # Kept by reference so Apply-without-close can re-express it in the newly
        # adopted unit alongside the Current line (CU-111).
        self._bounds_label: QLabel | None = None
        if self._pdef.bounds is not None:
            self._bounds_label = self._value_field(self._bounds_text())
            self._add_row(form, "Bounds", self._bounds_label)

        if self._read_only:
            note = self._value_field("derived from a consistency group — read-only")
            note.setObjectName("paramEditorDerivedNote")
            self._add_row(form, "State", note)

        layout.addLayout(form)

    def _build_editor_row(self, layout: QVBoxLayout) -> QWidget:
        """The value editor (per dtype) plus a unit selector for dimensional params."""
        row = QHBoxLayout()
        row.setSpacing(8)

        editor = self._make_value_editor()
        editor.setEnabled(not self._read_only)
        row.addWidget(editor, 1)

        # Browse… for filesystem-path parameters (leaf ends _path/_file/_dir): a native
        # picker filling the same line edit — typing a long path by hand stays possible,
        # it just stops being the only way (owner request 2026-07-18).
        self._browse_button: QPushButton | None = None
        if (
            self._pdef.dtype is str
            and self._pdef.enum_values is None
            and path_picker_kind(self._dotpath) is not None
            and isinstance(editor, QLineEdit)
        ):
            browse = QPushButton("Browse…", self)
            browse.setObjectName("paramEditorBrowseButton")
            browse.setEnabled(not self._read_only)
            browse.clicked.connect(self._on_browse)
            row.addWidget(browse)
            self._browse_button = browse

        # Unit selector for numeric parameters only (the unit= boundary applies to
        # float/int; enum/bool/str carry no unit). Populated from the public registry
        # seam, never a hardcoded list.
        self._unit_combo: QComboBox | None = None
        if self._pdef.dtype in (float, int):
            combo = QComboBox(self)
            combo.setObjectName("paramEditorUnitCombo")
            for unit in convertible_units(self._pdef.canonical_unit, self._pdef.input_unit):
                combo.addItem(unit if unit else _NO_UNIT_LABEL, unit)
            # Open on the row's display unit (owner feedback 2026-07-13), not always the
            # input unit — so a km-displayed altitude opens with the combo on km.
            start = combo.findData(self._display_unit)
            combo.setCurrentIndex(max(start, 0))
            combo.setEnabled(not self._read_only)
            combo.currentIndexChanged.connect(self._on_unit_changed)
            self._size_combo_popup(combo)
            row.addWidget(combo)
            self._unit_combo = combo

        container = QWidget(self)
        container.setObjectName("paramEditorRow")
        container.setLayout(row)
        layout.addWidget(container)
        self._editor_row_host = container
        return editor

    def _on_unit_changed(self) -> None:
        """Adopt the newly chosen unit: relabel any per-configuration rows, re-preview.

        Like the single-value path, changing the unit **reinterprets** what is typed
        rather than converting it — the one conversion still happens at the API
        boundary, from the unit reported here.
        """
        if self._per_config is not None:
            self._per_config.set_unit(self._chosen_unit() or "")
        # The tolerance boxes are read in this same unit, so their suffixes move
        # with it. Like the value box, what is already typed is *reinterpreted*
        # in the new unit rather than converted.
        self._sync_tolerance_units()
        self._update_preview()

    # -- multi-configuration mode (§4.2c) -----------------------------------

    def _build_per_configuration_section(self, layout: QVBoxLayout) -> None:
        """The (initially empty, hidden) host for the one-box-per-configuration block.

        Built unconditionally so entering the mode — at open for a configured
        parameter, or on the *Configure across configurations…* click for a shared one —
        is a fill-and-show rather than a re-layout of the whole dialog.
        """
        host = QWidget(self)
        host.setObjectName("paramEditorPerConfig")
        box = QVBoxLayout(host)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        heading = QLabel(PER_CONFIGURATION_HEADING, host)
        heading.setObjectName("geoModeGroupHeading")
        header.addWidget(heading)
        header.addStretch(1)
        box.addLayout(header)

        host.setVisible(False)
        layout.addWidget(host)
        self._per_config_host = host
        self._per_config_box = box
        self._per_config_header = header

    def _build_configure_affordance(self, layout: QVBoxLayout) -> None:
        """*Configure across configurations…* — the discoverability answer (owner Q3).

        Offered for an editable **shared** parameter whenever the session has a
        document. It is deliberately offered in a single-configuration session too and
        answers there with the 4b hint naming ``Edit → Configurations…``, exactly as the
        context-menu action does — a hidden control cannot teach the analyst that the
        capability exists (Rule 17's spirit for UI state).
        """
        self._configure_button: QPushButton | None = None
        self._configure_hint: QLabel | None = None
        scope = self._scope
        if scope is None or not scope.can_commit or self._read_only or self._opened_configured:
            return

        row = QHBoxLayout()
        row.setSpacing(8)
        button = QPushButton(CONFIGURE_TEXT, self)
        button.setObjectName("paramEditorConfigureButton")
        button.setToolTip(
            "Give this parameter its own value in every configuration, then set them all here."
            if scope.is_multi()
            else SINGLE_CONFIGURATION_HINT
        )
        button.clicked.connect(self._on_configure_clicked)
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)

        hint = QLabel("", self)
        hint.setObjectName("paramEditorConfigureHint")
        hint.setWordWrap(True)
        hint.setVisible(False)
        layout.addWidget(hint)

        self._configure_button = button
        self._configure_hint = hint

    def _on_configure_clicked(self) -> None:
        """Stage a configure and expand into per-configuration boxes (nothing committed).

        The parameter becomes configured only on **Apply**, as one atomic
        ``configure(dotpath, values, unit=)`` call — so Cancel leaves it shared and
        untouched, and one undo reverses the whole promotion. A single-configuration
        session gets the actionable hint instead, and nothing expands.
        """
        scope = self._scope
        if scope is None:
            return
        if not scope.is_multi():
            if self._configure_hint is not None:
                self._configure_hint.setText(SINGLE_CONFIGURATION_HINT)
                self._configure_hint.setVisible(True)
            return
        # Seed every configuration from what the editor currently holds — already in
        # the dialog's display unit, so the block must not convert it a second time.
        seed = self._editor_value()
        self._staged_configure = True
        self._enter_per_configuration([seed] * len(scope.names()), self._display_unit)
        if self._configure_button is not None:
            self._configure_button.setVisible(False)
        if self._configure_hint is not None:
            self._configure_hint.setVisible(False)

    def _enter_per_configuration(self, values: Any, source_unit: str) -> None:
        """Swap the single value box for one box per configuration, seeded from *values*."""
        scope = self._scope
        if scope is None:
            return
        block = PerConfigurationValues(
            self._pdef,
            scope.names(),
            list(values),
            self._display_unit,
            self._per_config_host,
            source_unit=source_unit,
        )
        block.valueChanged.connect(self._update_preview)
        self._per_config_box.addWidget(block)
        self._per_config = block

        # The unit selector governs the whole column (one schema entry, one dimension),
        # so it moves up beside the heading rather than being duplicated per row.
        if self._unit_combo is not None:
            self._per_config_header.addWidget(self._unit_combo)
        self._editor_row_host.setVisible(False)
        self._per_config_host.setVisible(True)
        if self._tol_shared_note is not None:
            self._tol_shared_note.setVisible(True)
        if not self._staged_configure:
            self._current_label.setText(scope.summary(self._dotpath))

    def _write_unit(self) -> str | None:
        """The unit to hand the API for a column write (``None`` = schema input unit)."""
        unit = self._chosen_unit()
        if not unit or unit == (self._pdef.input_unit or ""):
            return None
        return unit

    def _size_combo_popup(self, combo: QComboBox) -> None:
        """Size the unit combo + its popup to its widest item (owner punch-list item 1).

        The default popup clipped unit names to ~2 characters ("cr", "kı"): the view had
        no explicit width and Qt sized it to the collapsed box. ``AdjustToContents``
        sizes the collapsed control, and a view minimum width taken from the font
        metrics of the widest item (plus a scrollbar/margin allowance) guarantees the
        dropdown shows every unit in full. Width is layout geometry, not a design token,
        so it lives here; all colour/border still comes from the QSS theme.
        """
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        metrics = combo.fontMetrics()
        widest = max(
            (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
            default=0,
        )
        combo.view().setMinimumWidth(widest + _COMBO_POPUP_PADDING_PX)

    def _make_value_editor(self) -> QWidget:
        """Build the editor the parameter's dtype/enum calls for, seeded with its value.

        A numeric editor is seeded in the dialog's **display unit** so entry and display
        stay symmetric (owner feedback 2026-07-13): open a 500 km altitude and the field
        shows ``500`` with the unit combo on ``km``. Enum/bool/str carry no unit, so
        their seed is the raw input value.
        """
        pdef = self._pdef
        current = (
            self._current_display_value()
            if pdef.dtype in (float, int)
            else (self._current_input_value())
        )

        if pdef.enum_values is not None:
            combo = QComboBox(self)
            combo.addItems(list(pdef.enum_values))  # choices are schema-sourced
            pos = combo.findText("" if current is None else str(current))
            combo.setCurrentIndex(max(pos, 0))
            return combo
        if pdef.dtype is bool:
            check = QCheckBox(self)
            check.setChecked(bool(current))
            check.toggled.connect(self._update_preview)
            return check
        if pdef.dtype is int:
            spin = QSpinBox(self)
            if pdef.bounds is not None:
                lo, hi = pdef.bounds
                spin.setRange(int(lo), int(hi))
            else:
                spin.setRange(_INT_MIN, _INT_MAX)
            spin.setValue(int(current) if current is not None else 0)
            spin.valueChanged.connect(self._update_preview)
            return spin
        # float or free string: a permissive line edit (the API validates on commit).
        line = QLineEdit(self)
        line.setText("" if current is None else str(current))
        line.textChanged.connect(self._update_preview)
        return line

    def _build_preview(self, layout: QVBoxLayout) -> None:
        """The resulting canonical value (the "8 km → 8000 m" confirmation)."""
        preview = QLabel(_PREVIEW_UNSET, self)
        preview.setObjectName("paramEditorPreview")
        preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Only meaningful when a unit conversion is in play (numeric params); for
        # enum/bool/str the canonical value equals the input, so hide the row.
        preview.setVisible(self._unit_combo is not None)
        layout.addWidget(preview)
        self._preview_label = preview

    def _build_error_area(self, layout: QVBoxLayout) -> None:
        """The inline, themed what/why/action area (hidden until a rejected Apply)."""
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
        """Apply (keep open) + Apply & Close for editable params; Close for read-only."""
        buttons = QDialogButtonBox(self)
        if self._read_only:
            close = buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
            close.clicked.connect(self.reject)
        else:
            cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
            cancel.clicked.connect(self.reject)
            self._apply_button: QPushButton = buttons.addButton(
                "Apply", QDialogButtonBox.ButtonRole.ApplyRole
            )
            self._apply_button.clicked.connect(lambda: self.apply(close=False))
            self._apply_close_button: QPushButton = buttons.addButton(
                "Apply && Close", QDialogButtonBox.ButtonRole.AcceptRole
            )
            self._apply_close_button.clicked.connect(lambda: self.apply(close=True))
        layout.addWidget(buttons)
        self._buttons = buttons

    # -- info rendering -----------------------------------------------------

    def _bounds_text(self) -> str:
        """Bounds row text in the current display unit (falls back to input unit)."""
        lo, hi = self._pdef.bounds  # type: ignore[misc]  # caller guards bounds is not None
        # Bounds are declared in input_unit; show them in the display unit too when
        # soundly convertible (owner feedback 2026-07-13), else in the input unit.
        lo_d, hi_d = self._to_display(lo), self._to_display(hi)
        return f"{lo_d:g} – {hi_d:g} {self._display_unit}".rstrip()

    def _reexpress_in_unit(self, unit: str | None, provenance: str | None) -> None:
        """Adopt *unit* as the dialog's display unit and re-render the info rows.

        After Apply-without-close the editor + combo already hold the value in the
        chosen unit; this re-expresses the informative Current and Bounds rows in the
        same unit so the whole dialog agrees (CU-111). A no-unit param is unchanged.
        """
        if unit is None or unit == self._display_unit:
            self._render_current(provenance)
            return
        self._display_unit = self._sound_display_unit(unit)
        self._render_current(provenance)
        if self._bounds_label is not None:
            self._bounds_label.setText(self._bounds_text())

    def _render_current(self, provenance: str | None) -> None:
        """Set the Current row to ``<value> <unit>  ·  <provenance>`` (⚡ if derived).

        The value shows in the dialog's **display unit** (owner feedback 2026-07-13) so
        an altitude the user set as 500 km reads ``500 km``, not ``500000 m``.
        """
        value_text = format_value(self._current_display_value(), self._display_unit)
        if self._read_only:
            value_text = f"{DERIVED_BADGE} {value_text}"
        label = provenance_label(provenance)
        self._current_label.setText(f"{value_text}  ·  {label}" if label else value_text)

    def _add_row(self, form: QFormLayout, label: str, field: QWidget) -> None:
        """Add one ``key → field`` row (key styled as the shared muted dialog key)."""
        key = QLabel(label, self)
        key.setObjectName("errorDialogKey")
        form.addRow(key, field)

    def _value_field(self, text: str) -> QLabel:
        """A selectable, mono value label (shared dialog-value styling)."""
        label = QLabel(text, self)
        label.setObjectName("errorDialogValue")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _on_browse(self) -> None:
        """Native file/directory picker → the value editor (path params only).

        The picker starts at the current value's directory when one is set (so
        re-picking a sibling file is one click), else at the parameter's shipped-data
        default (:func:`default_browse_dir` — e.g. ``data/atmospheres`` for
        ``atmosphere.*``), else the working directory. Cancelling leaves the editor
        untouched; committing still goes through the one validated ``sensor.set`` on
        Apply — the picker only fills the text field.
        """
        editor = self._value_editor
        if not isinstance(editor, QLineEdit):
            return
        current = editor.text().strip()
        if current:
            start = str(Path(current).parent)
        else:
            start = str(default_browse_dir(self._dotpath) or Path.cwd())
        if path_picker_kind(self._dotpath) == "dir":
            chosen = QFileDialog.getExistingDirectory(
                self, f"Choose directory — {self._dotpath}", current or start
            )
        else:
            chosen, _filter = QFileDialog.getOpenFileName(
                self, f"Choose file — {self._dotpath}", start
            )
        if chosen:
            editor.setText(chosen)

    # -- edit / commit ------------------------------------------------------

    # Distribution → its parameter fields. Each dimensional field is entered and
    # shown in the dialog's **display unit** — the same unit the value editor
    # above it is using — and converted to the parameter's input unit at the
    # ``set_tolerance`` boundary (Rule 2: one conversion, at the boundary). The
    # per-field conversion rule lives in :mod:`radiant.gui.tolerance_units`,
    # because a spread and a bound do not transform alike under an affine unit.
    _TOL_FIELDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "gaussian": ("std",),
        "uniform": ("low", "high"),
        "truncated_gaussian": ("std", "low", "high"),
        "log_normal": ("sigma",),
    }

    def _build_tolerance_section(self, layout: QVBoxLayout) -> None:
        """The optional Monte-Carlo tolerance annotation (GT-2)."""
        heading = QLabel("Tolerance (Monte Carlo)", self)
        heading.setObjectName("geoModeGroupHeading")
        layout.addWidget(heading)
        # Only shown in per-configuration mode, where "which configuration does this
        # spread belong to?" is a real question: it belongs to all of them (ADR-0010
        # keeps tolerances on the shared parameter).
        note = QLabel(TOLERANCE_SHARED_NOTE, self)
        note.setObjectName("paramEditorDescription")
        note.setWordWrap(True)
        note.setVisible(False)
        layout.addWidget(note)
        self._tol_shared_note = note
        row_host = QWidget(self)
        row = QHBoxLayout(row_host)
        row.setContentsMargins(0, 0, 0, 0)
        self._tol_distribution = QComboBox(row_host)
        self._tol_distribution.addItems(["none", *self._TOL_FIELDS])
        row.addWidget(self._tol_distribution)
        for key in ("std", "low", "high", "sigma"):
            field = QLineEdit(row_host)
            field.setPlaceholderText(key)
            field.setMaximumWidth(90)
            self._tol_params[key] = field
            row.addWidget(field)
            # The unit this box is read in, stated beside it (owner rule: every
            # number the GUI shows or takes carries its unit). Kept in sync with
            # the value editor's unit combo by _sync_tolerance_units.
            suffix = QLabel("", row_host)
            suffix.setObjectName("paramEditorTolUnit")
            self._tol_units[key] = suffix
            row.addWidget(suffix)
        row.addStretch(1)
        layout.addWidget(row_host)
        self._tol_distribution.currentTextChanged.connect(self._sync_tolerance_fields)

        # Pre-fill from the live sensor's existing tolerance, converting out of
        # the stored input unit into the unit this dialog is displaying in.
        existing = self._sensor.tolerances().get(self._dotpath)
        if existing is not None:
            self._tol_distribution.setCurrentText(existing.distribution)
            for key, value in existing.params.items():
                if key in self._tol_params:
                    shown = self._tolerance_to_display(float(value), key)
                    self._tol_params[key].setText(f"{shown:g}")
        self._sync_tolerance_fields(self._tol_distribution.currentText())

    def _sync_tolerance_fields(self, distribution: str) -> None:
        wanted = set(self._TOL_FIELDS.get(distribution, ()))
        for key, field in self._tol_params.items():
            field.setVisible(key in wanted)
            suffix = self._tol_units.get(key)
            if suffix is not None:
                suffix.setVisible(key in wanted)
        self._sync_tolerance_units()

    def _sync_tolerance_units(self) -> None:
        """Relabel each tolerance box with the unit it is currently read in.

        Follows the value editor's chosen unit, so "30000 m" and a "1000 m"
        spread are stated in the same unit — the operator never converts in
        their head (owner display-unit rule).
        """
        unit = self._tolerance_unit()
        for key, suffix in self._tol_units.items():
            suffix.setText(field_unit_label(key, unit))

    def _tolerance_unit(self) -> str:
        """The unit tolerance entries are interpreted in — the editor's chosen unit."""
        return self._chosen_unit() or self._pdef.input_unit or ""

    def _tolerance_to_display(self, stored: float, field: str) -> float:
        """A stored (input-unit) tolerance *field* re-expressed in the display unit.

        Falls back to the stored number when the registry has no route (the same
        Rule-2 fallback the value editor's display path takes) rather than
        inventing a conversion.
        """
        try:
            return convert_tolerance_value(
                stored,
                field,
                self._pdef.input_unit or "",
                self._tolerance_unit(),
                self._pdef.canonical_unit,
            )
        except KeyError:
            return stored

    def _parse_tolerance(self) -> tuple[Callable[[], None] | None, str | None]:
        """Validate the tolerance section without writing: ``(write, error)`` (CU-219).

        Splitting parse from write is what lets both Apply paths hold to the
        contract every other reject surface keeps — *a rejected Apply changes
        nothing*. The single-value path used to commit the tolerance first, so an
        out-of-bounds value left a Monte-Carlo spread behind for a value that
        never landed, while the dialog said "Rejected".

        Returns ``(None, None)`` when there is no tolerance section or nothing to
        do, ``(callable, None)`` when the entered tolerance is valid and the
        callable performs the single API write, and ``(None, text)`` on rejection.
        All unit conversion happens here, once, at the API boundary (Rule 2) — the
        returned callable only writes.
        """
        if self._tol_distribution is None:
            return None, None
        distribution = self._tol_distribution.currentText()
        if distribution == "none":
            if self._sensor.tolerances().get(self._dotpath) is None:
                return None, None
            dotpath = self._dotpath
            return (lambda: self._sensor.clear_tolerance(dotpath)), None
        entered_unit = self._tolerance_unit()
        try:
            # Entered in the display unit; stored in the parameter's input unit.
            kwargs = {
                key: convert_tolerance_value(
                    float(self._tol_params[key].text()),
                    key,
                    entered_unit,
                    self._pdef.input_unit or "",
                    self._pdef.canonical_unit,
                )
                for key in self._TOL_FIELDS[distribution]
                if self._tol_params[key].text().strip()
            }
            missing = set(self._TOL_FIELDS[distribution]) - set(kwargs)
            if missing:
                return None, f"tolerance {distribution} needs {sorted(missing)}"
        except KeyError:
            return None, (
                f"no registered conversion from {entered_unit!r} to "
                f"{self._pdef.input_unit!r} for this tolerance"
            )
        except (ValueError, RadiantError) as exc:
            return None, str(exc)

        dotpath = self._dotpath

        def _write() -> None:
            self._sensor.set_tolerance(dotpath, distribution, **kwargs)

        return _write, None

    def _apply_tolerance(self) -> str | None:
        """Parse **and** write the tolerance — the pre-CU-219 single-step entry point.

        Retained for the per-configuration path and any caller that has already
        committed its value. New code should prefer :meth:`_parse_tolerance` and
        write only once every input has validated.
        """
        write, error = self._parse_tolerance()
        if error is not None:
            return error
        if write is not None:
            write()
        return None

    def apply(self, close: bool) -> None:
        """Validate on a clone, commit one ``sensor.set`` if accepted, else show error.

        The live sensor is mutated by exactly one ``set`` call, and only for a value the
        API accepts (validation runs first on a throwaway clone, so a rejected value
        never touches the live sensor). Rejections render inline and keep the dialog
        open; an unexpected exception raises a traceback dialog (Rules 15/17). On
        acceptance the tree is refreshed via ``on_committed`` and, when *close* is set,
        the dialog dismisses.
        """
        if self._read_only:
            return
        if self._per_config is not None:
            self._apply_per_configuration(close)
            return
        value = self._editor_value()
        unit = self._chosen_unit()
        canonical, rejection, unexpected = self._try_resolve(value, unit)
        if rejection is not None:
            self._show_error(rejection)
            return
        if unexpected is not None:
            exec_dialog(UnexpectedErrorDialog(unexpected, f"Editing “{self._dotpath}”", self))
            return

        # CU-219: validate the tolerance *before* writing anything. This path used
        # to commit the tolerance first, so an out-of-bounds value left a
        # Monte-Carlo spread behind for a value that never landed while the dialog
        # reported "Rejected" — breaking the contract every other reject surface in
        # the GUI keeps (Rules 15/17). Both inputs are now checked, then both are
        # written, in the same order the per-configuration path uses: value first,
        # tolerance second.
        write_tolerance, tol_error = self._parse_tolerance()
        if tol_error is not None:
            self._show_error(f"Tolerance not applied — {tol_error}")
            return

        # Accepted: the single mandated API call on the live sensor.
        if unit is not None:
            self._sensor.set(self._dotpath, value, unit=unit)
        else:
            self._sensor.set(self._dotpath, value)
        if write_tolerance is not None:
            write_tolerance()

        self._clear_error()
        # Refresh the dialog's own informative readouts (the "after") in the unit the
        # user just chose, so the Current/Bounds rows agree with the combo (CU-111);
        # then let the panel refresh the tree + mark results stale.
        self._reexpress_in_unit(unit, safe_provenance(self._sensor, self._dotpath))
        self._update_preview()
        if self._on_committed is not None:
            # Hand back the chosen unit so the panel adopts it as the row's display
            # unit (owner feedback 2026-07-13): the tree then shows the value in it too.
            self._on_committed(self._dotpath, unit)
        if close:
            self.accept()

    def _apply_per_configuration(self, close: bool) -> None:
        """Commit the whole column (and, if staged, the promotion) in one API call.

        The scope's committer performs exactly one ``ConfigurationSet`` call —
        ``configure(dotpath, values, unit=)`` when this Apply is also the promotion of a
        still-shared parameter, ``set_values(dotpath, values, unit=)`` when the column
        already exists — and records **one** scoped undo step, so undo restores both the
        values and the store they live in. The API validates every value before it
        writes anything, so a rejection (which names the offending configuration) leaves
        the set exactly as it was; it renders inline and the dialog stays open.
        """
        scope = self._scope
        block = self._per_config
        if scope is None or block is None:
            return
        rejection = scope.commit_values(
            self._dotpath,
            block.values(),
            self._write_unit(),
            configure=self._staged_configure,
        )
        if rejection is not None:
            self._show_error(rejection)
            return
        self._staged_configure = False
        self._opened_configured = True

        # Values first, then the (shared, base-level) tolerance: a value rejection must
        # leave the whole action uncommitted, which only holds if nothing precedes it.
        tol_error = self._apply_tolerance()
        if tol_error is not None:
            self._show_error(f"Tolerance not applied — {tol_error}")
            return

        self._clear_error()
        self._current_label.setText(scope.summary(self._dotpath))
        self._update_preview()
        if self._on_committed is not None:
            self._on_committed(self._dotpath, self._chosen_unit())
        if close:
            self.accept()

    def _per_configuration_preview(self) -> str:
        """``= MWIR: 3.5 um · LWIR: 8 um`` — every configuration's **canonical** value.

        The single-value dialog previews one canonical number; with N boxes that line
        would be a lie, so it becomes N named canonical values — what each configuration
        will actually hold once Apply lands. The conversion routes through the public
        registry seam, and a value that cannot yet be resolved (mid-typing, or a
        non-numeric parameter) drops the whole line to the visible not-yet-known state
        rather than showing a partial answer.
        """
        block = self._per_config
        scope = self._scope
        if block is None or scope is None:
            return _PREVIEW_UNSET
        chosen = self._chosen_unit() or ""
        canonical_unit = self._pdef.canonical_unit
        parts: list[str] = []
        for name, value in zip(scope.names(), block.values(), strict=False):
            try:
                canonical = display_in_unit(float(value), chosen, canonical_unit, canonical_unit)
            except (TypeError, ValueError, KeyError):
                return _PREVIEW_UNSET
            parts.append(f"{name}: {format_value(canonical, canonical_unit)}")
        return f"= {_PREVIEW_SEPARATOR.join(parts)}" if parts else _PREVIEW_UNSET

    def _try_resolve(
        self, value: Any, unit: str | None
    ) -> tuple[Any | None, RadiantError | None, BaseException | None]:
        """Resolve *value* on a throwaway clone: ``(canonical, rejection, unexpected)``.

        The clone carries the one ``set`` (with the chosen unit, so the Rule-2
        conversion happens exactly once, inside the API) and a full resolve
        (``get`` forces bounds/enum/consistency validation). A ``RadiantError`` is a
        rejected input; any other exception is an unexpected bug. The live sensor is
        never touched.

        An accepted value is additionally screened by the resolve-time
        target-spec seam (CU-244): a cross-parameter over-specification this
        edit introduces (e.g. a second reflectance surface) is rejected at the
        door with the same what/why/action ``evaluate()`` would produce, via
        the shared differential guard.
        """
        trial = self._sensor.clone()
        try:
            if unit is not None:
                trial.set(self._dotpath, value, unit=unit)
            else:
                trial.set(self._dotpath, value)
            canonical = trial.get(self._dotpath)
        except RadiantError as exc:
            # Differential test (from-scratch bootstrap, 2026-07-17): if the config
            # fails to resolve identically WITHOUT this edit, the failure is the
            # config's incompleteness, not this value — accept the edit (the
            # per-value bounds/enum checks already ran inside set()); Evaluate
            # remains the surface that reports what is still missing. Only a
            # failure this edit *introduces* is a rejection.
            baseline = self._sensor.clone()
            try:
                baseline.get(self._dotpath)
            except RadiantError:
                # Pre-existing incompleteness — but the VALUE itself must still pass
                # the schema checks (Rule 16: a negative aperture is wrong regardless
                # of how incomplete the config is).
                shallow = self._validate_value_shallow(value, unit)
                if shallow is not None:
                    return None, shallow, None
                return None, None, None
            return None, exc, None
        except Exception as exc:  # genuine bug, not a rejected input — never swallow
            return None, None, exc
        conflict = introduced_target_spec_conflict(self._sensor, trial)
        if conflict is not None:
            return None, conflict, None
        return canonical, None, None

    def _validate_value_shallow(self, value: Any, unit: str | None) -> RadiantError | None:
        """Schema-only value check for configs that cannot fully resolve yet.

        Bounds (canonical units, converted once from the chosen/input unit) and
        enum membership — the checks a full resolve would have run for this one
        parameter. Returns the rejection or None.
        """
        pdef = self._pdef
        if pdef.enum_values is not None and value not in pdef.enum_values:
            return ParameterBoundsError(
                what=f"{self._dotpath} = {value!r} is not a valid choice",
                why=f"Allowed values: {', '.join(pdef.enum_values)}.",
                action="Pick one of the listed values.",
                context={"param": self._dotpath, "value": value},
            )
        if pdef.dtype is float and pdef.bounds is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return ParameterBoundsError(
                    what=f"{self._dotpath} = {value!r} is not a number",
                    why="This parameter takes a numeric value.",
                    action="Enter a number.",
                    context={"param": self._dotpath, "value": value},
                )
            # ParameterDef.bounds are in the INPUT unit (Parameter System doc: "the
            # user thinks in input units; validation should too") — convert only when
            # a different display unit was chosen, then compare in input units.
            from_unit = unit or pdef.input_unit
            in_input_unit = numeric
            if from_unit and from_unit != pdef.input_unit:
                in_input_unit = convert(numeric, from_unit, pdef.input_unit)
            lo, hi = pdef.bounds
            if not (lo <= in_input_unit <= hi):
                return ParameterBoundsError(
                    what=(f"{self._dotpath} = {numeric:g} {from_unit or ''} is out of bounds"),
                    why=f"Allowed range: [{lo:g}, {hi:g}] {pdef.input_unit or ''}.",
                    action="Enter a value inside the allowed range.",
                    context={
                        "param": self._dotpath,
                        "value": in_input_unit,
                        "bounds": (lo, hi),
                    },
                )
        return None

    def _update_preview(self) -> None:
        """Recompute the canonical preview for the current editor value + unit.

        Shows ``= <canonical> <unit>`` when the value resolves, or ``= —`` when it
        cannot yet (mid-typing / out of bounds). The em-dash is a visible not-yet-known
        state, not a swallowed failure — Apply is the honest surface that renders the
        actual actionable error (Rule 17).
        """
        if self._unit_combo is None:
            return
        if self._per_config is not None:
            self._preview_label.setText(self._per_configuration_preview())
            return
        canonical, _rejection, _unexpected = self._try_resolve(
            self._editor_value(), self._chosen_unit()
        )
        if canonical is None:
            self._preview_label.setText(_PREVIEW_UNSET)
        else:
            self._preview_label.setText(f"= {format_value(canonical, self._pdef.canonical_unit)}")

    # -- error area ---------------------------------------------------------

    def _show_error(self, exc: RadiantError) -> None:
        """Render the rejection's what/why/action inside the dialog; keep it open."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        what = str(getattr(exc, "what", "") or exc)
        why = str(getattr(exc, "why", "") or "")
        action = str(getattr(exc, "action", "") or "")
        self._add_row(self._error_form, "What", self._value_field(what))
        if why:
            self._add_row(self._error_form, "Why", self._value_field(why))
        if action:
            self._add_row(self._error_form, "Action", self._value_field(action))
        self._error_frame.setVisible(True)

    def _clear_error(self) -> None:
        """Hide the inline error area and drop its fields."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        self._error_frame.setVisible(False)

    # -- value extraction ---------------------------------------------------

    def _current_input_value(self) -> Any:
        """The parameter's resolved input value, or None while the config cannot
        resolve yet (a from-scratch File → New — the dialog must still open so the
        user can enter the very first values; found 2026-07-17)."""
        try:
            return self._sensor.get_input(self._dotpath)
        except (KeyError, RadiantError):
            return None

    def _current_display_value(self) -> Any:
        """The current value re-expressed in the dialog's display unit (owner feedback).

        The input-unit value routed through the public registry seam; the display unit
        was validated at construction, so this cannot raise.
        """
        return self._to_display(self._current_input_value())

    def _to_display(self, input_value: Any) -> Any:
        """Convert an input-unit value to the dialog's display unit (public seam)."""
        return display_in_unit(
            input_value, self._pdef.input_unit, self._display_unit, self._pdef.canonical_unit
        )

    def _sound_display_unit(self, requested: str) -> str:
        """*requested* if it is soundly convertible from the input unit, else input_unit.

        Guards the display path against a one-way / offset unit (e.g. a temperature
        that only registers ``K``): rather than invent a conversion the dialog falls
        back to the parameter's own input unit (Rule 2).
        """
        if requested == self._pdef.input_unit:
            return requested
        try:
            display_in_unit(1.0, self._pdef.input_unit, requested, self._pdef.canonical_unit)
        except KeyError:
            return self._pdef.input_unit
        return requested

    def _editor_value(self) -> Any:
        """Extract the native Python value from the value editor."""
        editor = self._value_editor
        if isinstance(editor, QComboBox):
            return editor.currentText()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QSpinBox):
            return editor.value()
        if isinstance(editor, QLineEdit):
            return editor.text()
        return None

    def _chosen_unit(self) -> str | None:
        """The unit selected in the unit combo, or ``None`` for a non-numeric param."""
        if self._unit_combo is None:
            return None
        return str(self._unit_combo.currentData())

    # -- accessors (tests / host) ------------------------------------------

    @property
    def dotpath(self) -> str:
        """The parameter this dialog edits."""
        return self._dotpath

    @property
    def read_only(self) -> bool:
        """True when the parameter is derived and the dialog opened informative-only."""
        return self._read_only

    @property
    def path_label(self) -> QLabel:
        """The full-dot-path header label (selectable, mono)."""
        return self._path_label

    @property
    def description_label(self) -> QLabel:
        """The schema-description label."""
        return self._description_label

    @property
    def value_editor(self) -> QWidget:
        """The per-dtype value editor widget."""
        return self._value_editor

    @property
    def unit_combo(self) -> QComboBox | None:
        """The unit selector (``None`` for a non-numeric parameter)."""
        return self._unit_combo

    @property
    def browse_button(self) -> QPushButton | None:
        """The Browse… picker button (``None`` for a non-path parameter)."""
        return self._browse_button

    @property
    def preview_label(self) -> QLabel:
        """The canonical-value preview label."""
        return self._preview_label

    @property
    def error_frame(self) -> QFrame:
        """The inline error area (visible only after a rejected Apply)."""
        return self._error_frame

    # -- accessors: multi-configuration mode (§4.2c) ------------------------

    @property
    def per_configuration(self) -> PerConfigurationValues | None:
        """The one-box-per-configuration block, or ``None`` in single-value mode."""
        return self._per_config

    @property
    def configure_button(self) -> QPushButton | None:
        """The *Configure across configurations…* affordance (``None`` when not offered)."""
        return self._configure_button

    @property
    def configure_hint(self) -> QLabel | None:
        """The inline hint the affordance answers with in a single-configuration session."""
        return self._configure_hint

    @property
    def tolerance_note(self) -> QLabel | None:
        """The "tolerances are shared" clarifier (visible only in per-configuration mode)."""
        return self._tol_shared_note


__all__ = [
    "PER_CONFIGURATION_HEADING",
    "TOLERANCE_SHARED_NOTE",
    "ParameterEditorDialog",
    "convertible_units",
    "default_browse_dir",
    "path_picker_kind",
]
