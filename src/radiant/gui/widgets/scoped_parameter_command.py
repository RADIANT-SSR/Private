"""One reversible **scope-and-value** change of a parameter (multi-configuration Phase 4b).

Phase 4a's :class:`~radiant.gui.widgets.set_parameter_command.SetParameterCommand`
reverses one ``sensor.set`` on the shared base. A study needs more: an edit can move
a parameter *between stores* (shared base ⇄ configured table), and the plan's
acceptance criterion is that "undo/redo of a scoped edit restores both value **and**
scope" (plan §6, 4b).

:class:`ScopedParameterCommand` is that one command. Rather than three sibling
commands (configure / unconfigure / per-configuration edit) it records the
parameter's **whole scope state** before and after the user's action, and applying a
state is the same operation in every direction:

* :class:`ScopeState` ``configured`` → ``ConfigurationSet.configure`` (when the
  parameter is currently shared) or ``set_values`` (when it already has a column) —
  one API call, the dense full column, never a partial write;
* :class:`ScopeState` ``shared`` → ``unconfigure`` (dropping the column) followed by
  restoring the base's *recorded* explicit input — or ``Sensor.reset`` when the base
  never had one, so undoing a configure of a defaulted parameter leaves it defaulted
  rather than freezing today's default as an explicit input.

That covers every Phase 4b action with one class:

===========================  ==========================  ==========================
Action                       before                      after
===========================  ==========================  ==========================
Configure across configs     shared(v or unset)          configured(v, v, …)
Un-configure (keep #1)       configured(v1, v2, …)       shared(v1)
Table-editor edit            configured(old column)      configured(new column)
Inline edit while X shown    configured(old column)      configured(column with X)
===========================  ==========================  ==========================

Values are carried in the parameter's **input unit** — the unit the configured table
stores and ``Sensor.set`` assumes without an explicit ``unit=`` (Rule 2: the single
conversion already happened at the editing boundary).

The command holds the live :class:`~radiant.api.config_set.ConfigurationSet`; the
window clears the whole undo stack whenever the document is swapped, so a command
never references a stale set. No colour/font/size literal lives here (GUI plan §4.9).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet


@dataclass(frozen=True)
class ScopeState:
    """A parameter's store + value(s) at one instant — the unit of undo in a study.

    Attributes
    ----------
    configured:
        ``True`` when the parameter lives in the configured table (one value per
        configuration), ``False`` when it is a shared base input.
    values:
        The full configured column, in set order, when ``configured``.
    shared_value:
        The base's explicit input when not ``configured``. ``None`` means the base
        held **no** explicit input (the parameter resolved from its default or from
        a consistency group), and restoring the state resets it rather than pinning
        a value the user never typed.
    """

    configured: bool
    values: tuple[Any, ...] = ()
    shared_value: Any = None

    @classmethod
    def shared(cls, value: Any) -> ScopeState:
        """A shared parameter holding *value* (``None`` = no explicit base input)."""
        return cls(configured=False, shared_value=value)

    @classmethod
    def configured_column(cls, values: Sequence[Any]) -> ScopeState:
        """A configured parameter holding *values*, one per configuration, in set order."""
        return cls(configured=True, values=tuple(values))


class ScopedParameterCommand(QUndoCommand):
    """Reverse/replay one scope-and-value change of *dotpath* between two states.

    Parameters
    ----------
    config_set:
        The live session :class:`~radiant.api.config_set.ConfigurationSet`.
    dotpath:
        The parameter dot-path (e.g. ``"spectral_integration.filter_min_um"``).
    before, after:
        The parameter's :class:`ScopeState` before and after the user's action.
    on_applied:
        Called with *dotpath* after an undo or redo mutates the set, so the window
        re-materializes the displayed configuration, refreshes the badges, and
        re-evaluates.
    text:
        The command label shown in the Edit menu.
    """

    def __init__(
        self,
        config_set: ConfigurationSet,
        dotpath: str,
        before: ScopeState,
        after: ScopeState,
        on_applied: Callable[[str], None],
        text: str,
    ) -> None:
        super().__init__(text)
        self._config_set = config_set
        self._dotpath = dotpath
        self._before = before
        self._after = after
        self._on_applied = on_applied
        # QUndoStack.push() calls redo() immediately, but the action that created this
        # command has *already* applied the after-state. Skip that first redo so the
        # API is not called twice; every later redo (after an undo) does apply.
        self._skip_first_redo = True

    # -- QUndoCommand overrides ---------------------------------------------

    def redo(self) -> None:  # noqa: D401 - Qt override
        """Re-apply the after-state (a no-op on the first, action-triggered push)."""
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self._apply(self._after)

    def undo(self) -> None:  # noqa: D401 - Qt override
        """Restore the before-state — both the value(s) and the store they live in."""
        self._apply(self._before)

    # -- helpers ------------------------------------------------------------

    def _apply(self, state: ScopeState) -> None:
        """Put *dotpath* into *state* with the fewest possible API calls, then notify."""
        cs = self._config_set
        dotpath = self._dotpath
        if state.configured:
            if cs.is_configured(dotpath):
                cs.set_values(dotpath, state.values)
            else:
                cs.configure(dotpath, state.values)
        else:
            if cs.is_configured(dotpath):
                # unconfigure() itself writes configuration #1's value to the base
                # (ADR-0010 D-6); the recorded shared state then replaces it, which
                # is what makes "undo a configure" restore the *original* input.
                cs.unconfigure(dotpath)
            if state.shared_value is None:
                cs.base.reset(dotpath)
            else:
                cs.base.set(dotpath, state.shared_value)
        self._on_applied(dotpath)


__all__ = ["ScopeState", "ScopedParameterCommand"]
