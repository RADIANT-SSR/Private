"""Planning a geometry mode switch — withdraw the other doors, seed the new one (CU-377).

One computation, one module (Rule 19), Qt-free. Under the owner ruling of
2026-09-20 a family's mode selector **is** the switch: choosing a mode
withdraws the other doors' explicit inputs and seeds the chosen door from the
value it would carry under the current scene
(:meth:`~radiant.api.sensor.Sensor.geometry_door_values`), so the switch
re-expresses the geometry rather than changing it — the operator then edits
the number they wanted to enter. Doors with no inverse (the S3 site-and-time
inputs, the K2 target-velocity triple) are left unset and become editable; a
door already holding an explicit input is never re-seeded.

This module only *plans*; :mod:`radiant.gui.edit_guard` validates the plan on
a throwaway clone (the same differential rule as every edit) and applies it
to the live sensor as one logical action, which the window records as one
undo step (its input-snapshot diff, CU-372 F-20).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from radiant.gui.geometry_modes import (
    MODE_SEEDS,
    SUBDOORS,
    GeometryModeFamily,
    family_title,
    mode_label,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

__all__ = ["ModeSwitchPlan", "plan_mode_switch", "plan_subdoor_switch"]


@dataclass(frozen=True, slots=True)
class ModeSwitchPlan:
    """What one selector choice does to the explicit inputs.

    Attributes
    ----------
    label:
        Human wording for the action (undo text, error headers).
    withdraw:
        Explicit inputs to reset — the other doors' values.
    seeds:
        ``(dot-path, canonical value)`` pairs to set on the chosen door.
    """

    label: str
    withdraw: tuple[str, ...]
    seeds: tuple[tuple[str, Any], ...]

    @property
    def is_empty(self) -> bool:
        """True when the choice moves no input (nothing to validate or undo)."""
        return not self.withdraw and not self.seeds

    @property
    def headline(self) -> str:
        """The dot-path the window names for the edit (first seed, else first withdrawal)."""
        if self.seeds:
            return str(self.seeds[0][0])
        return self.withdraw[0] if self.withdraw else ""


def plan_mode_switch(sensor: Sensor, family: GeometryModeFamily, mode_key: str) -> ModeSwitchPlan:
    """The plan for selecting *mode_key* in *family* on the live *sensor*."""
    explicit = set(sensor.inputs())
    target = next(mode for mode in family.modes if mode.key == mode_key)
    withdraw = tuple(
        dotpath
        for mode in family.modes
        if mode.key != mode_key
        for dotpath in mode.params
        if dotpath in explicit
    )
    seeds: list[tuple[str, Any]] = []
    if not any(dotpath in explicit for dotpath in target.params):
        overrides = MODE_SEEDS.get(mode_key, {})
        doors = sensor.geometry_door_values()
        for dotpath in target.params:
            if dotpath in overrides:
                seeds.append((dotpath, overrides[dotpath]))
            elif doors.get(dotpath) is not None:
                seeds.append((dotpath, doors[dotpath]))
    label = f"Switch {family_title(family.key)} to {mode_label(mode_key)}"
    return ModeSwitchPlan(label, withdraw, tuple(seeds))


def plan_subdoor_switch(sensor: Sensor, mode_key: str, index: int) -> ModeSwitchPlan:
    """The plan for choosing sub-door *index* of *mode_key* (e.g. LTAN vs local solar time)."""
    explicit = set(sensor.inputs())
    subdoors = SUBDOORS[mode_key]
    chosen_label, _chosen = subdoors[index]
    withdraw = tuple(
        dotpath
        for i, (_label, dotpaths) in enumerate(subdoors)
        if i != index
        for dotpath in dotpaths
        if dotpath in explicit
    )
    return ModeSwitchPlan(f"Use {chosen_label} ({mode_label(mode_key)})", withdraw, ())
