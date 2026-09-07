"""The Detector stage's **FPA part library** card — apply a named preset (Gap 119 §3.6).

:class:`FPAPartSelector` sits above the Detector *Inputs* card: pick a real part
(GeoSnap-18, H2RG, Boson+, …) from the bundled library and apply it in **one API
call** (``sensor.apply_fpa`` — the GUI is a view over the scripting API, R-API).
The apply contract is the library's: *presets seed, explicit values win* — the
returned :class:`~radiant.api.fpa_preset.FPAApplyReport` is summarized inline
("N applied, M kept") and expandable to the per-parameter provenance detail
(value basis grades: datasheet / paper / derived / assumed). Each apply re-emits
:attr:`presetApplied`, so the host debounces a full re-evaluation exactly like a
field edit (edit-and-watch).

**Open datasheet/paper** opens the part's cited reference document: the
committed PDF under ``docs/validation/fpa_datasheets/`` when running from a
repository checkout, else the citation URL/DOI (wheel installs carry citations,
not PDFs — plan §3.5). Part metadata comes from
:func:`radiant.api.fpa_preset.available_fpa_parts` (the GUI imports
``radiant.api`` only, never ``radiant.data``).

All colour/typography comes from the QSS theme via object names (GUI plan
§4.9); this file holds no colour/font literal. One widget class per file
(Rule 19).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.fpa_preset import FPAApplyReport, FPAPartInfo, available_fpa_parts
from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_TITLE = "FPA part library"

# Human labels for the closed part-class taxonomy (labels only — the classes
# themselves come from the library metadata, never transcribed values).
_CLASS_LABELS = {
    "cooled_ir": "Cooled IR",
    "cooled_ir_droic": "Cooled IR — digital-pixel (counting)",
    "uncooled_bolometer": "Uncooled bolometer",
    "scientific_visible": "Scientific / visible",
    "swir": "SWIR",
}

# Repo-checkout home of the committed reference documents (plan §3.5). Resolved
# relative to this module; absent in a wheel install, where the URL fallback runs.
_DATASHEET_DIR = Path(__file__).resolve().parents[4] / "docs" / "validation" / "fpa_datasheets"


class FPAPartSelector(QWidget):
    """Part combo + Apply + Open datasheet + override-report summary."""

    #: Emitted after a successful apply with the part name; hosts treat it like
    #: a parameter edit (debounced re-evaluation).
    presetApplied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fpaPartSelector")

        self._sensor: Sensor | None = None
        self._parts: dict[str, FPAPartInfo] = {p.name: p for p in available_fpa_parts()}
        self._last_report: FPAApplyReport | None = None

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
        box.addWidget(title)

        picker_row = QWidget(card)
        picker = QHBoxLayout(picker_row)
        picker.setContentsMargins(0, 0, 0, 0)
        picker.setSpacing(8)

        self._combo = QComboBox(picker_row)
        self._combo.setObjectName("fpaPartCombo")
        self._combo.addItem("(choose a part…)", None)
        last_class: str | None = None
        for info in sorted(self._parts.values(), key=lambda i: (i.part_class, i.name)):
            if info.part_class != last_class:
                label = _CLASS_LABELS.get(info.part_class, info.part_class)
                self._combo.addItem(f"— {label} —", None)
                index = self._combo.count() - 1
                item = self._combo.model().item(index)  # type: ignore[union-attr]
                if item is not None:
                    item.setEnabled(False)
                last_class = info.part_class
            self._combo.addItem(f"{info.vendor} {info.model}  ({info.name})", info.name)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        picker.addWidget(self._combo, 1)

        self._apply = QPushButton("Apply preset", picker_row)
        self._apply.setObjectName("fpaApplyButton")
        self._apply.setEnabled(False)
        self._apply.clicked.connect(self._on_apply)
        picker.addWidget(self._apply)

        self._open_doc = QPushButton("Open datasheet/paper", picker_row)
        self._open_doc.setObjectName("fpaOpenDatasheetButton")
        self._open_doc.setEnabled(False)
        self._open_doc.clicked.connect(self._on_open_document)
        picker.addWidget(self._open_doc)

        box.addWidget(picker_row)

        # Selected-part blurb: band + parameter/basis census, before any apply.
        self._blurb = QLabel("", card)
        self._blurb.setObjectName("fpaPartBlurb")
        self._blurb.setWordWrap(True)
        self._blurb.hide()
        box.addWidget(self._blurb)

        report_row = QWidget(card)
        report_box = QHBoxLayout(report_row)
        report_box.setContentsMargins(0, 0, 0, 0)
        report_box.setSpacing(8)
        self._report_label = QLabel("", report_row)
        self._report_label.setObjectName("fpaApplyReportLabel")
        self._report_label.setWordWrap(True)
        report_box.addWidget(self._report_label, 1)
        self._details = QPushButton("Details…", report_row)
        self._details.setObjectName("fpaReportDetailsButton")
        self._details.clicked.connect(self._on_details)
        report_box.addWidget(self._details)
        report_row.hide()
        self._report_row = report_row
        box.addWidget(report_row)

        layout.addWidget(card)

    # -- binding -------------------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None) -> None:
        """Bind the live *sensor*; a ``None`` sensor disables Apply."""
        self._sensor = sensor
        self._on_selection_changed()

    # -- selection -----------------------------------------------------------

    def selected_part(self) -> str | None:
        """The selected part name, or ``None`` on the placeholder rows."""
        data = self._combo.currentData()
        return str(data) if data else None

    def _on_selection_changed(self, _index: int = 0) -> None:
        info = self._parts.get(self.selected_part() or "")
        self._apply.setEnabled(info is not None and self._sensor is not None)
        self._open_doc.setEnabled(info is not None and bool(info.sources))
        if info is None:
            self._blurb.hide()
            return
        census = ", ".join(f"{n} {basis}" for basis, n in info.basis_counts)
        self._blurb.setText(
            f"{info.band_label} — {info.parameter_count} parameters ({census}). {info.description}"
        )
        self._blurb.show()

    # -- apply ---------------------------------------------------------------

    def _on_apply(self) -> None:
        """One API call: ``sensor.apply_fpa(part)``; summarize the report."""
        name = self.selected_part()
        if self._sensor is None or name is None:
            return
        try:
            report = self._sensor.apply_fpa(name)
        except RadiantError as exc:
            QMessageBox.critical(self, "FPA preset", str(exc))
            return
        self._last_report = report
        kept = len(report.skipped_existing)
        summary = f"{report.part}: {len(report.applied)} parameter(s) applied"
        if kept:
            summary += f", {kept} kept their explicit values (explicit wins)"
        if report.qe_material:
            summary += f"; QE curve → {report.qe_material}"
        self._report_label.setText(summary)
        self._report_row.show()
        self.presetApplied.emit(name)

    def _on_details(self) -> None:
        """Per-parameter provenance detail for the last apply."""
        report = self._last_report
        if report is None:
            return
        info = self._parts.get(report.part)
        lines = [f"Preset '{report.part}' — provenance detail", ""]
        lines.append("Applied (Provenance.PRESET, source fpa:<part>/<citation>):")
        lines += [f"  • {p}" for p in report.applied] or ["  (none)"]
        if report.skipped_existing:
            lines.append("")
            lines.append("Kept — an explicit user/config value already held these:")
            lines += [f"  • {p}" for p in report.skipped_existing]
        if info is not None:
            lines.append("")
            census = ", ".join(f"{n} {basis}" for basis, n in info.basis_counts)
            lines.append(f"Value bases in the preset document: {census}.")
            lines.append("Sources: " + "; ".join(s.title for s in info.sources))
        box = QMessageBox(self)
        box.setObjectName("fpaReportDetailsDialog")
        box.setWindowTitle("FPA preset report")
        box.setText("\n".join(lines))
        box.exec()

    # -- reference documents -------------------------------------------------

    def _document_target(self) -> QUrl | None:
        """The best openable target for the selected part's first citation.

        Committed PDF (repo checkout) beats URL beats DOI; ``None`` when the
        part has no reachable citation.
        """
        info = self._parts.get(self.selected_part() or "")
        if info is None:
            return None
        for src in info.sources:
            if src.file is not None:
                local = _DATASHEET_DIR / src.file
                if local.is_file():
                    return QUrl.fromLocalFile(str(local))
        for src in info.sources:
            if src.url:
                return QUrl(src.url)
            if src.doi:
                return QUrl(f"https://doi.org/{src.doi}")
        return None

    def _on_open_document(self) -> None:
        target = self._document_target()
        if target is None:
            QMessageBox.information(
                self, "FPA preset", "This part's preset carries no openable citation."
            )
            return
        QDesktopServices.openUrl(target)


__all__ = ["FPAPartSelector"]
