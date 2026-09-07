"""The Detector stage's **FPA part library** row — apply a named preset (Gap 119 §3.6).

Live-review iteration (owner feedback 2026-09-06: the first-cut combo + blurb
card carried too much chrome and dead space): the card is now a **single
compact row** — status label + "Choose part & apply…" + "Open datasheet/paper"
— with the part browsing moved into
:class:`~radiant.gui.widgets.fpa_part_picker_dialog.FPAPartPickerDialog`
(sortable table with class/band/basis-census columns and a details pane).
Accepting the dialog makes the **one API call** (``sensor.apply_fpa``); the
applied-vs-kept summary replaces the status label, with a Details dialog for
the per-parameter provenance. A successful apply re-emits
:attr:`presetApplied`, so the host debounces a full re-evaluation exactly like
a field edit.

**Open datasheet/paper** opens the applied (or last-chosen) part's reference
document: the committed PDF under ``docs/validation/fpa_datasheets/`` in a
repository checkout, else the citation URL/DOI (wheel installs carry
citations, not PDFs — plan §3.5). Part metadata comes from
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
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.fpa_preset import FPAApplyReport, FPAPartInfo, available_fpa_parts
from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.widgets.fpa_part_picker_dialog import FPAPartPickerDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# Repo-checkout home of the committed reference documents (plan §3.5). Resolved
# relative to this module; absent in a wheel install, where the URL fallback runs.
_DATASHEET_DIR = Path(__file__).resolve().parents[4] / "docs" / "validation" / "fpa_datasheets"


class FPAPartSelector(QWidget):
    """One-row card: status + Choose-part-and-apply + Open-datasheet."""

    #: Emitted after a successful apply with the part name; hosts treat it like
    #: a parameter edit (debounced re-evaluation).
    presetApplied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fpaPartSelector")

        self._sensor: Sensor | None = None
        self._parts: dict[str, FPAPartInfo] = {p.name: p for p in available_fpa_parts()}
        self._current_part: str | None = None
        self._last_report: FPAApplyReport | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QHBoxLayout(card)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(8)

        title = QLabel("FPA part library", card)
        title.setObjectName("geoModeFamilyTitle")
        box.addWidget(title)

        self._status = QLabel("no part applied", card)
        self._status.setObjectName("fpaApplyReportLabel")
        self._status.setWordWrap(False)
        box.addWidget(self._status, 1)

        self._details = QPushButton("Details…", card)
        self._details.setObjectName("fpaReportDetailsButton")
        self._details.hide()
        self._details.clicked.connect(self._on_details)
        box.addWidget(self._details)

        self._choose = QPushButton("Choose part && apply…", card)
        self._choose.setObjectName("fpaChoosePartButton")
        self._choose.setEnabled(False)
        self._choose.clicked.connect(self._on_choose)
        box.addWidget(self._choose)

        self._open_doc = QPushButton("Open datasheet/paper", card)
        self._open_doc.setObjectName("fpaOpenDatasheetButton")
        self._open_doc.setEnabled(False)
        self._open_doc.clicked.connect(self._on_open_document)
        box.addWidget(self._open_doc)

        layout.addWidget(card)

    # -- binding -------------------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None) -> None:
        """Bind the live *sensor*; a ``None`` sensor disables choosing.

        A sensor that already carries preset applications (the config's
        ``fpa:`` key applies at load, before this card exists) is reflected
        immediately — the card reports the last apply instead of claiming
        "no part applied" (live-review finding 2026-09-06).
        """
        self._sensor = sensor
        self._choose.setEnabled(sensor is not None and bool(self._parts))
        reports = sensor.fpa_applications if sensor is not None else ()
        if reports:
            self._adopt_report(reports[-1])
        else:
            self._current_part = None
            self._last_report = None
            self._status.setText("no part applied")
            self._details.hide()
            self._open_doc.setEnabled(False)

    # -- state (tests + host) ------------------------------------------------

    def current_part(self) -> str | None:
        """The last applied (or dialog-chosen) part name, if any."""
        return self._current_part

    # -- choose + apply ------------------------------------------------------

    def _on_choose(self) -> None:
        """Open the picker; on accept, one ``sensor.apply_fpa`` call."""
        if self._sensor is None:
            return
        dialog = FPAPartPickerDialog(tuple(self._parts.values()), self)
        if self._current_part is not None:
            dialog.select_part(self._current_part)
        if exec_dialog(dialog) != int(dialog.DialogCode.Accepted):
            return
        name = dialog.selected_part()
        if name is not None:
            self.apply_part(name)

    def apply_part(self, name: str) -> None:
        """Apply *name* (one API call) and summarize the report inline."""
        if self._sensor is None:
            return
        try:
            report = self._sensor.apply_fpa(name)
        except RadiantError as exc:
            QMessageBox.critical(self, "FPA preset", str(exc))
            return
        self._adopt_report(report)
        self.presetApplied.emit(name)

    def _adopt_report(self, report: FPAApplyReport) -> None:
        """Reflect *report* on the card (status text, Details, Open-datasheet)."""
        self._current_part = report.part
        self._last_report = report
        kept = len(report.skipped_existing)
        summary = f"{report.part}: {len(report.applied)} applied"
        if kept:
            summary += f", {kept} kept (explicit wins)"
        if report.qe_material:
            summary += f"; QE curve → {report.qe_material}"
        self._status.setText(summary)
        self._details.show()
        self._open_doc.setEnabled(True)

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
        exec_dialog(box)

    # -- reference documents -------------------------------------------------

    def _document_target(self) -> QUrl | None:
        """The best openable target for the current part's first citation.

        Committed PDF (repo checkout) beats URL beats DOI; ``None`` when no
        part is chosen or it has no reachable citation.
        """
        info = self._parts.get(self._current_part or "")
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
