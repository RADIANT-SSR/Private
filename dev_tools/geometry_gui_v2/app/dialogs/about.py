"""About dialog — product name, version, license, attribution.

Phase 6 (PLAN_v2.md §14 step 5 + 8): leads with ``RADIANT Geometry
Module`` (D2 resolved 2026-04-26 — the "Vision Studio" naming is
dropped). Includes a credits paragraph for PyVista / VTK / Qt /
qt-material.

Rule 19: own file.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# Single source of truth for the product name + version. The Phase-7
# packaging task wires this to ``importlib.metadata.version`` once a
# pyproject.toml ships; for now it's a literal that the About dialog and
# any future ``--version`` CLI both read from.
PRODUCT_NAME: Final[str] = "RADIANT Geometry Module"
SHORT_VERSION: Final[str] = "0.6.0-phase6"


class AboutDialog(QDialog):
    """Modal About dialog. Constructed once per invocation, not cached."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setWindowTitle("About")

        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{PRODUCT_NAME}</h2>")
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)

        version = QLabel(f"<b>Version:</b> {SHORT_VERSION}")
        version.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(version)

        body = QLabel(
            "<p>Geometry module of the RADIANT GUI — a first-principles EO "
            "sensor performance modeling framework.</p>"
            "<p><b>License:</b> Internal to RADIANT (LGPL components: PySide6, "
            "qt-material; BSD: PyVista, VTK; numpy + scipy: BSD).</p>"
            "<p><b>Built on:</b> PyVista, VTK, PySide6, pyvistaqt, "
            "qt-material.</p>"
        )
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
