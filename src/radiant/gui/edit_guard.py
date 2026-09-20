"""Differential clone-validate guard shared by every GUI commit path (CU-372).

One computation, one module (Rule 19): given the live :class:`Sensor` and one
candidate change — a value for a dot-path, or the withdrawal of one — decide whether
the change is **accepted**, **rejected** with an actionable error, or hit a genuine
bug. The Parameters dock's in-place delegate, the Parameter Editor dialog, and the
dock's *Reset to Default* all decide here, so the three paths reject identically by
construction (audit F-02: the dialog had the differential guard, the delegate did not,
and on a blank configuration every in-place edit was rejected while the dialog accepted
the same value).

The **differential** rule, in one sentence: only a failure *this change introduces* is
a rejection. Concretely, the change is applied to a throwaway clone and the clone is
resolved (the API's own resolve does the validating — no reimplemented physics):

* the clone resolves → accepted (after the target-spec seam below);
* the clone fails but the live sensor **resolves** → the change caused it → rejected;
* the clone fails and the live sensor **also fails** → compare the two failures:

  - the clone's failure is a :class:`~radiant.core.parameters.RequiredParameterError`
    → the configuration is incomplete with or without this change; accepted (the
    from-scratch contract of 2026-07-17 — Evaluate's advisory reports what is still
    missing). Because the resolver validates every explicit input (type, bounds, enum)
    and every consistency group *before* it reports a missing required parameter
    (CU-373 F-13 ordering), a value that is wrong on its own terms can never hide
    behind incompleteness: it fails as a bounds / enum / over-constrained error first;
  - the two failures are the **identical** error (same type, same text) → it pre-exists
    without this change; accepted, and Evaluate keeps reporting it;
  - anything else → this change turned one failure into a different one (audit F-06:
    a disagreeing third member of the ``fnumber`` group typed on an incomplete
    configuration turns "required parameter unset" into "over-constrained") → rejected
    with the clone's error, at the door, on the row being edited.

An accepted value is additionally screened by two resolve-time seams, both
differential: the target-spec seam
(:func:`~radiant.gui.target_spec_guard.introduced_target_spec_conflict`, CU-244)
and the one-door-per-geometry-family seam
(:func:`~radiant.gui.geometry_mode_guard.introduced_geometry_mode_conflict`,
CU-377 — a second viewing/solar/kinematics/LOS-rate door entered outside the
family's mode selector is refused at the door).

**Mode switches (CU-377 F-05).** A geometry family's selector choice is planned
by :mod:`~radiant.gui.mode_switch` (withdraw the other doors, seed the chosen
one) and validated/applied here (:func:`validate_mode_switch` /
:func:`apply_mode_switch`) under the same differential rule.

Qt-free by design so the rule is unit-tested without a widget. Every call is one
public ``radiant.api`` call (R-API); the live sensor is never mutated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from radiant.core.exceptions import RadiantError
from radiant.core.parameters import RequiredParameterError
from radiant.gui.architecture_switch import SWITCH_DOTPATHS, apply_companion_resets
from radiant.gui.geometry_mode_guard import introduced_geometry_mode_conflict
from radiant.gui.target_spec_guard import introduced_target_spec_conflict

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor
    from radiant.gui.mode_switch import ModeSwitchPlan

__all__ = [
    "EditVerdict",
    "apply_edit",
    "apply_mode_switch",
    "apply_takeover",
    "validate_edit",
    "validate_mode_switch",
    "validate_reset",
    "validate_takeover",
]


@dataclass(frozen=True, slots=True)
class EditVerdict:
    """The outcome of validating one candidate change on a throwaway clone.

    Exactly one of three states: accepted (``rejection`` and ``unexpected`` both
    ``None``), rejected (``rejection`` carries the actionable
    :class:`~radiant.core.exceptions.RadiantError`), or a genuine bug (``unexpected``
    carries the non-RADIANT exception — surfaced, never swallowed, Rules 15/17).
    ``canonical`` is the resolved canonical value when the clone resolved, and
    ``None`` when the change was accepted by the differential rule on a configuration
    that cannot resolve yet (there is then no resolved value to preview).
    """

    canonical: Any | None
    rejection: RadiantError | None
    unexpected: BaseException | None

    @property
    def accepted(self) -> bool:
        """True when the change may be applied to the live sensor."""
        return self.rejection is None and self.unexpected is None


def validate_edit(live: Sensor, dotpath: str, value: Any, unit: str | None) -> EditVerdict:
    """Validate ``set(dotpath, value, unit=unit)`` against *live* on a clone.

    The clone carries the one ``set`` (with *unit*, so the Rule-2 conversion happens
    exactly once, inside the API) and a full resolve; the verdict follows the
    differential rule in the module docstring.
    """
    trial = live.clone()
    try:
        if unit is not None:
            trial.set(dotpath, value, unit=unit)
        else:
            trial.set(dotpath, value)
        canonical = trial.get(dotpath)
    except RadiantError as exc:
        return EditVerdict(None, _introduced_failure(live, exc), None)
    except Exception as exc:  # genuine bug, not a rejected input — never swallow
        return EditVerdict(None, None, exc)
    conflict = _introduced_seam_conflict(live, trial)
    if conflict is not None:
        return EditVerdict(None, conflict, None)
    return EditVerdict(canonical, None, None)


def validate_reset(live: Sensor, dotpath: str) -> EditVerdict:
    """Validate ``reset(dotpath)`` — withdrawing the explicit input — on a clone.

    The withdrawal is applied to a throwaway clone and the clone resolved; the same
    differential rule decides. A reset that leaves a resolvable configuration
    unresolvable (audit F-03: resetting ``optics.f_number`` when the focal length is
    derived from it) is therefore *refused* — the live sensor is untouched and the
    caller renders the resolver's own actionable error — while a reset on a
    configuration that could not resolve anyway is accepted, since withdrawing a
    value cannot make an incomplete configuration less complete in a way Evaluate
    would not report.
    """
    trial = live.clone()
    try:
        trial.reset(dotpath)
        trial.resolve()
    except RadiantError as exc:
        return EditVerdict(None, _introduced_failure(live, exc), None)
    except Exception as exc:  # genuine bug — never swallow
        return EditVerdict(None, None, exc)
    try:
        canonical = trial.get(dotpath)
    except KeyError:
        # A required-unless parameter superseded by its alternative resolves to no
        # value after the reset — a legal, visible unset state (Rule 17).
        canonical = None
    return EditVerdict(canonical, None, None)


def validate_takeover(
    live: Sensor, dotpath: str, value: Any, unit: str | None, release: str
) -> EditVerdict:
    """Validate "set *dotpath* and let *release* derive instead" on a clone (F-04).

    A derived consistency-group member is a consequence of its explicit siblings;
    typing into it means choosing it as the input, which needs one sibling to be
    released (its explicit input withdrawn so the group derives it). Both steps are
    applied to a throwaway clone — reset *release*, then set *dotpath* — and the
    same differential rule decides. Released and set as one logical action, so the
    group never passes through an under- or over-specified state on the live sensor.
    """
    trial = live.clone()
    try:
        trial.reset(release)
        if unit is not None:
            trial.set(dotpath, value, unit=unit)
        else:
            trial.set(dotpath, value)
        canonical = trial.get(dotpath)
    except RadiantError as exc:
        return EditVerdict(None, _introduced_failure(live, exc), None)
    except Exception as exc:  # genuine bug — never swallow
        return EditVerdict(None, None, exc)
    conflict = _introduced_seam_conflict(live, trial)
    if conflict is not None:
        return EditVerdict(None, conflict, None)
    return EditVerdict(canonical, None, None)


def apply_takeover(live: Sensor, dotpath: str, value: Any, unit: str | None, release: str) -> None:
    """Apply an **accepted** take-over to *live*: reset *release*, then set *dotpath*."""
    live.reset(release)
    if unit is not None:
        live.set(dotpath, value, unit=unit)
    else:
        live.set(dotpath, value)


def apply_edit(live: Sensor, dotpath: str, value: Any, unit: str | None) -> tuple[str, ...]:
    """Apply an **accepted** edit to *live*: one ``set``, plus its companion resets.

    The single mandated API call on the live sensor (§4.1), with ``unit=`` only
    when a display-unit override is active. A readout architecture or counting-mode
    switch (Gap 117) clears the explicit inputs the new selection rejects as part of
    the same logical action, whichever path committed it; the cleared dot-paths are
    returned so the caller can name them.
    """
    if unit is not None:
        live.set(dotpath, value, unit=unit)
    else:
        live.set(dotpath, value)
    if dotpath in SWITCH_DOTPATHS:
        return apply_companion_resets(live, dotpath, value)
    return ()


def validate_mode_switch(live: Sensor, plan: ModeSwitchPlan) -> EditVerdict:
    """Validate a geometry mode switch — withdrawals then seeds — on a clone (F-05).

    Seeds are canonical-unit values (:meth:`Sensor.geometry_door_values`), so they
    are set with ``unit=`` the schema's canonical unit and the API converts once
    (Rule 2). The differential rule decides as for any edit; a switch on a
    configuration that cannot resolve yet is accepted (withdrawing and seeding
    cannot make it less complete in a way Evaluate would not report).
    """
    trial = live.clone()
    try:
        _apply_plan(trial, plan)
        trial.resolve()
    except RadiantError as exc:
        return EditVerdict(None, _introduced_failure(live, exc), None)
    except Exception as exc:  # genuine bug — never swallow
        return EditVerdict(None, None, exc)
    conflict = _introduced_seam_conflict(live, trial)
    if conflict is not None:
        return EditVerdict(None, conflict, None)
    return EditVerdict(None, None, None)


def apply_mode_switch(live: Sensor, plan: ModeSwitchPlan) -> None:
    """Apply an **accepted** mode switch to *live* in the validated order."""
    _apply_plan(live, plan)


def _apply_plan(sensor: Sensor, plan: ModeSwitchPlan) -> None:
    for name in plan.withdraw:
        sensor.reset(name)
    for name, value in plan.seeds:
        canonical_unit = sensor.parameter_def(name).canonical_unit
        if canonical_unit and not isinstance(value, bool):
            sensor.set(name, value, unit=canonical_unit)
        else:
            sensor.set(name, value)


def _introduced_seam_conflict(live: Sensor, trial: Sensor) -> RadiantError | None:
    """The first resolve-time seam conflict *trial* introduces over *live*, if any."""
    conflict = introduced_target_spec_conflict(live, trial)
    if conflict is not None:
        return conflict
    return introduced_geometry_mode_conflict(live, trial)


def _introduced_failure(live: Sensor, trial_error: RadiantError) -> RadiantError | None:
    """The clone's failure if this change introduced it, else ``None`` (pre-existing)."""
    baseline = live.clone()
    try:
        baseline.resolve()
    except RadiantError as pre_existing:
        if isinstance(trial_error, RequiredParameterError):
            # Incomplete with or without this change: the change is not at fault.
            return None
        if type(pre_existing) is type(trial_error) and str(pre_existing) == str(trial_error):
            # The identical failure exists without this change (deliberate
            # differential acceptance, not a swallowed failure — Evaluate reports it).
            return None
        return trial_error
    return trial_error
