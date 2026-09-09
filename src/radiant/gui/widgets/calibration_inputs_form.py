"""The Calibration stage's **Inputs** section — scheme, cal points, drift, source.

:class:`CalibrationInputsForm` is the *Inputs* section of the Calibration stage's
contextual center (Gap 120, plan Phase 3; the screen the stage was minted for —
ADR-0012 §"one namespace, one screen"). The form leads with the **scheme
selector** (``calibration.scheme`` — the card that steers what the rest of the
screen means, the same rationale as the Geometry scene-class card and the Gap 117
readout-architecture selector), then shows the scheme's knobs grouped by physics:
cal points, NUC residual, drift-since-cal, cal-source uncertainty, and absolute
gain uncertainty.

**Scheme-contextual visibility (the Gap 117 convention).** ``none`` shows only
the selector — the model is off and today's PRNU/DSNU behavior applies, stated in
the stage note rather than by a wall of inert rows. ``one_point`` shows the
single cal point + drift + source + gain groups. ``two_point`` adds the upper
cal point and the nonlinearity dispersion (the quadratic-residual knob is
meaningless under offset-only correction). Unlike the readout architecture
switch, a scheme switch strands no rejected parameters — inactive knobs are
simply unused, so there are no companion resets (``architecture_switch.py`` has
no calibration sibling by design, not omission).

**Sentinel rendering.** The cal temperatures use the 0.0-unset sentinel
(schema); an unset cal point renders as words ("unset — required"), never as a
legitimate-looking "0 K" — the Gap 117 second-pass live-review lesson applied
from birth.

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is the
shared :class:`~radiant.gui.widgets.field_row.FieldRow` editing through the
shared :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`
(clone-validate commit, one ``sensor.set``, rejected values never touch the live
sensor), values in the row's session display unit (hours for time-since-cal —
entry/display symmetric). Each accepted edit re-emits :attr:`parameterEdited` so
the host re-evaluates and the Outputs readout + noise budget refresh
(edit-and-watch). All colour/typography from the QSS theme via object names; one
widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_TITLE: Final[str] = "Calibration inputs"

# (label, dot-path) manifests — labels + grouping are the only literals here;
# bounds/units/descriptions come from the live schema (CU-120 convention).
_SCHEME_FIELDS: Final[tuple[tuple[str, str], ...]] = (("Scheme", "calibration.scheme"),)

_CAL_POINT_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Cal point (low)", "calibration.cal_temp_low_K"),
    ("Cal point (mid)", "calibration.cal_temp_mid_K"),
    ("Cal point (high)", "calibration.cal_temp_high_K"),
)

_NUC_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Nonlinearity dispersion", "calibration.nonlinearity_pct"),
)

_DRIFT_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Time since cal", "calibration.time_since_cal_s"),
    ("Gain drift rate", "calibration.gain_drift_frac_per_s"),
    ("Offset drift rate", "calibration.offset_drift_e_per_s"),
)

_SOURCE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Source emissivity", "calibration.source_emissivity"),
    ("Source uniformity (1σ)", "calibration.source_uniformity_K"),
    ("Source ΔT (1σ)", "calibration.source_temp_uncertainty_K"),
    ("Source Δε (1σ)", "calibration.source_emissivity_uncertainty"),
)

_GAIN_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Gain uncertainty (1σ)", "calibration.gain_uncertainty_pct"),
)

_SCHEME_HEADING = "Calibration scheme"
_CAL_POINT_HEADING = "Cal points"
_NUC_HEADING = "NUC residual"
_DRIFT_HEADING = "Drift since cal"
_SOURCE_HEADING = "Cal source (bias budget)"
_GAIN_HEADING = "Absolute gain (bias budget)"

#: Rows visible per scheme (beyond the always-visible selector).
_TWO_POINT_ONLY: Final[tuple[str, ...]] = (
    "calibration.cal_temp_high_K",
    "calibration.nonlinearity_pct",
)
#: The middle cal point exists only under three_point (Gap 122 item 2).
_THREE_POINT_ONLY: Final[tuple[str, ...]] = ("calibration.cal_temp_mid_K",)


class CalibrationInputsForm(QWidget):
    """The Calibration inputs card: schema-driven :class:`FieldRow` per knob.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit — the same contract
        as every other stage-inputs form.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("calibrationInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, card)
        title.setObjectName("geoModeFamilyTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._rows: dict[str, FieldRow] = {}
        self._headings: dict[str, QLabel] = {}
        self._add_group(box, card, _SCHEME_HEADING, _SCHEME_FIELDS)
        self._add_group(box, card, _CAL_POINT_HEADING, _CAL_POINT_FIELDS)
        self._add_group(box, card, _NUC_HEADING, _NUC_FIELDS)
        self._add_group(box, card, _DRIFT_HEADING, _DRIFT_FIELDS)
        self._add_group(box, card, _SOURCE_HEADING, _SOURCE_FIELDS)
        self._add_group(box, card, _GAIN_HEADING, _GAIN_FIELDS)

        layout.addWidget(card)

    def _add_group(
        self,
        box: QVBoxLayout,
        card: QWidget,
        heading: str,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        """Add a titled sub-group (a heading over its :class:`FieldRow`s)."""
        label = QLabel(heading, card)
        label.setObjectName("geoModeGroupHeading")
        box.addWidget(label)
        self._headings[heading] = label
        for text, dotpath in fields:
            row = FieldRow(dotpath, text, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh."""
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field from the bound sensor and re-apply visibility."""
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))
        self._apply_scheme_visibility()

    def _scheme(self) -> str:
        """The resolved calibration scheme ('none' when unbound/unresolved)."""
        if self._sensor is None:
            return "none"
        try:
            return str(self._sensor.get("calibration.scheme"))
        except Exception:  # unresolved sensor — keep the model-off view
            return "none"

    def _apply_scheme_visibility(self) -> None:
        """Show only the groups meaningful under the current scheme.

        ``none``: selector only (the stage note says why the card is quiet).
        ``one_point``: everything except the upper/mid cal points and the
        nonlinearity dispersion (multi-point-only physics). ``two_point``:
        all but the mid point. ``three_point``: all (Gap 122 item 2).
        """
        scheme = self._scheme()
        active = scheme != "none"
        for heading in (
            _CAL_POINT_HEADING,
            _NUC_HEADING,
            _DRIFT_HEADING,
            _SOURCE_HEADING,
            _GAIN_HEADING,
        ):
            self._headings[heading].setVisible(active)
        for dotpath, row in self._rows.items():
            if dotpath == "calibration.scheme":
                continue
            row.setVisible(active)
        if active and scheme == "one_point":
            self._headings[_NUC_HEADING].setVisible(False)
            for dotpath in _TWO_POINT_ONLY + _THREE_POINT_ONLY:
                self._rows[dotpath].setVisible(False)
        if active and scheme == "two_point":
            for dotpath in _THREE_POINT_ONLY:
                self._rows[dotpath].setVisible(False)

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset).

        The cal temperatures use the 0.0-unset sentinel (schema): an unset cal
        point renders as words, never as a legitimate-looking "0 K".
        """
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        if dotpath in ("calibration.cal_temp_low_K", "calibration.cal_temp_high_K"):
            try:
                unset = float(sensor.get(dotpath)) <= 0.0
            except (RadiantError, KeyError):
                unset = False
            if unset:
                return "unset — required"
        return field_display_text(sensor, dotpath, self._display_units)

    # -- editing (reuses the Parameter Editor dialog + reject discipline) ----

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

    # -- accessors (tests) --------------------------------------------------

    def field_dotpaths(self) -> tuple[str, ...]:
        """The parameter dot-paths this form edits, in order."""
        return tuple(self._rows)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the field for *dotpath*."""
        return self._rows[dotpath].value_text()

    def row(self, dotpath: str) -> FieldRow:
        """The :class:`FieldRow` for *dotpath* (KeyError if unknown)."""
        return self._rows[dotpath]


__all__ = ["CalibrationInputsForm"]
