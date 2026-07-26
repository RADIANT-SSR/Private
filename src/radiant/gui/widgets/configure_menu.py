"""The three multi-configuration context actions, in one place (Phase 4b).

Two surfaces offer the configure/edit/un-configure actions on a parameter — the
all-parameters tree (§4.3) and every per-stage form field (§4.4, via
:class:`~radiant.gui.widgets.field_row.FieldRow`). Their wording, order, and
enablement live here so the two can never drift into two different vocabularies for
the same three API calls.

The actions are pure intent: each routes through the
:class:`~radiant.gui.config_scope.ConfigurationScope`, whose only listener is the main
window — which makes the single ``ConfigurationSet`` call and records one undoable
command (R-API).

* **Configure across configurations…** — shown for a *shared* parameter. It stays
  enabled in a single-configuration session and answers with an actionable status
  message (there is no second configuration to hold a second value, and the
  configuration manager that would create one is Phase 4c); a silently disabled or
  absent item would leave the analyst guessing (Rule 17's spirit for UI state).
* **Edit configured values…** — shown for a *configured* parameter; opens the
  all-configurations table.
* **Un-configure (keep <first>'s value)…** — shown for a *configured* parameter, and
  named with the configuration whose value survives (ADR-0010 D-6) so the collapse is
  never a surprise physics change; the window's confirmation states the kept value
  with its unit before anything happens.

No colour/font/size literal lives here (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenu

    from radiant.gui.config_scope import ConfigurationScope

CONFIGURE_TEXT = "Configure across configurations…"
EDIT_VALUES_TEXT = "Edit configured values…"

# Tooltip/status hint shown when the session has a single configuration — the
# actionable "what to do instead", pointing at the (Phase 4c) manager.
SINGLE_CONFIGURATION_HINT = (
    "Configuring a parameter needs more than one configuration — this session has one. "
    "Add configurations with the configuration manager (arriving in the next sub-phase), "
    "or open a study file that defines several."
)


def unconfigure_text(first_name: str) -> str:
    """The un-configure label, naming the configuration whose value is kept (D-6)."""
    return f"Un-configure (keep {first_name}'s value)…"


def add_configuration_actions(menu: QMenu, scope: ConfigurationScope, dotpath: str) -> None:
    """Append the configure / edit-values / un-configure actions for *dotpath* to *menu*.

    A shared parameter gets the configure action; a configured one gets the table
    editor and the un-configure action. Triggering routes through *scope*, so the
    caller needs no ``ConfigurationSet`` of its own.
    """
    menu.addSeparator()
    if scope.is_configured(dotpath):
        edit_action = QAction(EDIT_VALUES_TEXT, menu)
        edit_action.setToolTip(scope.summary(dotpath))
        edit_action.triggered.connect(lambda: scope.request_edit_values(dotpath))
        menu.addAction(edit_action)

        unconfigure_action = QAction(unconfigure_text(scope.first_name()), menu)
        unconfigure_action.triggered.connect(lambda: scope.request_unconfigure(dotpath))
        menu.addAction(unconfigure_action)
        return

    configure_action = QAction(CONFIGURE_TEXT, menu)
    if not scope.is_multi():
        configure_action.setToolTip(SINGLE_CONFIGURATION_HINT)
        configure_action.setStatusTip(SINGLE_CONFIGURATION_HINT)
    configure_action.triggered.connect(lambda: scope.request_configure(dotpath))
    menu.addAction(configure_action)


__all__ = [
    "CONFIGURE_TEXT",
    "EDIT_VALUES_TEXT",
    "SINGLE_CONFIGURATION_HINT",
    "add_configuration_actions",
    "unconfigure_text",
]
