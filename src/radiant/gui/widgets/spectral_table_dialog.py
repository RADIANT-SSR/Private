"""Modal editor for an inline spectral response — type it in a table or paste it.

:class:`SpectralTableDialog` produces the **inline spectral table** form of an element
document value (`{"wavelength_um": [...], "values": [...]}` — the same structure the
``optical_elements:`` YAML section carries), so a component's λ-vs-R/T response can be
defined without any external CSV (owner request 2026-07-16; ADR-0009 follow-on). Two
entry routes into one editable two-column table:

- **Type it**: add/remove rows and edit λ [µm] / value cells directly.
- **Paste it**: *Paste from clipboard* parses spreadsheet-style text (one point per
  line, columns separated by comma / tab / whitespace; ``#`` comments and blank lines
  ignored) into the table — the natural Excel/editor copy-paste round trip.

A live status line shows the parse state (point count, λ span, value span — units
labeled, R-UNITS) or the first problem; **OK enables only on a valid table** (≥ 2
numeric points). The dialog performs *shape* checks only — physics validation
(bounds, Kirchhoff energy conservation) stays with the io element parser when the
train is applied (single validation authority, ADR-0009 D2).

One widget class per file (Rule 19); styling entirely from the QSS theme.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.errors import GuiValidationError


def parse_spectrum_text(text: str) -> list[tuple[float, float]]:
    """Parse pasted spreadsheet-style text into (wavelength_um, value) points.

    One point per non-blank, non-``#`` line; the first two comma/tab/whitespace
    separated columns are λ [µm] and the value. Raises ``ValueError`` naming the
    first offending line (shown verbatim in the status row — never a silent skip).
    """
    points: list[tuple[float, float]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        columns = line.replace(",", " ").replace("\t", " ").split()
        if len(columns) < 2:
            raise GuiValidationError(f"line {lineno}: need two columns (λ_um, value), got {line!r}")
        try:
            points.append((float(columns[0]), float(columns[1])))
        except ValueError as exc:
            raise GuiValidationError(f"line {lineno}: {exc}") from exc
    return points


class SpectralTableDialog(QDialog):
    """Edit an inline λ-vs-value spectral table (typed rows and/or clipboard paste)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "Spectral response",
        initial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("spectralTableDialog")
        self.setWindowTitle(title)
        self.resize(420, 480)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Wavelength in µm, value dimensionless (R or T). Type rows below, or "
            "paste two columns copied from a spreadsheet.",
            self,
        )
        hint.setObjectName("stageCenterNote")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._table = QTableWidget(0, 2, self)
        self._table.setObjectName("spectrumTable")
        self._table.setHorizontalHeaderLabels(["λ (µm)", "value (–)"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        buttons_row = QWidget(self)
        row = QHBoxLayout(buttons_row)
        row.setContentsMargins(0, 0, 0, 0)
        self._add_row = QPushButton("Add row", buttons_row)
        self._remove_row = QPushButton("Remove row", buttons_row)
        self._paste = QPushButton("Paste from clipboard", buttons_row)
        row.addWidget(self._add_row)
        row.addWidget(self._remove_row)
        row.addStretch(1)
        row.addWidget(self._paste)
        layout.addWidget(buttons_row)

        self._status = QLabel("", self)
        self._status.setObjectName("spectrumStatusLabel")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._add_row.clicked.connect(lambda: self._append_point("", ""))
        self._remove_row.clicked.connect(self._remove_current)
        self._paste.clicked.connect(self._paste_clipboard)
        self._table.itemChanged.connect(lambda _item: self._revalidate())

        if initial:
            for wl, val in zip(
                initial.get("wavelength_um", ()), initial.get("values", ()), strict=False
            ):
                self._append_point(str(wl), str(val))
        self._revalidate()

    # -- table mechanics ------------------------------------------------------

    def _append_point(self, wl_text: str, val_text: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(wl_text))
        self._table.setItem(row, 1, QTableWidgetItem(val_text))

    def _remove_current(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._revalidate()

    def _paste_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.load_text(QApplication.clipboard().text())

    def load_text(self, text: str) -> None:
        """Fill the table from spreadsheet-style *text* (also the paste target)."""
        try:
            points = parse_spectrum_text(text)
        except ValueError as exc:
            self._status.setText(f"Paste failed — {exc}")
            return
        self._table.setRowCount(0)
        for wl, val in points:
            self._append_point(f"{wl:g}", f"{val:g}")
        self._revalidate()

    # -- validation / result ---------------------------------------------------

    def _points(self) -> list[tuple[float, float]]:
        """The table parsed to points; raises ValueError on the first bad cell."""
        points: list[tuple[float, float]] = []
        for row in range(self._table.rowCount()):
            wl_item = self._table.item(row, 0)
            val_item = self._table.item(row, 1)
            wl_text = wl_item.text().strip() if wl_item else ""
            val_text = val_item.text().strip() if val_item else ""
            if not wl_text and not val_text:
                continue  # an all-blank row is ignorable scaffolding
            points.append((float(wl_text), float(val_text)))
        return points

    def _revalidate(self) -> None:
        """Refresh the status line and gate OK on a valid (≥ 2 point) table."""
        try:
            points = self._points()
        except ValueError:
            self._status.setText("Row has a non-numeric cell — fix or remove it.")
            self._set_ok(False)
            return
        if len(points) < 2:
            self._status.setText(f"{len(points)} point(s) — at least 2 required.")
            self._set_ok(False)
            return
        wavelengths = [p[0] for p in points]
        values = [p[1] for p in points]
        self._status.setText(
            f"{len(points)} points · λ {min(wavelengths):g}–{max(wavelengths):g} µm · "
            f"value {min(values):g}–{max(values):g}"
        )
        self._set_ok(True)

    def _set_ok(self, ok: bool) -> None:
        button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(ok)

    def spectrum(self) -> dict[str, list[float]]:
        """The inline spectral table (`wavelength_um` / `values`), λ-sorted."""
        points = sorted(self._points())
        return {
            "wavelength_um": [p[0] for p in points],
            "values": [p[1] for p in points],
        }

    # -- accessors (tests) -------------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The two-column point table (tests)."""
        return self._table

    @property
    def status_text(self) -> str:
        """The current status-line text (tests)."""
        return self._status.text()

    def ok_enabled(self) -> bool:
        """Whether OK is currently enabled (tests)."""
        button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        return bool(button is not None and button.isEnabled())


__all__ = ["SpectralTableDialog", "parse_spectrum_text"]
