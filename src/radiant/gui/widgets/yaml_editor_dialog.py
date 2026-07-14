"""The roomy in-app YAML config editor modal (arch doc §4.5).

:class:`YamlEditorDialog` is what the right-rail **Edit Config (YAML)** button opens: a
large :class:`QPlainTextEdit` preloaded with the current config YAML (via
:func:`radiant.gui.yaml_format.serialize_yaml`, the ``Sensor.save`` round-trip), with
**Apply / Revert / Cancel**.

**Apply re-parses the edited text through the framework** and never corrupts the live
sensor: the text is loaded into a *fresh* :class:`~radiant.api.sensor.Sensor` via
:meth:`Sensor.load` (round-tripped through a temp file — there is no string-load surface,
Gap 88). Only on success is the new sensor handed back (via :attr:`configApplied`) so the
caller can swap it in and re-evaluate; on failure the live sensor is untouched and the
dialog stays open with the bad text so the user can fix it:

* a :class:`~radiant.core.exceptions.RadiantError` (e.g. a YAML/`ConfigError`) shows the
  actionable :class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`
  (what / why / action, Rule 15);
* any other exception shows the traceback dialog — surfaced, never swallowed (Rule 17).

**Revert** restores the editor to the current config text. **Cancel** closes without
applying. One widget class per file (Rule 19); styling is entirely themed via object
names (GUI plan §4.9), so this file holds no colour/font/size literal.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog
from radiant.gui.yaml_format import serialize_yaml

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

logger = logging.getLogger(__name__)

_TITLE: str = "Edit Configuration"
_CAP: str = "Apply re-parses through the framework; invalid YAML leaves the config unchanged."


def load_sensor_from_text(yaml_text: str) -> Sensor:
    """Parse *yaml_text* into a fresh :class:`Sensor` via the public loader.

    ``Sensor.load`` takes a path only (no string-load surface — Gap 88), so the text is
    written to a throwaway temp file and loaded back. Any parse/validation failure
    propagates to the caller — the live sensor is never touched here.
    """
    from radiant.api.sensor import Sensor

    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="radiant_gui_yaml_edit_")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(yaml_text)
        return Sensor.load(tmp_path)
    finally:
        # Best-effort cleanup; a failed unlink is benign (the OS reclaims the temp
        # dir) but it is logged, never silently swallowed (Rule 17).
        try:
            os.unlink(tmp_path)
        except OSError as exc:  # pragma: no cover - benign
            logger.debug("Could not remove temp YAML file %s: %s", tmp_path, exc)


class YamlEditorDialog(QDialog):
    """A roomy editable YAML modal; Apply validates on a fresh sensor (arch doc §4.5).

    Parameters
    ----------
    sensor:
        The live :class:`~radiant.api.sensor.Sensor`; its serialized config preloads the
        editor. Never mutated by this dialog.
    parent:
        The owning widget, if any.

    Signals
    -------
    configApplied(object):
        Emitted with the freshly-parsed :class:`Sensor` when Apply succeeds; the caller
        swaps it in and re-evaluates. Not emitted on failure.
    """

    configApplied = Signal(object)

    def __init__(self, sensor: Sensor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("yamlEditorDialog")
        self.setWindowTitle(_TITLE)
        self.setModal(True)
        self.resize(680, 560)

        self._sensor = sensor
        self._original_text = serialize_yaml(sensor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        header = QLabel(_TITLE, self)
        header.setObjectName("yamlEditorHeader")
        layout.addWidget(header)

        self._editor = QPlainTextEdit(self)
        self._editor.setObjectName("yamlEditorText")
        self._editor.setPlainText(self._original_text)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._editor, 1)

        caption = QLabel(_CAP, self)
        caption.setObjectName("yamlEditorCaption")
        caption.setWordWrap(True)
        layout.addWidget(caption)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._apply_button = QPushButton("Apply", self)
        self._apply_button.setObjectName("yamlApplyButton")
        self._apply_button.setProperty("primary", True)
        self._apply_button.clicked.connect(self._on_apply)
        self._revert_button = QPushButton("Revert", self)
        self._revert_button.setObjectName("yamlRevertButton")
        self._revert_button.clicked.connect(self._on_revert)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("yamlCancelButton")
        self._cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self._apply_button)
        buttons.addWidget(self._revert_button)
        buttons.addWidget(self._cancel_button)
        layout.addLayout(buttons)

    # -- accessors (tests) --------------------------------------------------

    @property
    def editor(self) -> QPlainTextEdit:
        """The YAML text editor."""
        return self._editor

    @property
    def apply_button(self) -> QPushButton:
        """The Apply button."""
        return self._apply_button

    @property
    def revert_button(self) -> QPushButton:
        """The Revert button."""
        return self._revert_button

    def yaml_text(self) -> str:
        """The current editor text (plain text)."""
        return self._editor.toPlainText()

    # -- actions ------------------------------------------------------------

    def _on_apply(self) -> None:
        """Validate the edited text on a fresh sensor; swap in only on success.

        The live sensor is never mutated here — the text is parsed into a *new*
        ``Sensor`` first (§4.1 validate-before-commit). On failure the actionable /
        traceback dialog is shown and this dialog stays open with the bad text.
        """
        text = self._editor.toPlainText()
        try:
            new_sensor = load_sensor_from_text(text)
        except RadiantError as exc:
            ActionableErrorDialog(exc, "Edit Config (YAML)", self).exec()
            return
        except Exception as exc:  # surfaced, never swallowed (Rules 15/17)
            UnexpectedErrorDialog(exc, "Parsing the edited YAML config", self).exec()
            return
        self.configApplied.emit(new_sensor)
        self.accept()

    def _on_revert(self) -> None:
        """Restore the editor to the current config text (the preloaded serialization)."""
        self._editor.setPlainText(self._original_text)


__all__ = ["YamlEditorDialog", "load_sensor_from_text"]
