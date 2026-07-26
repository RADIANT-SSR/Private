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

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

from radiant.gui.param_format import format_value

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet

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
        The user asked to open the per-parameter all-configurations table editor.
    """

    changed = Signal()
    configureRequested = Signal(str)
    unconfigureRequested = Signal(str)
    editValuesRequested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config_set: ConfigurationSet | None = None

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
        """Ask the host to open *dotpath*'s all-configurations table editor."""
        self.editValuesRequested.emit(dotpath)


__all__ = ["ConfigurationScope"]
