"""The Detector stage's **Inputs** section — editable schema-driven detector fields.

:class:`DetectorInputsForm` is the *Inputs* section of the Detector stage's contextual
center (arch doc §4.4 section 1, GUI plan Phase PS-3): the key detector parameters —
quantum efficiency, dark rate, the cross/along-track pixel pitch, the fill factor, and the
detector operating temperature — as editable schema-driven rows. It is the detector sibling
of :class:`~radiant.gui.widgets.optics_inputs_form.OpticsInputsForm`: edit an input and watch
the Detector instrument respond — editing the dark rate shifts the noise pie (a new
``dark_shot`` variance share), editing the pixel pitch redraws the detector illustration and
the PSF pixel-grid overlay (a wider pixel samples the PSF differently).

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface; editing a field
opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first (a rejected value never
touches the live sensor; the actionable what/why/action shows inline) — the identical
edit+reject discipline as the parameter tree (Phase 2), the Geometry Inputs form (Phase 5),
the Source Inputs form (Phase PS-1), and the Optics Inputs form (Phase PS-2). The value shows
in the row's **display unit**, sharing the parameter panel's session display-unit store so a
unit chosen on any surface agrees. Each accepted edit re-emits :attr:`parameterEdited`, so the
host debounces a full re-evaluation and every Detector diagnostic + the Outputs readout refresh
(edit-and-watch).

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow` — the same building
block every other schema-driven field uses — so the Detector inputs render **identically by
construction** to every other field (owner hard rule). All colour/typography comes from the QSS
theme via object names (GUI plan §4.9); this file holds no colour/font literal. One widget class
per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The key detector parameters (label, dot-path), grouped as detection efficiency (QE),
# dark generation, pixel geometry (cross/along-track pitch + fill factor), and the
# operating temperature. Bounds/units/description all come from the live schema (never
# transcribed) — only the human label + the grouping is a literal here (CU-120, tracked
# with the geometry/source/optics manifests).
_DETECTOR_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Quantum efficiency", "detector.qe_value"),
    ("Dark rate", "detector.dark_rate_e_per_s"),
    ("Pixel pitch x (cross-track)", "detector.pixel_pitch_x_um"),
    ("Pixel pitch y (along-track)", "detector.pixel_pitch_y_um"),
    ("Fill factor", "detector.fill_factor"),
    ("Detector temperature", "detector.detector_temperature_K"),
)

_TITLE = "Detector — quantum efficiency, dark rate, pixel geometry, temperature"


class DetectorInputsForm(QWidget):
    """The Detector inputs card: schema-driven :class:`FieldRow` per key detector parameter.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract as
        :attr:`OpticsInputsForm.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detectorInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # One ``geoModeFamily`` card (same object name → same QSS as every geometry/source/
        # optics card), so the Detector inputs sit in an identically-styled card.
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
        for label, dotpath in _DETECTOR_FIELDS:
            row = FieldRow(dotpath, label, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

        layout.addWidget(card)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the parameter panel's session display-unit dict (shared by
        reference), so a unit chosen on any surface reflects here. A ``None`` sensor blanks
        every field (the pre-config state).
        """
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field's value+unit text from the bound sensor (— if no sensor)."""
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
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
        dialog.exec()

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


__all__ = ["DetectorInputsForm"]
