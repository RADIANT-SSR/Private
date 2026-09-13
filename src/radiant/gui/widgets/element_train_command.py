"""The undo command for element-train commits (CU-357).

One :class:`ElementTrainCommand` reverses or replays one committed change of the
element document — a cell edit, a structure change (add / remove / reorder), a
configure-across, an un-configure, or a mode detach — between two
:class:`~radiant.api.config_set.ElementTrainState` snapshots. The snapshot is the
**whole train** (shared rows plus the configured-row table with positions), the
same before/after pattern
:class:`~radiant.gui.widgets.scoped_parameter_command.ScopedParameterCommand` uses
for a configured column: restoring the pair of stores together is what makes
"undo a configure-across" put the row back where it was, entries and all.

The command holds no API object: the window's apply callback owns the write
(``ConfigurationSet.restore_element_state`` in a study,
``Sensor.set_optical_elements`` in a plain session), so one command class serves
both session shapes and never outlives the document it targets.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from collections.abc import Callable

    from radiant.api.config_set import ElementTrainState


class ElementTrainCommand(QUndoCommand):
    """Reverse/replay one element-train commit between two whole-train states.

    Parameters
    ----------
    before, after:
        The train's :class:`ElementTrainState` before and after the committed
        edit (deep snapshots — later edits never reach them).
    on_applied:
        Called with the state to restore after an undo or redo, so the window
        writes it to the session document, re-renders the table, and schedules
        the debounced re-evaluation.
    text:
        The command label shown in the Edit menu.
    """

    def __init__(
        self,
        before: ElementTrainState,
        after: ElementTrainState,
        on_applied: Callable[[ElementTrainState], None],
        text: str,
    ) -> None:
        super().__init__(text)
        self._before = copy.deepcopy(before)
        self._after = copy.deepcopy(after)
        self._on_applied = on_applied
        # QUndoStack.push() calls redo() immediately, but the commit that created
        # this command has *already* applied the after-state. Skip that first redo
        # so the document is not written twice; every later redo (after an undo)
        # does apply.
        self._skip_first_redo = True

    # -- QUndoCommand overrides ---------------------------------------------

    def redo(self) -> None:  # noqa: D401 - Qt override
        """Re-apply the after-state (a no-op on the first, commit-triggered push)."""
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self._on_applied(copy.deepcopy(self._after))

    def undo(self) -> None:  # noqa: D401 - Qt override
        """Restore the before-state — shared rows, configured rows, and positions."""
        self._on_applied(copy.deepcopy(self._before))


__all__ = ["ElementTrainCommand"]
