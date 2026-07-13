"""The YAML detail tab (arch doc §4.5): read-only current config + Export.

:class:`YamlTab` shows the **current config** the way the scripting API serialises it —
via the one public serialize surface (:meth:`Sensor.save`, round-tripped through
:func:`radiant.gui.yaml_format.serialize_yaml`) — as read-only mono-font text, with each
parameter line **tinted by its provenance** (user-set / config / default / derived /
sampled), reusing the Phase-2 provenance path. An **Export…** button writes the same YAML
to a user-chosen file through :meth:`Sensor.save` — the tab's only file I/O.

Provenance colours are resolved at render time from the active theme
(:func:`radiant.gui.themes.active_theme`) via
:data:`radiant.gui.yaml_format.PROVENANCE_TOKEN`, which names a theme **attribute**, never
a colour literal — so every value still lives in ``themes/`` (GUI plan §4.9). The text is
the *inputs* scope and round-trips through :meth:`Sensor.load` exactly (defaults / derived
values re-apply on load); a fully-resolved export needs a serialize surface the public API
does not expose (**Gap 88**).

Pre-result the tab shows a themed "evaluate first" state; :meth:`show_sensor` fills it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.themes import active_theme
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog
from radiant.gui.yaml_format import (
    PROVENANCE_TOKEN,
    dotpath_provenance,
    line_provenance,
    serialize_yaml,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

_EMPTY: Final[str] = "YAML — evaluate (or load a config) to populate."
_EXPORT_CAPTION: Final[str] = "Export config as YAML"
_EXPORT_FILTER: Final[str] = "YAML config (*.yaml *.yml)"


class YamlTab(QWidget):
    """Read-only provenance-coloured current config + Export button (arch doc §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("yamlTab")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedWidget(self)

        self._empty = QLabel(_EMPTY, self)
        self._empty.setObjectName("detailPlaceholderMsg")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 8, 10, 10)
        content_layout.setSpacing(8)

        self._view = QTextEdit(self._content)
        self._view.setObjectName("yamlView")
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)
        self._export_button = QPushButton("Export…", self._content)
        self._export_button.setObjectName("yamlExportButton")
        self._export_button.clicked.connect(self._on_export_clicked)
        button_row.addWidget(self._export_button)

        content_layout.addWidget(self._view, 1)
        content_layout.addLayout(button_row)

        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._content)
        outer.addWidget(self._stack)

        self._sensor: Sensor | None = None

    # -- accessors (tests) --------------------------------------------------

    @property
    def view(self) -> QTextEdit:
        """The read-only YAML text view."""
        return self._view

    @property
    def export_button(self) -> QPushButton:
        """The Export… button."""
        return self._export_button

    def is_populated(self) -> bool:
        """True once a sensor has been shown (content page active)."""
        return self._stack.currentWidget() is self._content

    def yaml_text(self) -> str:
        """The serialised YAML currently displayed (plain text, for tests)."""
        return self._view.toPlainText()

    # -- result delivery ----------------------------------------------------

    def show_sensor(self, sensor: Sensor) -> None:
        """Serialise *sensor*'s current config and render it, provenance-tinted."""
        self._sensor = sensor
        yaml_text = serialize_yaml(sensor)
        tokens = dotpath_provenance(sensor)
        self._render(line_provenance(yaml_text, tokens))
        self._stack.setCurrentWidget(self._content)

    def _render(self, lines: list[tuple[str, str | None]]) -> None:
        """Fill the view, tinting each line by its provenance token (theme-resolved)."""
        theme = active_theme()
        self._view.clear()
        cursor = self._view.textCursor()
        for text, token in lines:
            fmt = QTextCharFormat()
            attr = PROVENANCE_TOKEN.get(token) if token is not None else None
            if attr is not None:
                fmt.setForeground(QColor(getattr(theme, attr)))
            cursor.insertText(text + "\n", fmt)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._view.setTextCursor(cursor)

    # -- export (the tab's only file I/O) -----------------------------------

    def export_to(self, path: str) -> None:
        """Write the current config to *path* via :meth:`Sensor.save` (public surface).

        Used directly by tests; the button handler calls this after the file dialog.
        A failure surfaces (Rules 15/17) — the button handler renders the exception
        (message + traceback) in a dialog rather than swallowing it.
        """
        if self._sensor is None:  # pragma: no cover - button disabled pre-populate
            return
        self._sensor.save(path)

    def _on_export_clicked(self) -> None:
        """Open a save dialog and export the current config, surfacing any error."""
        if self._sensor is None:  # pragma: no cover - button disabled pre-populate
            return
        path, _selected = QFileDialog.getSaveFileName(
            self, _EXPORT_CAPTION, "", _EXPORT_FILTER
        )
        if not path:
            return
        try:
            self.export_to(path)
        except Exception as exc:  # surface, never swallow (Rules 15/17)
            UnexpectedErrorDialog(exc, "Exporting the config to YAML", self).exec()
