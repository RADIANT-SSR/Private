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

from pathlib import Path
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import (
    LABEL_COLUMN_WIDTH,
    VALUE_BOX_MAX,
    FieldRow,
)
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.import_preview_dialog import ImportPreviewDialog
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.spectral_table_dialog import SpectralTableDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The full detector schema as grouped (label, dot-path) manifests (GUI Capability
# Expansion plan GS-3 — audit D-1…D-9: the engine's richest noise model was 6/27 exposed).
# Bounds/units/choices/description all come from the live schema (never transcribed) —
# only the human labels + the grouping are literals here (CU-120, tracked with the
# geometry/source/optics manifests). Grouping is presentation only; no schema change.
_GEOMETRY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Pixel pitch x (cross-track)", "detector.pixel_pitch_x_um"),
    ("Pixel pitch y (along-track)", "detector.pixel_pitch_y_um"),
    ("Fill factor", "detector.fill_factor"),
    ("Cross-track pixel count", "detector.n_pixels_cross"),
    ("Detector temperature", "detector.detector_temperature_K"),
)

_QE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Quantum efficiency (scalar)", "detector.qe_value"),
    ("QE curve CSV (import)", "detector.qe_table_path"),
    ("QE material (library)", "detector.qe_material"),
    ("QE temperature coefficient", "detector.qe_temperature_coeff_per_K"),
    ("QE reference temperature", "detector.qe_temperature_ref_K"),
)

_DARK_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Dark rate", "detector.dark_rate_e_per_s"),
    ("Dark reference temperature", "detector.dark_reference_temperature_K"),
    ("Dark activation energy", "detector.dark_activation_energy_eV"),
    ("ROIC glow", "detector.glow_e_per_s"),
)

_FLICKER_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("1/f coefficient K", "detector.flicker_K"),
    ("1/f band low edge", "detector.flicker_f_low_hz"),
    ("1/f band high edge", "detector.flicker_f_high_hz"),
)

_GR_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("G-R factor (HgCdTe)", "detector.gr_factor"),
    ("R₀A product (Johnson)", "detector.r0a_ohm_cm2"),
)

_FPN_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("PRNU", "detector.prnu_pct"),
    ("DSNU", "detector.dsnu_e_rms"),
    ("Clutter σ (SCNR)", "detector.clutter_sigma"),
    ("Noise regime", "detector.noise_regime"),
)

_PERSISTENCE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Persistence fraction", "detector.persistence_fraction"),
    ("Persistence time constant", "detector.persistence_tau_s"),
    ("Prior-frame signal", "detector.prior_signal_e"),
)

_COUPLING_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("IPC coupling α", "detector.ipc_coupling"),
    ("Charge-diffusion length", "detector.charge_diffusion_length_m"),
)

# The flat union, in display order — the single manifest tests and hosts iterate.
_DETECTOR_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    _GEOMETRY_FIELDS
    + _QE_FIELDS
    + _DARK_FIELDS
    + _FLICKER_FIELDS
    + _GR_FIELDS
    + _FPN_FIELDS
    + _PERSISTENCE_FIELDS
    + _COUPLING_FIELDS
)

# (heading, fields) in reading order: geometry first (what the pixel is), then signal
# efficiency, then the noise-model groups in signal-chain order.
_GROUPS: Final[tuple[tuple[str, tuple[tuple[str, str], ...]], ...]] = (
    ("Pixel geometry & temperature", _GEOMETRY_FIELDS),
    ("Quantum efficiency", _QE_FIELDS),
    ("Dark current & glow", _DARK_FIELDS),
    ("1/f noise", _FLICKER_FIELDS),
    ("G-R & Johnson noise", _GR_FIELDS),
    ("Fixed-pattern noise & regime", _FPN_FIELDS),
    ("Persistence", _PERSISTENCE_FIELDS),
    ("IPC & diffusion", _COUPLING_FIELDS),
)

