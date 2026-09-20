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
file — there is no string-load surface, Gap 88), and that fresh document is then
**resolved** (:func:`~radiant.gui.document_yaml.document_rejection`, CU-372 F-32) with the
same differential posture as every other commit path: an incomplete document is admitted
(Evaluate's advisory names what is missing), a wrong value — out of bounds, a bad enum, an
over-constrained group — is refused. Only on success is the new document handed back (via
:attr:`configApplied`) so the caller can swap it in and re-evaluate; on failure the live
document is untouched and the dialog stays open with the bad text so the user can fix it:

* a :class:`~radiant.core.exceptions.RadiantError` (a YAML/`ConfigError`, which for a
  section violation already names the configuration and the parameter, or a resolve
  failure) renders its what / why / action **inline** in the dialog's themed error area,
  beneath the text it refers to (Rule 15) — the dialog never raises a modal over itself;
* any other exception shows the traceback dialog — surfaced, never swallowed (Rule 17).

The editor **always opens**, on an unresolvable document too: the serialization it
preloads never resolves. Before F-32 an out-of-bounds value that reached the live sensor
left the editor unable to reopen (the serializer raised the bounds error first), so the
one surface that could have fixed the document was the one that was dead.

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
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.document_yaml import (
    document_rejection,
    is_study,
    load_document_from_text,
    serialize_document,
)
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet

logger = logging.getLogger(__name__)

_TITLE: str = "Edit Configuration"
_CAP: str = (
    "Apply re-parses and resolves through the framework; invalid YAML or a value the "
    "framework refuses leaves the config unchanged."
)
_STUDY_CAP: str = (
    "This is the whole study — the shared parameters plus the configurations: section. "
    "Apply re-parses and resolves through the framework; invalid YAML or a value the "
    "framework refuses leaves the study unchanged."
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

        # Inline actionable-error area (hidden until an Apply is refused): the same
        # themed frame the Parameter Editor uses, so a refusal reads the same way
        # wherever it happens.
        self._last_rejection: RadiantError | None = None
        self._error_frame = QFrame(self)
        self._error_frame.setObjectName("paramEditorError")
        error_layout = QVBoxLayout(self._error_frame)
        error_layout.setContentsMargins(12, 10, 12, 10)
        error_layout.setSpacing(6)
        error_header = QLabel("Not applied", self._error_frame)
        error_header.setObjectName("errorDialogHeader")
        error_header.setWordWrap(True)
        error_layout.addWidget(error_header)
        self._error_form = QFormLayout()
        self._error_form.setSpacing(4)
        error_layout.addLayout(self._error_form)
        self._error_frame.setVisible(False)
        layout.addWidget(self._error_frame)

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

    @property
    def error_frame(self) -> QFrame:
        """The inline error area (visible only after a refused Apply)."""
        return self._error_frame

    @property
    def last_rejection(self) -> RadiantError | None:
        """The error the last refused Apply rendered inline (``None`` after a success)."""
        return self._last_rejection

    # -- actions ------------------------------------------------------------

    def _on_apply(self) -> None:
        """Parse and resolve the edited text on a fresh document; hand it back on success.

        The live document is never mutated here — the text is parsed into a *new*
        ``ConfigurationSet`` first, then that document is resolved
        (:func:`document_rejection`; §4.1 validate-before-commit, CU-372 F-32). A parse
        or resolve refusal renders inline and this dialog stays open with the bad
        text; a genuine bug gets the traceback dialog.
        """
        text = self._editor.toPlainText()
        try:
            new_document = load_document_from_text(text)
            rejection = document_rejection(new_document)
        except RadiantError as exc:
            self._show_rejection(exc)
            return
        except Exception as exc:  # surfaced, never swallowed (Rules 15/17)
            exec_dialog(UnexpectedErrorDialog(exc, "Parsing the edited YAML config", self))
            return
        if rejection is not None:
            self._show_rejection(rejection)
            return
        self._clear_rejection()
        self.configApplied.emit(new_document)
        self.accept()

    def _show_rejection(self, exc: RadiantError) -> None:
        """Render *exc*'s what / why / action in the inline error area; keep the dialog open."""
        self._clear_rejection()
        self._last_rejection = exc
        what = str(getattr(exc, "what", "") or exc)
        why = str(getattr(exc, "why", "") or "")
        action = str(getattr(exc, "action", "") or "")
        self._add_error_row("What", what)
        if why:
            self._add_error_row("Why", why)
        if action:
            self._add_error_row("Action", action)
        self._error_frame.setVisible(True)

    def _add_error_row(self, label: str, text: str) -> None:
        key = QLabel(label, self._error_frame)
        key.setObjectName("errorDialogKey")
        value = QLabel(text, self._error_frame)
        value.setObjectName("errorDialogValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(value.textInteractionFlags().TextSelectableByMouse)
        self._error_form.addRow(key, value)

    def _clear_rejection(self) -> None:
        """Hide the inline error area and drop its rows."""
        self._last_rejection = None
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        self._error_frame.setVisible(False)

    def _on_revert(self) -> None:
        """Restore the editor to the current document text (the preloaded serialization)."""
        self._editor.setPlainText(self._original_text)


__all__ = ["YamlEditorDialog"]
