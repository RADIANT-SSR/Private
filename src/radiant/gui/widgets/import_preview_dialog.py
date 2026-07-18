"""Modal confirm-before-Apply preview for spectral import files (ADR-0009 D5).

:class:`ImportPreviewDialog` is the shared import flow the scenario docs ask for:
*pick file → see the parsed curve + metadata → Apply or Cancel*. Parsing runs
through :func:`radiant.api.preview_spectral_import` — the identical loader the
attach-time path takes (single validation authority), so a file that previews
cleanly binds cleanly. Nothing is mutated here: the **caller** commits the
accepted path with its one ``sensor.set`` (the same division of labour as the
element editor and the Zemax import).

The info line carries the parse facts with units (R-UNITS): point count, λ span
[µm], per-series value ranges. A parse failure shows the loader's actionable
message inline (what/why/action — never a silent blank), and Apply stays
disabled until a file parses.

One widget class per file (Rule 19); styling from the QSS theme via object
names; the figure is drawn with the same matplotlib embedding as every canvas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.config_io import preview_spectral_import
from radiant.core.exceptions import RadiantError
from radiant.gui.errors import GuiValidationError
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.api.config_io import SpectralImportPreview

# kind -> (window title, file-dialog filter)
_KINDS: dict[str, tuple[str, str]] = {
    "qe_csv": ("Import QE curve", "CSV (*.csv);;All files (*)"),
    "tape7": ("Import MODTRAN tape7", "tape7 (*.tp7 *.7sc *_tape7* tape7*);;All files (*)"),
}


class ImportPreviewDialog(QDialog):
    """Pick a spectral file, preview the parsed curve, Apply or Cancel."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in _KINDS:
            raise GuiValidationError(f"ImportPreviewDialog: unknown kind {kind!r}")
        self._kind = kind
        title, self._filter = _KINDS[kind]
        self.setObjectName("importPreviewDialog")
        self.setWindowTitle(title)
        self.resize(560, 480)

        self._path: str | None = None

        layout = QVBoxLayout(self)

        picker_row = QWidget(self)
        row = QHBoxLayout(picker_row)
        row.setContentsMargins(0, 0, 0, 0)
        self._path_label = QLabel("No file selected", picker_row)
        self._path_label.setObjectName("importPathLabel")
        self._browse = QPushButton("Browse…", picker_row)
        self._browse.clicked.connect(self._on_browse)
        row.addWidget(self._path_label, 1)
        row.addWidget(self._browse)
        layout.addWidget(picker_row)

        self._canvas = MatplotlibCanvas(self)
        layout.addWidget(self._canvas, 1)

        self._info = QLabel("", self)
        self._info.setObjectName("importInfoLabel")
        self._info.setWordWrap(True)
        layout.addWidget(self._info)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        self._buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # -- flow -----------------------------------------------------------------

    def _on_browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.windowTitle(), "", self._filter)
        if filename:
            self.load_path(filename)

    def load_path(self, path: str) -> bool:
        """Parse *path* via the facade; render the curve or the actionable error.

        Returns True (and arms Apply) on a clean parse.
        """
        try:
            preview = preview_spectral_import(self._kind, path)
        except (RadiantError, FileNotFoundError) as exc:
            self._path = None
            self._path_label.setText(path)
            self._info.setText(f"Parse failed — {exc}")
            self._buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
            return False
        self._path = path
        self._path_label.setText(path)
        self._render(preview)
        self._buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)
        return True

    def _render(self, preview: SpectralImportPreview) -> None:
        figure = Figure(figsize=(5.2, 3.2), tight_layout=True)
        axis = figure.add_subplot(111)
        for label, values in preview.series:
            axis.plot(preview.wavelength_um, values, label=label)
        axis.set_xlabel("Wavelength [µm]")
        axis.legend(fontsize=8)
        axis.grid(True, alpha=0.3)
        self._canvas.show_figure(figure)

        wl = preview.wavelength_um
        ranges = "; ".join(
            f"{label}: {values.min():.4g}–{values.max():.4g}" for label, values in preview.series
        )
        self._info.setText(f"{preview.n_points} points · λ {wl.min():g}–{wl.max():g} µm · {ranges}")

    def selected_path(self) -> str | None:
        """The parsed-and-accepted file path (None before a clean parse)."""
        return self._path

    # -- accessors (tests) ------------------------------------------------------

    def apply_enabled(self) -> bool:
        """Whether Apply is armed (tests)."""
        return self._buttons.button(QDialogButtonBox.StandardButton.Apply).isEnabled()

    @property
    def info_text(self) -> str:
        """The info-line text (tests)."""
        return self._info.text()


__all__ = ["ImportPreviewDialog"]
