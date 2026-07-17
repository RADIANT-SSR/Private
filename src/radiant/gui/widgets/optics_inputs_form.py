"""The Optics stage's **Inputs** section — editable schema-driven optics fields.

:class:`OpticsInputsForm` is the *Inputs* section of the Optics stage's contextual center
(arch doc §4.4 section 1, GUI plan Phase PS-2): the key instrument parameters — aperture
diameter, focal length / f-number, central obscuration + spiders, the scalar throughput
τ_opt, the RMS wavefront error, and the optics temperature — as editable schema-driven
rows. It is the optics sibling of :class:`~radiant.gui.widgets.source_inputs_form.SourceInputsForm`:
together with the MTF / PSF+pupil / throughput diagnostic tabs it makes the Optics stage the
richest per-stage *instrument* (arch doc §4.4.1 Optics rows) — edit an input and watch the
maps respond (WFE → the pupil-phase map gains structure; aperture → MTF/PSF; τ_opt → the
throughput curve).

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface
(:meth:`Sensor.parameter_def` for the label/unit, :meth:`Sensor.get_input` for the value).
Editing a field opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first (a rejected value never
touches the live sensor; the actionable what/why/action shows inline) — the identical
edit+reject discipline as the parameter tree (Phase 2), the Geometry Inputs form (Phase 5),
and the Source Inputs form (Phase PS-1). The value shows in the row's **display unit**,
sharing the parameter panel's session display-unit store so a unit chosen on any surface
agrees. Each accepted edit re-emits :attr:`parameterEdited`, so the host debounces a full
re-evaluation and every Optics diagnostic + the Outputs readout refresh (edit-and-watch).

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow` — the same
building block every other schema-driven field uses — so the Optics inputs render
**identically by construction** to every other field (owner hard rule). All
colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour/font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.config_io import preview_zemax_zernike
from radiant.core.exceptions import RadiantError
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.field_row import (
    LABEL_COLUMN_WIDTH,
    VALUE_BOX_MAX,
    FieldRow,
)
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The key optics parameters (label, dot-path), in a reading order that groups the aperture
# geometry (diameter, focal length, f/#, obscuration, spiders), the scalar throughput τ_opt
# (the coating parameter present in scalar-transmission mode), the RMS wavefront error, and
# the optics temperature. Bounds/units/description all come from the live schema (never
# transcribed) — only the human label + the grouping is a literal here (CU-120, tracked with
# the geometry/source manifests).
_OPTICS_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Aperture diameter", "optics.aperture_diameter_m"),
    ("Focal length", "optics.focal_length_m"),
    ("f-number", "optics.f_number"),
    ("Obscuration ratio", "optics.obscuration_ratio"),
    ("Spider arms", "optics.n_spiders"),
    ("Scalar throughput τ_opt", "optics.transmission_scalar"),
    ("WFE RMS (scalar)", "optics.wfe_rms_waves"),
    ("WFE reference wavelength", "optics.wfe_reference_wavelength_um"),
    ("Zernike file (Zemax export)", "optics.zernike_file"),
    ("Defocus", "optics.defocus_um"),
    ("Optics temperature", "optics.optics_temperature_K"),
)

_TITLE = "Optics — aperture, throughput, wavefront error, temperature"


class OpticsInputsForm(QWidget):
    """The Optics inputs card: schema-driven :class:`FieldRow` per key optics parameter.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract as
        :attr:`SourceInputsForm.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("opticsInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # One ``geoModeFamily`` card (same object name → same QSS as every geometry/source
        # card), so the Optics inputs sit in an identically-styled card to the other fields.
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
        for label, dotpath in _OPTICS_FIELDS:
            row = FieldRow(dotpath, label, self._open_editor)
            box.addWidget(row)
            self._rows[dotpath] = row

        # GS-4 split 2: import a Zemax 'Zernike Standard Coefficients' export. The
        # D5 confirm-before-Apply flow: parse for display (api facade), show the
        # summary, and only on Yes commit optics.zernike_file (one sensor.set) —
        # the session loads the file pre-chain and the ZERNIKE wavefront supersedes
        # the scalar WFE path.
        self._import_zernike = QPushButton("Import Zemax Zernike…", card)
        self._import_zernike.setObjectName("importZernikeButton")
        self._import_zernike.setMaximumWidth(LABEL_COLUMN_WIDTH + VALUE_BOX_MAX + 10)
        self._import_zernike.clicked.connect(self._on_import_zernike)
        box.addWidget(self._import_zernike)

        layout.addWidget(card)

    # -- Zemax Zernike import (GS-4 split 2, ADR-0009 D5 flow) ----------------

    def _on_import_zernike(self) -> None:
        """Pick a Zemax export, preview it, and on confirm set optics.zernike_file."""
        if self._sensor is None:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Zemax Zernike export", "", "Zemax export (*.txt);;All files (*)"
        )
        if not filename:
            return
        try:
            preview = preview_zemax_zernike(filename)
        except RadiantError as exc:
            ActionableErrorDialog(exc, "optics.zernike_file", self).exec()
            return
        ref = (
            f"{preview.reference_wavelength_um:g} µm (from report)"
            if preview.reference_wavelength_um is not None
            else "none in report — optics.wfe_reference_wavelength_um applies"
        )
        answer = QMessageBox.question(
            self,
            "Apply Zernike wavefront?",
            (
                f"{Path(filename).name}: {preview.n_terms} terms, "
                f"RSS {preview.rms_waves:.4g} waves (non-piston)\n"
                f"Reference wavelength: {ref}\n\n"
                "Apply as the wavefront error (supersedes the scalar WFE)?"
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._sensor.set("optics.zernike_file", filename)
        self.refresh()
        self.parameterEdited.emit("optics.zernike_file")

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


__all__ = ["OpticsInputsForm"]
