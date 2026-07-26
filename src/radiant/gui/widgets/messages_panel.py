"""The right-rail Messages panel: warnings and errors (arch doc §4.5).

:class:`MessagesPanel` is the bottom section of the persistent right rail. It replaces
the shipped floating chain-warning strip, widened to carry **errors** as well as
warnings (§4.5, §4.7):

* **Warnings** — the chain ``UserWarning``s ``ConfigurationSet.evaluate_all`` captured for
  the last evaluation (saturation clip, NIIRS extrapolation, …), attributed per
  configuration and prefixed with the configuration name in a multi-configuration
  study. Each is a
  clickable :class:`~radiant.gui.widgets.message_item.MessageItem` (warn token); clicking
  any opens the verbatim :class:`~radiant.gui.widgets.warning_list_dialog.WarningListDialog`
  (the shipped full list). Nothing is swallowed (Rule 17) — the worker also re-logs them.
* **Errors** — a failed evaluation's :class:`~radiant.core.exceptions.RadiantError` renders
  here as an err-token item showing its actionable ``what``; clicking opens the full
  :class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`
  (what / why / action, Rule 15).
* **Per-configuration failures** — in a multi-configuration study, a configuration that
  failed while it was *not* the displayed one renders here as a named error item
  (:meth:`MessagesPanel.set_configuration_failures`) instead of interrupting the session
  with a modal. Nothing is dropped; the study keeps running on the configurations that
  succeeded (Rule 17).

The panel clears/repopulates each evaluation: :meth:`set_warnings` on success,
:meth:`set_error` on failure (the error item persists alongside the last warnings until
the next result). One widget class per file (Rule 19); styling is entirely themed via
object names (GUI plan §4.9), so this file holds no colour/font/size literal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.message_item import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    MessageItem,
)
from radiant.gui.widgets.warning_list_dialog import WarningListDialog

_EMPTY_TEXT: str = "No messages — the last run was clean."


def _payload_what(exc: BaseException) -> str:
    """The one-line ``what`` of *exc* (a structured RadiantError's field, else its str)."""
    return str(getattr(exc, "what", "") or exc)


class MessagesPanel(QWidget):
    """The Messages rail section: clickable warning + error rows (arch doc §4.5).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("messagesPanel")

        self._warnings: list[str] = []
        self._error: BaseException | None = None
        self._config_errors: dict[str, BaseException] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        header = QWidget(self)
        header.setObjectName("railSectionHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        self._title = QLabel("Messages", header)
        self._title.setObjectName("railSectionTitle")
        self._count = QLabel("", header)
        self._count.setObjectName("railSectionCount")
        header_layout.addWidget(self._title)
        header_layout.addWidget(self._count)
        layout.addWidget(header)

        self._items_host = QWidget(self)
        self._items_layout = QVBoxLayout(self._items_host)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(7)
        layout.addWidget(self._items_host)

        self._empty = QLabel(_EMPTY_TEXT, self)
        self._empty.setObjectName("messagesEmpty")
        self._empty.setWordWrap(True)
        layout.addWidget(self._empty)

        layout.addStretch(1)
        self._rebuild()

    # -- accessors ----------------------------------------------------------

    @property
    def warnings(self) -> list[str]:
        """The warnings currently listed."""
        return list(self._warnings)

    @property
    def warning_count(self) -> int:
        """How many warnings the panel currently lists."""
        return len(self._warnings)

    @property
    def error(self) -> BaseException | None:
        """The error currently listed (``None`` when the last run did not fail)."""
        return self._error

    def has_error(self) -> bool:
        """True iff an error item is currently shown."""
        return self._error is not None

    @property
    def configuration_errors(self) -> dict[str, BaseException]:
        """Per-configuration failures currently listed (name → recorded error).

        Populated by the multi-configuration evaluate-all pass for the
        configurations that are **not** displayed: their failure is a Messages
        entry naming the configuration, never a modal (a modal for a
        configuration the user is not looking at would block the study). The
        displayed configuration's failure still takes the ordinary
        :meth:`set_error` + modal path. Empty for a single-configuration
        session, so that session's panel is byte-for-byte today's.
        """
        return dict(self._config_errors)

    # -- update -------------------------------------------------------------

    def set_warnings(self, messages: Sequence[str]) -> None:
        """Replace the warning list (and clear any error) — the success path.

        Called after a successful evaluation: a warning-free run leaves the panel
        empty (owner feedback 2026-07-13, Rule 17).
        """
        self._warnings = list(messages)
        self._error = None
        self._rebuild()

    def set_error(self, exc: BaseException | None) -> None:
        """Set (or clear) the error item shown alongside the last warnings — the failure path."""
        self._error = exc
        self._rebuild()

    def set_configuration_failures(self, failures: Mapping[str, BaseException]) -> None:
        """Replace the per-configuration failure items (multi-configuration Phase 4a).

        Each entry renders as an error-token row reading
        ``<name>: <the error's what line>`` and clicking it opens the full
        actionable dialog, so a configuration that failed in the background is
        named and inspectable rather than silently missing (Rule 17). Passing an
        empty mapping clears them — which is what every single-configuration
        evaluation does.
        """
        self._config_errors = dict(failures)
        self._rebuild()

    def clear(self) -> None:
        """Clear every message (warnings, error, per-configuration failures)."""
        self._warnings = []
        self._error = None
        self._config_errors = {}
        self._rebuild()

    # -- internal -----------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild the message rows from the current warnings + error state."""
        while self._items_layout.count():
            item = self._items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for message in self._warnings:
            row = MessageItem(message, SEVERITY_WARNING, self._items_host)
            row.clicked.connect(self._open_warning_list)
            self._items_layout.addWidget(row)

        if self._error is not None:
            row = MessageItem(_payload_what(self._error), SEVERITY_ERROR, self._items_host)
            row.clicked.connect(self._open_error_dialog)
            self._items_layout.addWidget(row)

        for name, exc in self._config_errors.items():
            row = MessageItem(f"{name}: {_payload_what(exc)}", SEVERITY_ERROR, self._items_host)
            row.clicked.connect(
                lambda _checked=False, e=exc: ActionableErrorDialog(e, "evaluate", self).exec()
            )
            self._items_layout.addWidget(row)

        has_any = bool(self._warnings) or self._error is not None or bool(self._config_errors)
        self._empty.setVisible(not has_any)
        self._update_count()

    def _update_count(self) -> None:
        """Refresh the header count line (warnings + errors)."""
        n_warn = len(self._warnings)
        n_err = len(self._config_errors) + (1 if self._error is not None else 0)
        parts: list[str] = []
        if n_warn:
            parts.append(f"{n_warn} warning{'s' if n_warn != 1 else ''}")
        if n_err:
            parts.append(f"{n_err} error{'s' if n_err != 1 else ''}")
        self._count.setText(", ".join(parts) if parts else "clean")

    def _open_warning_list(self) -> WarningListDialog:
        """Open the verbatim warning list (the shipped dialog); returned for tests."""
        dialog = WarningListDialog(self._warnings, self)
        dialog.exec()
        return dialog

    def _open_error_dialog(self) -> ActionableErrorDialog | None:
        """Open the actionable error dialog for the current error; returned for tests."""
        if self._error is None:  # pragma: no cover - guarded by the item's presence
            return None
        dialog = ActionableErrorDialog(self._error, "evaluate", self)
        dialog.exec()
        return dialog


__all__ = ["MessagesPanel"]
