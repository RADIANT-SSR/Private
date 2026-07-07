"""Settings dialog — theme picker + default frame.

Phase 6 (PLAN_v2.md §14 step 4): the spec lists Theme dropdown,
default frame, display units, font size, and label-density. The Phase-6
deliverable ships theme + default-frame; the remaining three (units,
font size, label density) are deferred — see CU-040 in
``docs/tracking/Cleanup_Backlog.md``.

Rule 19: own file.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from dev_tools.geometry_gui_v2.app.interaction_state import DisplayFrame
from dev_tools.geometry_gui_v2.app.theme import SUPPORTED_THEMES


class SettingsDialog(QDialog):
    """Modal Settings dialog. Emits chosen values via accessor methods.

    Caller usage::

        dlg = SettingsDialog(current_theme_xml, current_frame, parent)
        if dlg.exec() == QDialog.Accepted:
            new_theme = dlg.selected_theme()
            new_frame = dlg.selected_default_frame()
    """

    def __init__(
        self,
        current_theme_xml: str,
        current_frame: DisplayFrame,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_dialog")
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Theme dropdown ----------------------------------------------------
        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("settings_theme_combo")
        for label, xml in SUPPORTED_THEMES.items():
            self._theme_combo.addItem(label, xml)
        # Restore the current selection by data match (not label match) — the
        # data is the canonical key, the label is presentation.
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_theme_xml:
                self._theme_combo.setCurrentIndex(i)
                break
        form.addRow("Theme:", self._theme_combo)

        # Default frame dropdown -------------------------------------------
        self._frame_combo = QComboBox()
        self._frame_combo.setObjectName("settings_frame_combo")
        for frame in DisplayFrame:
            self._frame_combo.addItem(frame.display_name, frame)
        self._frame_combo.setCurrentIndex(
            list(DisplayFrame).index(current_frame)
        )
        form.addRow("Default frame:", self._frame_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_theme(self) -> str:
        """Return the chosen theme xml key (e.g. ``dark_teal.xml``)."""
        return str(self._theme_combo.currentData())

    def selected_default_frame(self) -> DisplayFrame:
        return self._frame_combo.currentData()  # type: ignore[no-any-return]
