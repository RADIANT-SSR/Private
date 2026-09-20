"""Differential one-door-per-family guard for the GUI edit discipline (CU-377).

One computation, one module (Rule 19), the twin of
:mod:`radiant.gui.target_spec_guard`: given the live :class:`Sensor` and a trial
clone carrying one candidate edit, decide whether that edit *introduces* a
second explicit door in a geometry family (``Sensor.validate_geometry_modes``,
the resolve-time seam over the ADR-0006 manifest — a pure provenance read).

Only a conflict **this edit introduces** is a rejection. A configuration that
already carries the identical conflict (a loaded file with an agreeing pair,
which Evaluate tolerates under ADR-0006 rule 2) is not this edit's fault, and
editing anything else on it stays possible; the family's mode selector is the
way out. Shared by every commit path through :mod:`radiant.gui.edit_guard`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

__all__ = ["introduced_geometry_mode_conflict"]


def introduced_geometry_mode_conflict(live: Sensor, trial: Sensor) -> RadiantError | None:
    """Return the door conflict *trial* introduces over *live*, else ``None``.

    Both sensors are only read (the seam never resolves or mutates), so no
    clone is taken here.
    """
    try:
        trial.validate_geometry_modes()
    except RadiantError as exc:
        try:
            live.validate_geometry_modes()
        except RadiantError as pre_existing:
            if str(pre_existing) == str(exc):
                # The identical conflict exists without this edit — deliberate
                # differential acceptance; Evaluate (or the selector) resolves it.
                return None
            return exc
        return exc
    return None
