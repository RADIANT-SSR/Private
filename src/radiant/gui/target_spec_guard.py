"""Differential target-spec conflict guard for the GUI edit discipline (CU-244).

One computation, one module (Rule 19): given the live :class:`Sensor` and a
trial clone carrying one candidate edit, decide whether that edit *introduces*
a target-spec over-specification (``Sensor.validate_target_spec``, the
resolve-time seam over the source inferrer's mutual-exclusivity guards).

The differential comparison mirrors the editor's existing philosophy for
pre-existing config incompleteness: only a conflict **this edit introduces**
is a rejection. If the live sensor already carries the *identical* conflict
(same what/why/action), the edit is not at fault — Evaluate remains the
surface that reports the pre-existing problem. A conflict that is present on
the trial but different from the live one (e.g. the live config pairs ρ with
(ε, T) and the edit adds a second ρ surface) is still this edit's doing and is
rejected.

Shared by :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`
(``_try_resolve``) and :class:`~radiant.gui.widgets.parameter_panel.ParameterPanel`
(``_commit_edit``) so the two clone-validate commit paths reject identically by
construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

__all__ = ["introduced_target_spec_conflict"]


def introduced_target_spec_conflict(live: Sensor, trial: Sensor) -> RadiantError | None:
    """Return the target-spec conflict *trial* introduces over *live*, else ``None``.

    Both sensors are only read (``validate_target_spec`` is a pure provenance
    check — no physics, no file I/O, no mutation), so no clone is taken here.
    """
    try:
        trial.validate_target_spec()
    except RadiantError as exc:
        try:
            live.validate_target_spec()
        except RadiantError as pre_existing:
            if str(pre_existing) == str(exc):
                # The identical conflict exists without this edit — not this
                # edit's fault; Evaluate reports it (deliberate differential
                # acceptance, not a swallowed failure).
                return None
            return exc
        return exc
    return None
