"""The Platform stage's **Inputs** section — the v1-minimal jitter + smear knobs.

:class:`PlatformInputsForm` is the *Inputs* section of the Platform stage's contextual
center (arch doc §4.4 section 1, GUI plan Phase PS-5 — v1-minimal). The Platform stage is
v1-minimal (owner-ratified: it needs **no** dedicated MTF view; the smear/jitter MTF terms
remain in the Optics/Performance overlays), so the instrument is deliberately small: the
platform-dynamics parameters that drive the jitter and smear kernels — the jitter RMS
(isotropic + the anisotropic cross/along-track pair) and the linear-motion smear inputs
(ground velocity + the direct focal-plane smear length) — as editable schema-driven rows. It
is the platform sibling of :class:`~radiant.gui.widgets.detector_inputs_form.DetectorInputsForm`:
edit a jitter/smear input and watch the Platform outputs (``jitter_sigma_x_m``,
``smear_width_m``, ``EE_box``) respond on the next evaluation.

**The jitter / motion grouping.** The three jitter knobs sit under a **Jitter** heading and
the two smear knobs under a **Motion & smear** heading — a presentation choice only, no schema
change (the sensor paths stay ``platform.jitter_*`` / ``platform.ground_velocity_m_s`` /
``platform.smear_length_um``), mirroring the Spectral-Integration form's *Filter bandpass* /
*Acquisition* grouping.

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface; editing a field
opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first (a rejected value never
touches the live sensor; the actionable what/why/action shows inline) — the identical
edit+reject discipline as the parameter tree (Phase 2), the Geometry Inputs form (Phase 5),
and the Source / Optics / Detector / Spectral-Integration Inputs forms (Phases PS-1..4). The
value shows in the row's **display unit**, sharing the parameter panel's session display-unit
store so a unit chosen on any surface agrees. Each accepted edit re-emits
:attr:`parameterEdited`, so the host debounces a full re-evaluation and the Outputs readout
refreshes (edit-and-watch).

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow` — the same
building block every other schema-driven field uses — so these inputs render **identically
by construction** to every other field (owner hard rule). All colour/typography comes from
the QSS theme via object names (GUI plan §4.9); this file holds no colour/font literal. One
widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The jitter knobs (label, dot-path). Bounds/units/description all come from the live schema
# (never transcribed) — only the human label + the grouping is a literal here (CU-120,
# tracked with the geometry/source/optics/detector/spectral manifests).
_JITTER_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Jitter RMS (isotropic)", "platform.jitter_rms_urad"),
    ("Jitter RMS x (cross-track)", "platform.jitter_rms_x_urad"),
    ("Jitter RMS y (along-track)", "platform.jitter_rms_y_urad"),
)

# The linear-motion smear knobs (velocity-based + direct focal-plane length).
_MOTION_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Ground velocity", "platform.ground_velocity_m_s"),
    ("Smear length (focal-plane)", "platform.smear_length_um"),
)

_TITLE = "Platform — jitter & smear (v1-minimal)"
_JITTER_HEADING = "Jitter"
_MOTION_HEADING = "Motion & smear"


class PlatformInputsForm(QWidget):
    """The Platform inputs card: schema-driven :class:`FieldRow` per jitter/smear knob.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract as
        :attr:`DetectorInputsForm.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("platformInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # One ``geoModeFamily`` card (same object name → same QSS as every geometry/source/
        # optics/detector/spectral card), so these inputs sit in an identically-styled card.
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
        self._add_group(box, card, _JITTER_HEADING, _JITTER_FIELDS)
        self._add_group(box, card, _MOTION_HEADING, _MOTION_FIELDS)

        layout.addWidget(card)

    def _add_group(
        self,
        box: QVBoxLayout,
        card: QWidget,
        heading: str,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        """Add a titled sub-group (a heading over its :class:`FieldRow`s) to the card."""
        label = QLabel(heading, card)
        label.setObjectName("geoModeGroupHeading")
        box.addWidget(label)
        for text, dotpath in fields:
            row = FieldRow(dotpath, text, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

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


__all__ = ["PlatformInputsForm"]
