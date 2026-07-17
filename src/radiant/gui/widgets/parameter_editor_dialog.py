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
from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from radiant.api.units import _CONVERSIONS
from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterBoundsError
from radiant.core.units import convert
from radiant.gui.param_format import (
    DERIVED_BADGE,
    display_in_unit,
    format_value,
    is_derived,
    provenance_label,
    safe_provenance,
)
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor
    from radiant.core.parameters import ParameterDef

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


def convertible_units(canonical_unit: str, input_unit: str) -> list[str]:
    """Units the registry can convert to *canonical_unit* (public-seam enumeration).

    Reads the conversion registry through the public :mod:`radiant.api.units` seam
    (the same surface the ``radiant convert`` CLI lists targets from) and returns every
    source unit ``u`` for which ``convert(x, u, canonical_unit)`` is registered — i.e.
    every unit the user may legally enter a value in for this parameter. The
    parameter's own ``input_unit`` and ``canonical_unit`` are always included (both are
    always legal), so the list is never empty even for a single-unit dimension.
    """
    units = {frm for (frm, to) in _CONVERSIONS if to == canonical_unit}
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
    """

    def __init__(
        self,
        sensor: Sensor,
        dotpath: str,
        on_committed: Callable[[str, str | None], None] | None = None,
        parent: QWidget | None = None,
        display_unit: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._sensor = sensor
        self._dotpath = dotpath
        self._on_committed = on_committed
        self._pdef: ParameterDef = sensor.parameter_def(dotpath)
        # The unit the Current line / editor / bounds open displayed in. Validated for
        # sound convertibility (falls back to input_unit) so no downstream conversion
        # can raise. Only meaningful for numeric params; "" for the rest.
        self._display_unit: str = self._sound_display_unit(display_unit or self._pdef.input_unit)

        # Read-only when the value is derived from a consistency group (⚡): the dialog
        # opens informative but the editors stay disabled (arch doc §4.3, Rule 4).
        provenance = safe_provenance(sensor, dotpath)
        self._read_only = is_derived(provenance)

        self.setObjectName("parameterEditorDialog")
        self.setWindowTitle(f"Edit — {dotpath}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        self._build_header(layout)
        self._build_info(layout, provenance)
        self._value_editor: QWidget = self._build_editor_row(layout)
        # GT-2 tolerance annotation — placed BELOW the main value (owner request
        # 2026-07-17): the value is the headline, the Monte-Carlo spread annotates it.
        self._tol_distribution: QComboBox | None = None
        self._tol_params: dict[str, QLineEdit] = {}
        if self._pdef.dtype is float and not self._read_only:
            self._build_tolerance_section(layout)
        self._build_preview(layout)
        self._build_error_area(layout)
        self._build_buttons(layout)

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

        if self._pdef.bounds is not None:
            lo, hi = self._pdef.bounds
            # Bounds are declared in input_unit; show them in the display unit too when
            # soundly convertible (owner feedback 2026-07-13), else in the input unit.
            lo_d, hi_d = self._to_display(lo), self._to_display(hi)
            bounds_text = f"{lo_d:g} – {hi_d:g} {self._display_unit}".rstrip()
            self._add_row(form, "Bounds", self._value_field(bounds_text))

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
            combo.currentIndexChanged.connect(self._update_preview)
            self._size_combo_popup(combo)
            row.addWidget(combo)
            self._unit_combo = combo

        container = QWidget(self)
        container.setObjectName("paramEditorRow")
        container.setLayout(row)
        layout.addWidget(container)
        return editor

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

    # -- edit / commit ------------------------------------------------------

    # Distribution → its parameter fields (labels carry units: absolute spreads are
    # in the parameter's input unit; fractions are of nominal).
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
        row.addStretch(1)
        layout.addWidget(row_host)
        self._tol_distribution.currentTextChanged.connect(self._sync_tolerance_fields)

        # Pre-fill from the live sensor's existing tolerance, if any.
        existing = self._sensor.tolerances().get(self._dotpath)
        if existing is not None:
            self._tol_distribution.setCurrentText(existing.distribution)
            for key, value in existing.params.items():
                if key in self._tol_params:
                    self._tol_params[key].setText(f"{value:g}")
        self._sync_tolerance_fields(self._tol_distribution.currentText())

    def _sync_tolerance_fields(self, distribution: str) -> None:
        wanted = set(self._TOL_FIELDS.get(distribution, ()))
        for key, field in self._tol_params.items():
            field.setVisible(key in wanted)

    def _apply_tolerance(self) -> str | None:
        """Commit the tolerance section (one API call); returns an error text or None."""
        if self._tol_distribution is None:
            return None
        distribution = self._tol_distribution.currentText()
        existing = self._sensor.tolerances().get(self._dotpath)
        if distribution == "none":
            if existing is not None:
                self._sensor.clear_tolerance(self._dotpath)
            return None
        try:
            kwargs = {
                key: float(self._tol_params[key].text())
                for key in self._TOL_FIELDS[distribution]
                if self._tol_params[key].text().strip()
            }
            missing = set(self._TOL_FIELDS[distribution]) - set(kwargs)
            if missing:
                return f"tolerance {distribution} needs {sorted(missing)}"
            self._sensor.set_tolerance(self._dotpath, distribution, **kwargs)
        except (ValueError, RadiantError) as exc:
            return str(exc)
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
        value = self._editor_value()
        unit = self._chosen_unit()
        canonical, rejection, unexpected = self._try_resolve(value, unit)
        if rejection is not None:
            self._show_error(rejection)
            return
        if unexpected is not None:
            UnexpectedErrorDialog(unexpected, f"Editing “{self._dotpath}”", self).exec()
            return

        tol_error = self._apply_tolerance()
        if tol_error is not None:
            self._show_error(f"Tolerance not applied — {tol_error}")
            return

        # Accepted: the single mandated API call on the live sensor.
        if unit is not None:
            self._sensor.set(self._dotpath, value, unit=unit)
        else:
            self._sensor.set(self._dotpath, value)

        self._clear_error()
        # Refresh the dialog's own informative readouts (the "after"), then let the
        # panel refresh the tree + mark results stale.
        self._render_current(safe_provenance(self._sensor, self._dotpath))
        self._update_preview()
        if self._on_committed is not None:
            # Hand back the chosen unit so the panel adopts it as the row's display
            # unit (owner feedback 2026-07-13): the tree then shows the value in it too.
            self._on_committed(self._dotpath, unit)
        if close:
            self.accept()

    def _try_resolve(
        self, value: Any, unit: str | None
    ) -> tuple[Any | None, RadiantError | None, BaseException | None]:
        """Resolve *value* on a throwaway clone: ``(canonical, rejection, unexpected)``.

        The clone carries the one ``set`` (with the chosen unit, so the Rule-2
        conversion happens exactly once, inside the API) and a full resolve
        (``get`` forces bounds/enum/consistency validation). A ``RadiantError`` is a
        rejected input; any other exception is an unexpected bug. The live sensor is
        never touched.
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
    def preview_label(self) -> QLabel:
        """The canonical-value preview label."""
        return self._preview_label

    @property
    def error_frame(self) -> QFrame:
        """The inline error area (visible only after a rejected Apply)."""
        return self._error_frame


__all__ = ["ParameterEditorDialog", "convertible_units"]