_TITLE = "Detector — geometry, QE, dark, noise model (full schema)"


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
        # Two-column group grid (owner layout report 2026-07-16): the full-schema form
        # is 27 fields — one long column read badly. Each group is a self-contained
        # block placed left/right alternately; the flat _rows dict is unchanged, so
        # binding/refresh and every test iterate exactly as before.
        grid_host = QWidget(card)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        for index, (heading, fields) in enumerate(_GROUPS):
            block = QWidget(grid_host)
            block_box = QVBoxLayout(block)
            block_box.setContentsMargins(0, 0, 0, 0)
            block_box.setSpacing(6)
            group_label = QLabel(heading, block)
            group_label.setObjectName("geoModeGroupHeading")
            block_box.addWidget(group_label)
            for label, dotpath in fields:
                row = FieldRow(dotpath, label, self._open_editor)
                block_box.addWidget(row)
                self._rows[dotpath] = row
            if fields is _QE_FIELDS:
                # Define QE(λ) inline (owner request 2026-07-16): type or paste a λ-vs-QE
                # table; the dialog's points are written to a user-chosen CSV and
                # detector.qe_table_path is set in one API call — the same loader path a
                # hand-made vendor CSV takes (io/qe_csv.py auto-detects the units).
                self._define_qe = QPushButton("Define QE(λ) table…", block)
                self._define_qe.setObjectName("defineQeButton")
                self._define_qe.setMaximumWidth(LABEL_COLUMN_WIDTH + VALUE_BOX_MAX + 10)
                self._define_qe.clicked.connect(self._on_define_qe)
                block_box.addWidget(self._define_qe)
                # D5 confirm-before-Apply import: preview the parsed curve (header
                # unit auto-detection shown) before the one sensor.set commits it.
                self._import_qe = QPushButton("Import QE curve (preview)…", block)
                self._import_qe.setObjectName("importQeButton")
                self._import_qe.setMaximumWidth(LABEL_COLUMN_WIDTH + VALUE_BOX_MAX + 10)
                self._import_qe.clicked.connect(self._on_import_qe)
                block_box.addWidget(self._import_qe)
            block_box.addStretch(1)
            grid.addWidget(block, index // 2, index % 2, Qt.AlignmentFlag.AlignTop)
        box.addWidget(grid_host)

        layout.addWidget(card)

    # -- QE(λ) table authoring (owner request 2026-07-16) ---------------------

    def _on_define_qe(self) -> None:
        """Open the λ-table dialog, save the points as a QE CSV, set qe_table_path."""
        if self._sensor is None:
            return
        current = str(self._sensor.get_input("detector.qe_table_path") or "")
        dialog = SpectralTableDialog(self, title="Quantum efficiency QE(λ)")
        if current and Path(current).is_file():
            dialog.load_text(Path(current).read_text(encoding="utf-8"))
        if exec_dialog(dialog) != int(dialog.DialogCode.Accepted):
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save QE curve CSV", "qe_curve.csv", "CSV (*.csv);;All files (*)"
        )
        if not filename:
            return
        self.define_qe_table(dialog.spectrum(), Path(filename))

    def _on_import_qe(self) -> None:
        """Preview a vendor QE CSV (D5 dialog); on Apply bind detector.qe_table_path."""
        if self._sensor is None:
            return
        dialog = ImportPreviewDialog("qe_csv", self)
        if exec_dialog(dialog) != int(dialog.DialogCode.Accepted):
            return
        path = dialog.selected_path()
        if path is None:
            return
        self._sensor.set("detector.qe_table_path", path)
        self.refresh()
        self.parameterEdited.emit("detector.qe_table_path")

    def define_qe_table(self, spectrum: dict[str, list[float]], path: Path) -> None:
        """Write *spectrum* as a QE CSV at *path* and bind it — one ``sensor.set``.

        The CSV header ``wavelength_um,qe`` lets the io loader auto-detect µm +
        fraction; the file is ordinary user data, re-importable anywhere.
        """
        if self._sensor is None:
            return
        lines = ["wavelength_um,qe"]
        lines += [
            f"{wl:g},{qe:g}"
            for wl, qe in zip(spectrum["wavelength_um"], spectrum["values"], strict=True)
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._sensor.set("detector.qe_table_path", str(path))
        self.refresh()
        self.parameterEdited.emit("detector.qe_table_path")

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


__all__ = ["DetectorInputsForm"]
