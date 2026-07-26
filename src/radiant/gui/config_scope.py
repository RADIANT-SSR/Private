"""The GUI-side view of *which parameters are configured* (multi-configuration Phase 4b).

Phase 4a made the session a :class:`~radiant.api.config_set.ConfigurationSet`
(arch doc §4.2b). Phase 4b adds the surfaces that let an analyst mark a parameter
as **configured** (one value per configuration, ADR-0010 D-A/D-2), see that state
at a glance, and edit every configuration's value in one place.

:class:`ConfigurationScope` is the single object those surfaces share. It is a
*mediator*, not a model:

* **Read side** — the parameter tree (§4.3) and every :class:`FieldRow` in the
  per-stage forms (§4.4) ask it whether a dot-path is configured and, if so, for
  the badge tooltip listing **every** configuration's value with units (R-UNITS).
* **Request side** — those same surfaces emit *intent* (``Configure across
  configurations…`` / ``Edit configured values…`` / ``Un-configure…``) through it;
  the main window is the only listener and the only caller of the
  ``ConfigurationSet`` API, so one GUI action is still exactly one API call
  (R-API) and every scope change is one undoable command.

Nothing here mutates a ``ConfigurationSet``: the scope holds a reference and reads
it. That is what keeps the widgets free of API calls and the window free of widget
plumbing, and it is why a single ``changed`` signal is enough to keep every badge
in the window honest after a configure / unconfigure / value edit.

No colour, font, or size literal lives here (GUI plan §4.9) — this module is pure
state plumbing over the public :mod:`radiant.api` surface.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

from radiant.core.exceptions import RadiantError
from radiant.gui.param_format import format_value

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet

# The host's whole-column writer: ``(dotpath, values, unit, configure) -> rejection``.
# ``configure`` is True when the parameter is still shared and this write is the
# moment it becomes configured (one atomic ``configure(dotpath, values, unit=)``);
# False when it already has a column (``set_values``). Returning the API's
# ``RadiantError`` keeps the caller's dialog open with the rejection rendered;
# returning None means the write landed and is on the undo stack.
CommitValues = Callable[[str, Sequence[Any], str | None, bool], "RadiantError | None"]


class ConfigurationScopeError(RadiantError):
    """The scope was asked to do something its host never wired up.

    Raised only for a *wiring* fault — a surface offering a whole-column write
    before the window installed its committer. It is not a user input rejection
    (those are the API's own :class:`~radiant.api.config_set.ConfigSetError`,
    passed back to the caller untouched), but it must not be swallowed either:
    silently dropping the analyst's whole column is exactly the failure Rule 17
    forbids. Carries the Rule-15 what/why/action payload like every other
    RADIANT error, so a surface that does surface it renders it the usual way.
    """

    def __init__(self, what: str, why: str = "", action: str = "") -> None:
        self.what: str = what
        self.why: str = why
        self.action: str = action
        parts = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))

# Separator between per-configuration entries in a badge tooltip, e.g.
# "MWIR: 3.5 µm · LWIR: 8.0 µm" (the owner's Phase 4b spec, plan §4 item 3).
_TOOLTIP_SEPARATOR = " · "


class ConfigurationScope(QObject):
    """Read-only view of the session's configured parameters + edit-intent signals.

    Signals
    -------
    changed():
        Emitted whenever the configured table may have changed (a bind, a
        configure / unconfigure, or a value edit). Every badge-bearing surface
        re-reads itself from this one signal.
    configureRequested(str):
        The user asked to configure a dot-path across all configurations.
    unconfigureRequested(str):
        The user asked to collapse a configured dot-path back to a shared value.
    editValuesRequested(str):
        The user asked to open the parameter's per-configuration value editor.
    """

    changed = Signal()
    configureRequested = Signal(str)
    unconfigureRequested = Signal(str)
    editValuesRequested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config_set: ConfigurationSet | None = None
        self._committer: CommitValues | None = None

    # -- binding ------------------------------------------------------------

    def bind(self, config_set: ConfigurationSet | None) -> None:
        """Point the scope at *config_set* (the session document) and refresh readers."""
        self._config_set = config_set
        self.changed.emit()

    def notify_changed(self) -> None:
        """Announce that the configured table changed (badges re-read themselves)."""
        self.changed.emit()

    @property
    def configuration_set(self) -> ConfigurationSet | None:
        """The bound configuration set (``None`` before a document is open)."""
        return self._config_set

    # -- read side ----------------------------------------------------------

    def names(self) -> tuple[str, ...]:
        """The configuration names, in set order (empty when nothing is bound)."""
        return () if self._config_set is None else self._config_set.names()

    def is_multi(self) -> bool:
        """True when the session holds more than one configuration.

        The gate on configuring anything: a single-configuration session has no
        second column to hold a second value, so the action is refused with an
        actionable message rather than silently doing nothing (plan §4 item 3).
        """
        return len(self.names()) > 1

    def is_configured(self, dotpath: str) -> bool:
        """True when *dotpath* carries one value per configuration."""
        if self._config_set is None:
            return False
        return self._config_set.is_configured(dotpath)

    def values_for(self, dotpath: str) -> tuple[Any, ...]:
        """*dotpath*'s per-configuration values in set order (empty when not configured)."""
        if self._config_set is None or not self._config_set.is_configured(dotpath):
            return ()
        return tuple(self._config_set.configured()[dotpath])

    def unit_for(self, dotpath: str) -> str:
        """The parameter's schema input unit — the unit configured values are stored in."""
        if self._config_set is None:
            return ""
        return self._config_set.base.parameter_def(dotpath).input_unit or ""

    def value_text(self, dotpath: str, index: int) -> str:
        """Configuration *index*'s value of *dotpath*, rendered **with its unit** (R-UNITS)."""
        values = self.values_for(dotpath)
        if not (0 <= index < len(values)):
            return format_value(None, "")
        return format_value(values[index], self.unit_for(dotpath))

    def summary(self, dotpath: str) -> str:
        """Every configuration's value with units, in set order — the badge tooltip.

        E.g. ``"MWIR: 3.5 µm · LWIR: 8.0 µm"``. Empty for a parameter that is not
        configured (its row carries no badge, so there is nothing to describe).
        """
        values = self.values_for(dotpath)
        if not values:
            return ""
        unit = self.unit_for(dotpath)
        return _TOOLTIP_SEPARATOR.join(
            f"{name}: {format_value(value, unit)}"
            for name, value in zip(self.names(), values, strict=False)
        )

    def first_name(self) -> str:
        """The first configuration's name — the value un-configuring keeps (ADR-0010 D-6)."""
        names = self.names()
        return names[0] if names else ""

    # -- request side -------------------------------------------------------

    def request_configure(self, dotpath: str) -> None:
        """Ask the host to configure *dotpath* across every configuration."""
        self.configureRequested.emit(dotpath)

    def request_unconfigure(self, dotpath: str) -> None:
        """Ask the host to collapse *dotpath* back to a shared value."""
        self.unconfigureRequested.emit(dotpath)

    def request_edit_values(self, dotpath: str) -> None:
        """Ask the host to open *dotpath*'s per-configuration editor."""
        self.editValuesRequested.emit(dotpath)

    # -- whole-column writes (the one synchronous request) ------------------

    def set_committer(self, committer: CommitValues | None) -> None:
        """Install the host's whole-column writer (the window installs it once).

        The three actions above are *asynchronous* intent: the window acts and the
        surfaces re-read themselves from ``changed``. Writing a whole column from a
        dialog is different — the dialog must know, **synchronously**, whether the API
        accepted it, because a rejection has to render inline and keep the dialog open
        (Rules 15/17). A Qt signal cannot answer, so the write is a callback. It still
        keeps R-API intact: the callback is the *window's* method, so the single
        ``ConfigurationSet`` call and the one undo command stay where they belong.
        """
        self._committer = committer

    @property
    def can_commit(self) -> bool:
        """True when a bound set **and** a host writer make a column write possible."""
        return self._config_set is not None and self._committer is not None

    def commit_values(
        self,
        dotpath: str,
        values: Sequence[Any],
        unit: str | None,
        *,
        configure: bool,
    ) -> RadiantError | None:
        """Write *dotpath*'s whole column through the host; return any rejection.

        *unit* is the unit **every** value is expressed in (``None`` = the schema input
        unit); the API converts once at its own boundary (Rule 2). *configure* marks the
        write that also promotes a still-shared parameter, which the host performs as
        the single atomic ``configure(dotpath, values, unit=)`` call — so a staged
        configure and its values land, and undo, as one step.

        Raises :class:`ConfigurationScopeError` when no committer is installed: that is
        a wiring bug, never a user input, and silently dropping the analyst's whole
        column would be exactly the swallowed failure Rule 17 forbids. Surfaces guard
        on :attr:`can_commit` before offering a column edit, so it is unreachable in a
        correctly wired window.
        """
        if self._committer is None:
            raise ConfigurationScopeError(
                what=f"no committer is installed, so {dotpath}'s values cannot be written",
                why="ConfigurationScope routes whole-column writes to the host window, "
                "which must install that writer before any surface offers the edit",
                action="Call ConfigurationScope.set_committer(...) when the window is "
                "constructed, and gate column-editing surfaces on scope.can_commit.",
            )
        return self._committer(dotpath, values, unit, configure)


def scope_of(node: QObject | None) -> ConfigurationScope | None:
    """The session :class:`ConfigurationScope` owning *node*, by ancestor walk.

    Every configured-parameter surface is a descendant of the one window that owns the
    scope, and the window exposes it as ``configuration_scope``. Walking up from a
    widget therefore finds the session's scope without threading it through the ten
    places that open the Parameter Editor — and, unlike a module-level singleton, it
    stays per-window, so two windows in one process (the test suite's normal state)
    never share a scope. A widget with no such ancestor — a dialog built parentless in
    a unit test — gets ``None`` and the single-value behaviour.
    """
    while node is not None:
        candidate = getattr(node, "configuration_scope", None)
        if isinstance(candidate, ConfigurationScope):
            return candidate
        node = node.parent()
    return None


__all__ = ["CommitValues", "ConfigurationScope", "ConfigurationScopeError", "scope_of"]
