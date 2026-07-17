"""Tools → Compare Measured MTF… — lab points over the predicted curve (Tier-2 GT-5).

:class:`MtfOverlayDialog` is the measurement-overlay surface (GUI-4, persona-7
workflows): pick a two-column measured MTF file (frequency, MTF), and the dialog
runs the shipped :func:`radiant.api.compare_mtf` against the **last result** —
rendering the predicted curve, the measured points, and a residual sub-plot,
with the RMS / max-abs residual stats (unit-labeled) in the status line. Axis
(cross/along-track) and frequency unit are selectable; the comparison is
overlap-only by contract (points outside the predicted range are excluded by
the API and the count shows how many compared).

One widget class per file (Rule 19); parse errors surface actionably inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api import compare_mtf
from radiant.api.config_io import load_measured_curve_file
from radiant.core.exceptions import RadiantError
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.io.results import ChainResult

_FREQ_UNITS = ("cy/m", "cy/mm", "cy/px", "normalized")


class MtfOverlayDialog(QDialog):
    """Overlay a measured MTF file on the predicted curve, with residuals (GT-5)."""

    def __init__(self, result: ChainResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mtfOverlayDialog")
        self.setWindowTitle("Compare Measured MTF")
        self.resize(640, 560)
        self._result = result
        self.comparison: Any | None = None

        layout = QVBoxLayout(self)
        top = QWidget(self)
        row = QHBoxLayout(top)
        row.setContentsMargins(0, 0, 0, 0)
        self._path_label = QLabel("No file selected", top)
        self._browse = QPushButton("Browse…", top)
        self._browse.clicked.connect(self._on_browse)
        row.addWidget(self._path_label, 1)
        row.addWidget(QLabel("Axis:"))
        self._axis = QComboBox(top)
        self._axis.addItems(["x", "y"])
        row.addWidget(self._axis)
        row.addWidget(QLabel("Frequency unit:"))
        self._freq_unit = QComboBox(top)
        self._freq_unit.addItems(list(_FREQ_UNITS))
        row.addWidget(self._freq_unit)
        row.addWidget(self._browse)
        layout.addWidget(top)

        self._canvas = MatplotlibCanvas(self)
        layout.addWidget(self._canvas, 1)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        layout.addWidget(box)

    def _on_browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Measured MTF file", "", "Measured data (*.csv *.txt);;All files (*)"
        )
        if filename:
            self.load_path(filename)

    def load_path(self, path: str) -> bool:
        """Load + compare + render; actionable error inline on failure."""
        self._path_label.setText(path)
        try:
            measured = load_measured_curve_file(path)
            comparison = compare_mtf(
                self._result,
                measured,
                axis=self._axis.currentText(),
                frequency_unit=self._freq_unit.currentText(),
            )
        except RadiantError as exc:
            self._status.setText(f"Comparison failed — {exc}")
            self.comparison = None
            return False
        self.comparison = comparison
        self._render(comparison)
        unit = self._freq_unit.currentText()
        self._status.setText(
            f"{comparison.n_compared} points compared (overlap-only) · "
            f"RMS residual {comparison.rms_residual:.4g} · "
            f"max |residual| {comparison.max_abs_residual:.4g} · frequency in {unit}"
        )
        return True

    def _render(self, comparison: Any) -> None:
        figure = Figure(figsize=(5.6, 4.0), tight_layout=True)
        top = figure.add_subplot(211)
        top.plot(comparison.freq_cy_m, comparison.predicted, label="predicted")
        top.plot(comparison.freq_cy_m, comparison.measured, "o", ms=4, label="measured")
        top.set_ylabel("MTF [-]")
        top.legend(fontsize=8)
        top.grid(True, alpha=0.3)
        bottom = figure.add_subplot(212, sharex=top)
        bottom.plot(comparison.freq_cy_m, comparison.residual, "o-", ms=3)
        bottom.axhline(0.0, lw=0.8)
        bottom.set_xlabel("Spatial frequency [cy/m]")
        bottom.set_ylabel("measured − predicted")
        bottom.grid(True, alpha=0.3)
        self._canvas.show_figure(figure)

    @property
    def status_text(self) -> str:
        """The status-line text (tests)."""
        return self._status.text()


__all__ = ["MtfOverlayDialog"]
