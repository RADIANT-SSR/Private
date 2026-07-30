"""The roomy in-app YAML document editor modal (arch doc §4.5, §4.2f).

:class:`YamlEditorDialog` is what the right-rail **Edit Config (YAML)** button opens: a
large :class:`QPlainTextEdit` preloaded with the session **document**'s YAML (via
:func:`radiant.gui.document_yaml.serialize_document`), with **Apply / Revert / Cancel**.

**The document, not one configuration** (multi-configuration Phase 4e). The session
document is a :class:`~radiant.api.config_set.ConfigurationSet`, so a study's text is
the full study — the shared body **plus** its ``configurations:`` section — and a plain
single-configuration session's text is exactly what it always was, with no section.
:mod:`radiant.gui.document_yaml` makes that choice once for every surface that
serializes or re-reads the document.

**Apply re-parses the edited text through the framework** and never corrupts the live
document: the text is loaded into a *fresh* ``ConfigurationSet`` via
:func:`~radiant.gui.document_yaml.load_document_from_text` (round-tripped through a temp
file — there is no string-load surface, Gap 88). Only on success is the new document
handed back (via :attr:`configApplied`) so the caller can swap it in and re-evaluate; on
failure the live document is untouched and the dialog stays open with the bad text so the
user can fix it:

* a :class:`~radiant.core.exceptions.RadiantError` (e.g. a YAML/`ConfigError`, which for
  a section violation already names the configuration and the parameter) shows the
  actionable :class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`
  (what / why / action, Rule 15);
* any other exception shows the traceback dialog — surfaced, never swallowed (Rule 17).

Because Apply goes through the ordinary loader, **editing the section away is a legal
edit**: the parsed document is then the degenerate one-configuration set and the window
adopts it as a plain session (the selector band disappears). That is the analyst's
explicit instruction, typed into the document, not a silent collapse by the GUI.

**Revert** restores the editor to the current document text. **Cancel** closes without
applying. One widget class per file (Rule 19); styling is entirely themed via object
names (GUI plan §4.9), so this file holds no colour/font/size literal.
"""

from __future__ import annotations

import logging
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
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.document_yaml import is_study, load_document_from_text, serialize_document
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet

logger = logging.getLogger(__name__)

_TITLE: str = "Edit Configuration"
_CAP: str = "Apply re-parses through the framework; invalid YAML leaves the config unchanged."
_STUDY_CAP: str = (
    "This is the whole study — the shared parameters plus the configurations: section. "
    "Apply re-parses through the framework; invalid YAML leaves the study unchanged."
)


class YamlEditorDialog(QDialog):
    """A roomy editable YAML modal; Apply validates on a fresh document (arch doc §4.5).

    Parameters
    ----------
    config_set:
        The live session document. Never mutated by this dialog — its serialization
        preloads the editor and Apply parses a *new* set from the edited text.
    parent:
        The owning widget, if any.

    Signals
    -------
    configApplied(object):
        Emitted with the freshly-parsed
        :class:`~radiant.api.config_set.ConfigurationSet` when Apply succeeds; the
        caller adopts it and re-evaluates. Not emitted on failure.
    """

    configApplied = Signal(object)

    def __init__(self, config_set: ConfigurationSet, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("yamlEditorDialog")
        self.setWindowTitle(_TITLE)
        self.setModal(True)
        self.resize(680, 560)

        self._config_set = config_set
        self._original_text = serialize_document(config_set)

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

        caption = QLabel(_STUDY_CAP if is_study(config_set) else _CAP, self)
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
        """Validate the edited text on a fresh document; hand it back only on success.

        The live document is never mutated here — the text is parsed into a *new*
        ``ConfigurationSet`` first (§4.1 validate-before-commit). On failure the
        actionable / traceback dialog is shown and this dialog stays open with the bad
        text.
        """
        text = self._editor.toPlainText()
        try:
            new_document = load_document_from_text(text)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, "Edit Config (YAML)", self))
            return
        except Exception as exc:  # surfaced, never swallowed (Rules 15/17)
            exec_dialog(UnexpectedErrorDialog(exc, "Parsing the edited YAML config", self))
            return
        self.configApplied.emit(new_document)
        self.accept()

    def _on_revert(self) -> None:
        """Restore the editor to the current document text (the preloaded serialization)."""
        self._editor.setPlainText(self._original_text)


__all__ = ["YamlEditorDialog"]
