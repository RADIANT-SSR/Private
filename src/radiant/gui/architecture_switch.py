"""Companion resets for a readout-architecture switch (Gap 117, plan Phase 3).

The readout stage rejects mixed architecture specifications (Rule 16): the
counting-only parameters under ``analog_well``, and an explicit
``full_well_capacity_e`` under ``digital_counting``. A loaded analog config
almost always pins the full well explicitly, so a bare architecture switch
would commit cleanly (the check runs at evaluate time) and then fail the very
next evaluation — the operator saw it as *Cannot set "evaluate"* on the live
review of 2026-09-06. The switch is therefore committed as one logical action:
set the architecture, then clear the explicit inputs the new architecture
rejects. Cleared parameters revert to their schema defaults (visible again on
switch-back); the values are not silently reinterpreted, they are removed —
mirroring, not bypassing, the stage's validation posture.

The dot-path lists mirror ``radiant.readout.stage`` (``_COUNTING_ONLY_PARAMS``
and the FWC rule). They are literals here because ``radiant.gui`` may import
only ``radiant.api`` + ``radiant.core`` (import rules) — same manifest
convention as the stage input forms (CU-120).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

ARCHITECTURE_DOTPATH: Final[str] = "readout.architecture"

#: Rejected as over-specification when explicitly set under analog_well.
_COUNTING_ONLY: Final[tuple[str, ...]] = (
    "readout.counter_bits",
    "readout.count_packet_e",
    "readout.residue_readout",
    "readout.max_count_rate_hz",
    "readout.counting_mode",
    "readout.reference_source",
    "readout.reference_rate_e_per_s",
    "readout.reference_integration_s",
)

#: Rejected when explicitly set under digital_counting (the effective well is
#: 2^counter_bits × count_packet_e; the schema default passes silently).
_ANALOG_ONLY: Final[tuple[str, ...]] = ("readout.full_well_capacity_e",)

#: The counting-mode selector (plan Phase 4) — switching back to plain "up"
#: rejects the explicit reference parameters, the same trap one level down.
MODE_DOTPATH: Final[str] = "readout.counting_mode"

_UPDOWN_ONLY: Final[tuple[str, ...]] = (
    "readout.reference_source",
    "readout.reference_rate_e_per_s",
    "readout.reference_integration_s",
)

#: The dot-paths whose editor commits carry companion resets.
SWITCH_DOTPATHS: Final[frozenset[str]] = frozenset({ARCHITECTURE_DOTPATH, MODE_DOTPATH})


def companion_resets_for(dotpath: str, new_value: object) -> tuple[str, ...]:
    """The dot-paths a switch of *dotpath* to *new_value* must clear."""
    if dotpath == ARCHITECTURE_DOTPATH:
        if new_value == "digital_counting":
            return _ANALOG_ONLY
        if new_value == "analog_well":
            return _COUNTING_ONLY
    elif dotpath == MODE_DOTPATH and new_value == "up":
        return _UPDOWN_ONLY
    return ()


def apply_companion_resets(sensor: Sensor, dotpath: str, new_value: object) -> tuple[str, ...]:
    """Clear the explicit inputs the new selection rejects; return those cleared.

    ``Sensor.reset`` on a parameter with no explicit input is a no-op, so this
    is safe to call unconditionally after every switch commit. The returned
    tuple (possibly empty) names the parameters actually cleared, for the
    caller's messaging surface.
    """
    explicit = set(sensor.inputs())
    cleared: list[str] = []
    for name in companion_resets_for(dotpath, new_value):
        if name in explicit:
            sensor.reset(name)
            cleared.append(name)
    return tuple(cleared)


__all__ = [
    "ARCHITECTURE_DOTPATH",
    "MODE_DOTPATH",
    "SWITCH_DOTPATHS",
    "apply_companion_resets",
    "companion_resets_for",
]
