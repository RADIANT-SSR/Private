"""A single reversible parameter edit for the Edit → Undo/Redo stack (Phase 9).

:class:`SetParameterCommand` wraps one ``sensor.set(dotpath, value)`` as a named
:class:`~PySide6.QtGui.QUndoCommand` so the window's :class:`~PySide6.QtGui.QUndoStack`
(Edit → Undo / Redo, arch doc §10) can reverse and replay parameter edits. One GUI action
still maps to exactly one API call (GUI plan §4.1) — undo/redo simply issue that same
``sensor.set`` with the before/after value.

Values are carried in the parameter's **input unit** (the unit :meth:`Sensor.get_input`
returns and :meth:`Sensor.set` accepts via ``unit=``), so undo/redo round-trip through the
public unit seam with no ad-hoc conversion (Rule 2). The command captures the live sensor at
construction; the window clears the whole stack whenever the sensor is swapped (Open / New /
YAML-apply / console refresh), so a command never references a stale sensor.

No colour/font/size literal lives here (GUI plan §4.9); this is pure command logic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class SetParameterCommand(QUndoCommand):
    """Reverse/replay one ``sensor.set`` of *dotpath* between *old_value* and *new_value*.

    Parameters
    ----------
    sensor:
        The live :class:`~radiant.api.sensor.Sensor` the edit applies to.
    dotpath:
        The parameter dot-path (e.g. ``"optics.aperture_diameter_m"``).
    old_value, new_value:
        The parameter's value **in its input unit**, before and after the edit.
    unit:
        The input unit to pass to :meth:`Sensor.set` (``None`` for a dimensionless /
        enum parameter, whose value carries no unit).
    on_applied:
        Called with *dotpath* after an undo or redo mutates the sensor, so the window
        re-reads the panels and re-evaluates.
    text:
        The human-readable command label shown in the Edit menu (e.g.
        ``"Set optics.aperture_diameter_m = 0.5 m"``).
    """

    def __init__(
        self,
        sensor: Sensor,
        dotpath: str,
        old_value: Any,
        new_value: Any,
        unit: str | None,
        on_applied: Callable[[str], None],
        text: str,
    ) -> None:
        super().__init__(text)
        self._sensor = sensor
        self._dotpath = dotpath
        self._old = old_value
        self._new = new_value
        self._unit = unit
        self._on_applied = on_applied
        # QUndoStack.push() calls redo() immediately, but the edit that created this
        # command has *already* applied new_value to the live sensor. Skip that first
        # redo so we neither re-set the value nor fire a redundant re-evaluate; every
        # later redo (after an undo) does apply.
        self._skip_first_redo = True

    # -- QUndoCommand overrides ---------------------------------------------

    def redo(self) -> None:  # noqa: D401 - Qt override
        """Re-apply *new_value* (a no-op on the first, edit-triggered push)."""
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self._apply(self._new)

    def undo(self) -> None:  # noqa: D401 - Qt override
        """Restore *old_value*."""
        self._apply(self._old)

    # -- helpers ------------------------------------------------------------

    def _apply(self, value: Any) -> None:
        """Set *value* on the live sensor (in the input unit) and notify the window."""
        if self._unit:
            self._sensor.set(self._dotpath, value, unit=self._unit)
        else:
            self._sensor.set(self._dotpath, value)
        self._on_applied(self._dotpath)


__all__ = ["SetParameterCommand"]
