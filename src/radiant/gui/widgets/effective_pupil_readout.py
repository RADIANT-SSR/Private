"""The Transmission tab's **cold stop & effective pupil** strip (Gap 128).

:class:`EffectivePupilReadout` is the compact bottom strip of the Optics **Transmission**
tab. Gap 128 (2026-09-09) deleted per-element near-field geometry and the old
leakage-fraction knobs outright: an element has no near-field geometry of its own, and a
cold stop cannot attenuate in-cone warm-optics emission. What a cold stop *does* is set
the size of the pupil, so the model states it as exactly that — two parameters —

* ``optics.cold_stop_undersize_frac`` (u) — the pupil **diameter** it removes,
  ``D_eff = (1 − u)·D``;
* ``optics.cold_stop_obscuration_ratio`` — the central obscuration the stop itself
  imposes;

— and everything downstream follows from the effective pupil they produce. This strip
puts the two editable parameters beside the four derived quantities they move, so the
operator sees signal and near-field move **together** rather than having to reason about
them on separate screens. The panel is specified by two scenario GUI workflows —
``scenarios/07_karen_test_engineer/7.2_radiometric_calibration/gui_workflow.md`` ("the
effective pupil it produces (D_eff [m], f/#_eff [-], A_collect [m²], Ω_cone [sr]) shown
live") and
``scenarios/10_direction_general/10.1_ground_to_air_mwir_detection/gui_workflow.md``,
which additionally records *why* a vendor "cold shield 90 % efficient" figure has no model
home.

**Read-only values come from the last evaluation, verbatim.** The four derived quantities
are ``stage_outputs["optics"]`` entries rendered through the framework's single
authoritative unit table (:func:`radiant.api.stage_output_units.stage_output_unit`); no
unit maths and no physics happen here (Rules 2/6 — display only). Before the first
evaluation every value reads ``—``: the strip never guesses.

**The two editable rows are the shared :class:`~radiant.gui.widgets.field_row.FieldRow`**,
so they render identically by construction to every other schema-driven field and commit
through exactly one ``sensor.set`` via the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog` (validated on
a throwaway clone first; a rejected value never touches the live sensor).

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour or font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from radiant.api.stage_output_units import stage_output_unit
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text, format_value
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_STAGE: Final[str] = "optics"

_TITLE: Final[str] = "Cold stop & effective pupil"

_HINT: Final[str] = (
    "The cold stop IS the aperture stop (Gap 128): undersizing it shrinks the pupil "
    "diameter, D_eff = (1 − u)·D, and every quantity below follows. A cold stop cannot "
    "attenuate in-cone warm-optics emission, so there is no blocked-fraction knob — a "
    "vendor 'cold shield 90 % efficient' figure has no model home here."
)

# The two editable cold-stop parameters (label, dot-path). Bounds / units / description
# all come from the live schema; only the human label is a literal here (CU-120).
_COLD_STOP_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Cold-stop undersizing u", "optics.cold_stop_undersize_frac"),
    ("Cold-stop obscuration", "optics.cold_stop_obscuration_ratio"),
)

# The derived effective-pupil quantities (label, stage-output key), in the reading order
# the scenario workflows state: the diameter the stop leaves, the working f-number it
# implies, the area that collects, and the cone every warm element is seen through.
_DERIVED: Final[tuple[tuple[str, str], ...]] = (
    ("D_eff", "D_eff_m"),
    ("f/#_eff", "f_number_eff"),
    ("A_collect", "A_collect"),
    ("Ω_cone", "Omega_cone"),
)

_DERIVED_TOOLTIPS: Final[dict[str, str]] = {
    "D_eff_m": "Effective pupil diameter D_eff = (1 − u)·D — what the cold stop leaves.",
    "f_number_eff": "Working f-number N_eff = f / D_eff — the cone the focal plane sees.",
    "A_collect": "Clear collecting area of the effective pupil (obscuration removed).",
    "Omega_cone": (
        "Étendue acceptance cone Ω_cone — the only near-field geometry (Gap 128). "
        "Every in-beam warm element is seen through this one cone."
    ),
}

# A dimensionless derived value still carries a unit token: the scenario workflows spell
# it "[-]", and an unannotated number on this strip would be the one value the operator
# has to infer (the units-on-every-value hard rule).
_DIMENSIONLESS: Final[str] = "[-]"


class EffectivePupilReadout(QWidget):
    """The cold-stop parameters + the effective pupil they produce, in one strip.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted cold-stop edit, so the host
        debounces a re-evaluation and this strip's derived values refresh — the same
        contract as every other Inputs form.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("effectivePupilReadout")

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
        for label, dotpath in _COLD_STOP_FIELDS:
            row = FieldRow(dotpath, label, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

        derived_heading = QLabel("Effective pupil (from the last evaluation)", card)
        derived_heading.setObjectName("geoModeGroupHeading")
        box.addWidget(derived_heading)

        grid_host = QWidget(card)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 1)
        self._value_labels: dict[str, QLabel] = {}
        for index, (label, key) in enumerate(_DERIVED):
            name = QLabel(label, grid_host)
            name.setObjectName("outputsRowLabel")
            value = QLabel(_UNSET, grid_host)
            value.setObjectName("outputsRowValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            tooltip = _DERIVED_TOOLTIPS.get(key, "")
            if tooltip:
                name.setToolTip(tooltip)
                value.setToolTip(tooltip)
            grid.addWidget(name, index, 0)
            grid.addWidget(value, index, 1)
            self._value_labels[key] = value
        box.addWidget(grid_host)

        hint = QLabel(_HINT, card)
        hint.setObjectName("stageCenterNote")
        hint.setWordWrap(True)
        box.addWidget(hint)

        layout.addWidget(card)

    # -- binding / refresh ----------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* + shared display-unit store, then re-read the fields.

        The derived values are **not** cleared here: they belong to the last evaluation and
        are replaced by :meth:`populate` when the next one lands.
        """
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read the two editable cold-stop fields from the bound sensor."""
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))

    def _value_text(self, dotpath: str) -> str:
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, dotpath, self._display_units)

    def populate(self, stage_outputs: Mapping[str, Any]) -> None:
        """Render the derived effective-pupil values from ``stage_outputs['optics']``.

        Values are read verbatim and formatted with the framework's unit for the key; a
        key the stage did not publish stays at ``—`` rather than being guessed.
        """
        for _label, key in _DERIVED:
            value = stage_outputs.get(key)
            self._value_labels[key].setText(self._format(key, value))

    @staticmethod
    def _format(key: str, value: Any) -> str:
        """``value`` with its unit — ``[-]`` for the dimensionless ones, ``—`` if absent."""
        if value is None:
            return _UNSET
        unit = stage_output_unit(_STAGE, key)
        return format_value(value, unit) if unit else f"{format_value(value, '')} {_DIMENSIONLESS}"

    # -- editing (the shared Parameter Editor + reject discipline) -------------

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

    # -- accessors (tests) ----------------------------------------------------

    def field_dotpaths(self) -> tuple[str, ...]:
        """The cold-stop parameter dot-paths this strip edits, in order."""
        return tuple(self._rows)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the cold-stop field for *dotpath*."""
        return self._rows[dotpath].value_text()

    def row(self, dotpath: str) -> FieldRow:
        """The :class:`FieldRow` for *dotpath* (KeyError if unknown)."""
        return self._rows[dotpath]

    def derived_keys(self) -> tuple[str, ...]:
        """The stage-output keys rendered in the derived grid, in order."""
        return tuple(key for _label, key in _DERIVED)

    def derived_text(self, key: str) -> str:
        """The rendered 'value + unit' text for a derived *key* (tests)."""
        return self._value_labels[key].text()


__all__ = ["EffectivePupilReadout"]
