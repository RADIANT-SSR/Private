"""The Optics stage's **Elements** tab — the mixed-train element-list editor (ADR-0009 D2).

:class:`OpticalElementEditor` is the structured config-document editor of the GUI
Capability Expansion plan Phase GS-4 (audit O-1: per-element %R/%T/temperature mapping —
the audit's flagship optics gap). It edits the **declarative element document** — the same
entry dicts the ``optical_elements:`` YAML section carries — never physics objects: rows
are (name, transfer mode, kind, R-or-T value, temperature, geometry), *Apply* serializes
the table to entries and commits through exactly **one API call**,
:meth:`Sensor.set_optical_elements` (validate-and-attach through the io parser — the single
validation authority, Kirchhoff checks included — then persisted by ``Sensor.save``,
ADR-0009 D4). The optics stage runs full-prescription on the next evaluation and the
Throughput tab's coating-spectra figure reflects the authored train.

**Emissivity is derived, never an input (Rule 5).** The ε column is **read-only**, filled
from :func:`radiant.api.preview_optical_elements` (band-mean Kirchhoff ε: 1 − R for
mirrors, cavity/zero for refractive). There is no ε input anywhere in this editor.

**R/T value cells** accept a scalar (``0.97``) or a spectral-CSV path (``coatings/au.csv``)
— exactly the document schema; the io parser resolves and validates either form. A
rejected document (missing field, Kirchhoff violation, bad file) surfaces the parser's
actionable error in the shared
:class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`; the live
sensor is never touched by an invalid Apply (fail-fast in ``set_optical_elements``).

Applying emits :attr:`elementsApplied`, which the host relays through the standard
``parameterEdited`` pipeline (stale dots + debounced re-evaluation). The pseudo dot-path
``optics_config.element_list`` identifies the edit; it is not a scalar parameter, so no
undo command is recorded (documented Phase-9 limitation for non-scalar edits).

All colour/typography comes from the QSS theme via object names; one widget class per
file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api.config_io import preview_optical_elements
from radiant.core.exceptions import RadiantError
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The pseudo dot-path the host's parameterEdited pipeline sees for an element-document
# commit (not a scalar parameter; undo skips it, dirty/stale/re-evaluate all apply).
ELEMENT_EDIT_PATH: Final[str] = "optics_config.element_list"

_TITLE = "Optical element train — per-element R/T, temperature, geometry (ε derived)"
_HINT = (
    "R/T cells take a scalar (0.97) or a spectral-CSV path. ε is Kirchhoff-derived "
    "(read-only). Kind is a descriptive label for refractive elements (legend/reporting; "
    "the physics comes from R/T and temperature) — a REFLECTIVE row is always a mirror. "
    "Apply commits the train (one API call); Save persists it in the config."
)

_TRANSFER_CHOICES: Final[tuple[str, ...]] = ("REFLECTIVE", "REFRACTIVE")
# Refractive kinds (a REFLECTIVE row is always a mirror; the factory sets it).
_KIND_CHOICES: Final[tuple[str, ...]] = (
    "lens",
    "window",
    "filter",
    "beamsplitter",
    "dewar_window",
)

_COL_NAME = 0
_COL_TRANSFER = 1
_COL_KIND = 2
_COL_VALUE = 3
_COL_TEMP = 4
_COL_DIAM = 5
_COL_DIST = 6
_COL_EPS = 7
_HEADERS: Final[tuple[str, ...]] = (
    "Name",
    "Transfer",
    "Kind",
    "R or T (scalar | CSV)",
    "T (K)",
    "Diam (m)",
    "→FPA (m)",
    "ε (derived)",
)

# Sensible new-row defaults (ambient mirror / cold filter): plain literals for the
# editor's starting text only — every physical check happens in the io parser on Apply.
_NEW_MIRROR: Final[dict[str, Any]] = {
    "name": "mirror",
    "transfer_mode": "REFLECTIVE",
    "reflectance": 0.97,
    "temperature_K": 293.0,
    "diameter_m": 0.3,
    "distance_to_fpa_m": 1.0,
}
_NEW_REFRACTIVE: Final[dict[str, Any]] = {
    "name": "element",
    "transfer_mode": "REFRACTIVE",
    "kind": "filter",
    "transmittance": 0.9,
    "temperature_K": 240.0,
    "diameter_m": 0.05,
    "distance_to_fpa_m": 0.05,
}


class OpticalElementEditor(QWidget):
    """The element-train table editor: rows ⇌ the declarative element document.

    Signals
    -------
    elementsApplied(str):
        Emitted with :data:`ELEMENT_EDIT_PATH` after a successful Apply (the one
        ``sensor.set_optical_elements`` call), so the host marks state stale and
        schedules a re-evaluation — the same contract as ``parameterEdited``.
    """

    elementsApplied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("opticalElementEditor")

        self._sensor: Sensor | None = None

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

        hint = QLabel(_HINT, card)
        hint.setObjectName("stageCenterNote")
        hint.setWordWrap(True)
        box.addWidget(hint)

        self._table = QTableWidget(0, len(_HEADERS), card)
        self._table.setObjectName("elementTable")
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        box.addWidget(self._table)

        buttons = QWidget(card)
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        self._add_mirror = QPushButton("Add mirror", buttons)
        self._add_refractive = QPushButton("Add refractive", buttons)
        self._remove = QPushButton("Remove", buttons)
        self._up = QPushButton("↑", buttons)
        self._down = QPushButton("↓", buttons)
        self._apply = QPushButton("Apply train", buttons)
        self._apply.setObjectName("elementApplyButton")
        for b in (self._add_mirror, self._add_refractive, self._remove, self._up, self._down):
            button_row.addWidget(b)
        button_row.addStretch(1)
        button_row.addWidget(self._apply)
        box.addWidget(buttons)

        self._add_mirror.clicked.connect(lambda: self._append_row(dict(_NEW_MIRROR)))
        self._add_refractive.clicked.connect(lambda: self._append_row(dict(_NEW_REFRACTIVE)))
        self._remove.clicked.connect(self._remove_current)
        self._up.clicked.connect(lambda: self._move_current(-1))
        self._down.clicked.connect(lambda: self._move_current(+1))
        self._apply.clicked.connect(self.apply_train)

        layout.addWidget(card)

    # -- binding --------------------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor*; load its attached element document into the table.

        Loading happens on bind only (never on populate), so an in-progress table edit
        is not clobbered by each re-evaluation. *display_units* is accepted for
        signature parity with the other Inputs forms; the table's engineering columns
        are canonical-unit by design (K, m).
        """
        del display_units  # signature parity with the other Inputs forms
        self._sensor = sensor
        self._table.setRowCount(0)
        document = sensor.optical_elements() if sensor is not None else None
        if document:
            for entry in document:
                self._append_row(entry)
            self._refresh_derived_emissivity(document)

    def refresh(self) -> None:
        """No-op on re-evaluation (the table is an editor, not a readout)."""

    # -- table mechanics ------------------------------------------------------

    def _append_row(self, entry: dict[str, Any]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        transfer = str(entry.get("transfer_mode", "REFLECTIVE")).upper()
        value = entry.get("reflectance" if transfer == "REFLECTIVE" else "transmittance", "")

        self._table.setItem(row, _COL_NAME, QTableWidgetItem(str(entry.get("name", ""))))

        transfer_combo = QComboBox(self._table)
        transfer_combo.addItems(list(_TRANSFER_CHOICES))
        transfer_combo.setCurrentText(transfer)
        self._table.setCellWidget(row, _COL_TRANSFER, transfer_combo)

        kind_combo = QComboBox(self._table)
        kind_combo.addItems(list(_KIND_CHOICES))
        kind_combo.setCurrentText(str(entry.get("kind", "lens")).lower())
        self._table.setCellWidget(row, _COL_KIND, kind_combo)
        # Kind applies to refractive rows only (a REFLECTIVE row is always a mirror —
        # the factory forces it and entries() omits kind). Keep the combo honest:
        # locked to "mirror" and disabled while the row is reflective.
        transfer_combo.currentTextChanged.connect(
            lambda text, combo=kind_combo: self._sync_kind_combo(combo, text)
        )
        self._sync_kind_combo(kind_combo, transfer)

        self._table.setItem(row, _COL_VALUE, QTableWidgetItem(str(value)))
        self._table.setItem(
            row, _COL_TEMP, QTableWidgetItem(str(entry.get("temperature_K", 293.0)))
        )
        self._table.setItem(row, _COL_DIAM, QTableWidgetItem(str(entry.get("diameter_m", 0.1))))
        self._table.setItem(
            row, _COL_DIST, QTableWidgetItem(str(entry.get("distance_to_fpa_m", 1.0)))
        )
        eps_item = QTableWidgetItem("—")
        eps_item.setFlags(eps_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, _COL_EPS, eps_item)

    @staticmethod
    def _sync_kind_combo(kind_combo: QComboBox, transfer_text: str) -> None:
        """Lock Kind to "mirror" (disabled) on a REFLECTIVE row; free it on REFRACTIVE.

        Kind is a descriptive label for refractive elements; a reflective element is
        a mirror by construction, so showing an editable refractive kind there would
        misstate the document (owner report 2026-07-16).
        """
        reflective = transfer_text.upper() == "REFLECTIVE"
        if reflective:
            if kind_combo.findText("mirror") < 0:
                kind_combo.insertItem(0, "mirror")
            kind_combo.setCurrentText("mirror")
            kind_combo.setEnabled(False)
        else:
            kind_combo.setEnabled(True)
            mirror_idx = kind_combo.findText("mirror")
            if mirror_idx >= 0:
                if kind_combo.currentText() == "mirror":
                    kind_combo.setCurrentText("lens")
                kind_combo.removeItem(mirror_idx)

    def _remove_current(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def _move_current(self, delta: int) -> None:
        row = self._table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < self._table.rowCount()):
            return
        entries = self.entries()
        entries[row], entries[target] = entries[target], entries[row]
        self._reload(entries)
        self._table.setCurrentCell(target, _COL_NAME)

    def _reload(self, entries: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        for entry in entries:
            self._append_row(entry)

    # -- document assembly ----------------------------------------------------

    def entries(self) -> list[dict[str, Any]]:
        """The table serialized to the declarative element document (verbatim cells).

        Value cells parse as float when numeric, otherwise pass through as a
        spectral-CSV path string — the two forms the document schema accepts. No
        physics validation happens here (the io parser owns it, on Apply).
        """
        result: list[dict[str, Any]] = []
        for row in range(self._table.rowCount()):
            transfer_widget = self._table.cellWidget(row, _COL_TRANSFER)
            kind_widget = self._table.cellWidget(row, _COL_KIND)
            assert isinstance(transfer_widget, QComboBox)  # noqa: S101 — widget invariant
            assert isinstance(kind_widget, QComboBox)  # noqa: S101 — widget invariant
            transfer = transfer_widget.currentText()
            entry: dict[str, Any] = {
                "name": self._cell_text(row, _COL_NAME),
                "transfer_mode": transfer,
                "temperature_K": self._cell_number(row, _COL_TEMP),
                "diameter_m": self._cell_number(row, _COL_DIAM),
                "distance_to_fpa_m": self._cell_number(row, _COL_DIST),
            }
            # A value cell is a scalar when it parses, else a spectral-CSV path
            # string — the two forms the document schema accepts.
            text = self._cell_text(row, _COL_VALUE)
            value: Any
            try:
                value = float(text)
            except ValueError:
                value = text
            if transfer == "REFLECTIVE":
                entry["reflectance"] = value
            else:
                entry["kind"] = kind_widget.currentText()
                entry["transmittance"] = value
            result.append(entry)
        return result

    def _cell_text(self, row: int, col: int) -> str:
        item = self._table.item(row, col)
        return item.text().strip() if item is not None else ""

    def _cell_number(self, row: int, col: int) -> Any:
        text = self._cell_text(row, col)
        try:
            return float(text)
        except ValueError:
            return text  # let the io parser reject it with its actionable message

    # -- commit (one API call) -------------------------------------------------

    def apply_train(self) -> bool:
        """Validate + attach the table's document — one ``set_optical_elements`` call.

        Success fills the derived-ε column from the preview and emits
        :attr:`elementsApplied`; a parser rejection shows the actionable error dialog
        and leaves the live sensor untouched (fail-fast in the API). An empty table
        detaches the document (back to the scalar/params transmission mode).
        """
        sensor = self._sensor
        if sensor is None:
            return False
        entries = self.entries()
        try:
            if entries:
                sensor.set_optical_elements(entries)
                self._refresh_derived_emissivity(sensor.optical_elements() or entries)
            else:
                sensor.set_optical_elements(None)
        except RadiantError as exc:
            dialog = ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self)
            dialog.exec()
            return False
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)
        return True

    def _refresh_derived_emissivity(self, entries: list[dict[str, Any]]) -> None:
        """Fill the read-only ε column from the facade preview (Rule 5 — derived only)."""
        previews = preview_optical_elements(entries)
        for row, preview in enumerate(previews):
            item = self._table.item(row, _COL_EPS)
            if item is not None:
                item.setText(f"{preview.emissivity_mean:.4f}")

    # -- accessors (tests) ------------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The element table (tests)."""
        return self._table

    @property
    def apply_button(self) -> QPushButton:
        """The Apply button (tests)."""
        return self._apply


__all__ = ["OpticalElementEditor", "ELEMENT_EDIT_PATH"]
