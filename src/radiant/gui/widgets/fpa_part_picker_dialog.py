"""Modal picker for the FPA part library (Gap 119 §3.6, live-review iteration).

:class:`FPAPartPickerDialog` replaces the first-cut combo box (owner feedback
2026-09-06: too much chrome on the card): a sortable table of every shipped
part — vendor/model, class, band, and the data-quality basis census — with a
details pane (description + citations) that follows the selection. **Apply
preset** accepts the dialog; the host card then makes the one
``sensor.apply_fpa`` call. Read-only over
:func:`radiant.api.fpa_preset.available_fpa_parts`; no colour/font literals
(QSS themes by object name). One widget class per file (Rule 19).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api.fpa_preset import FPAPartInfo

_CLASS_LABELS = {
    "cooled_ir": "Cooled IR",
    "cooled_ir_droic": "Digital-pixel (counting)",
    "uncooled_bolometer": "Uncooled bolometer",
    "scientific_visible": "Scientific / visible",
    "swir": "SWIR",
}
_COLUMNS = ("Part", "Kind", "Class", "Band", "Values (basis census)")


class FPAPartPickerDialog(QDialog):
    """Table of library parts + details pane; OK applies the selection."""

    def __init__(self, parts: tuple[FPAPartInfo, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fpaPartPickerDialog")
        self.setWindowTitle("FPA part library")
        self.resize(1000, 560)
        self._parts = parts

        layout = QVBoxLayout(self)

        self._table = QTableWidget(len(parts), len(_COLUMNS), self)
        self._table.setObjectName("fpaPartTable")
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        for row, info in enumerate(parts):
            census = ", ".join(f"{n} {basis}" for basis, n in info.basis_counts)
            kind = "ROIC — needs detector" if info.part_kind == "roic" else "FPA"
            # Model first — it carries the identity; long vendor prefixes were
            # eliding the distinctive text (owner live-review 2026-09-06).
            cells = (
                f"{info.model} — {info.vendor}",
                kind,
                _CLASS_LABELS.get(info.part_class, info.part_class),
                info.band_label,
                f"{info.parameter_count} ({census})",
            )
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, info.name)
                item.setToolTip(text)
                self._table.setItem(row, col, item)
        header = self._table.horizontalHeader()
        # The Part (name) column takes the slack (owner live-review 2026-09-06:
        # "we need the name column larger") — Kind/Class stay content-sized, and
        # the wordy Band and census columns get bounded, elidable widths so they
        # cannot starve the names into "Teledyne e…".
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(3, 230)
        self._table.setColumnWidth(4, 190)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._table.setWordWrap(False)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self._table, 2)

        details_row = QWidget(self)
        details_box = QHBoxLayout(details_row)
        details_box.setContentsMargins(0, 0, 0, 0)
        self._details = QLabel("Select a part to see its description and citations.", details_row)
        self._details.setObjectName("fpaPartDetails")
        self._details.setWordWrap(True)
        self._details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_box.addWidget(self._details, 1)
        layout.addWidget(details_row, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText("Apply preset")
            ok.setEnabled(False)
        self._ok = ok
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- selection -----------------------------------------------------------

    def selected_part(self) -> str | None:
        """The selected part name, or ``None``."""
        items = self._table.selectedItems()
        if not items:
            return None
        return str(items[0].data(Qt.ItemDataRole.UserRole))

    def select_part(self, name: str) -> None:
        """Programmatically select *name*'s row (tests + reopening)."""
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                self._table.selectRow(row)
                return

    def _on_selection(self) -> None:
        name = self.selected_part()
        info = next((p for p in self._parts if p.name == name), None)
        if self._ok is not None:
            self._ok.setEnabled(info is not None)
        if info is None:
            return
        sources = "; ".join(s.title for s in info.sources)
        kind_note = (
            "Bare ROIC: detector-side values (QE, dark, band) belong to the mated "
            "diode — set them per study (Gap 121). "
            if info.part_kind == "roic"
            else ""
        )
        self._details.setText(f"{info.name} — {kind_note}{info.description}\nSources: {sources}")


__all__ = ["FPAPartPickerDialog"]
