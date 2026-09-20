"""Companion withdrawals for a source target-door entry (CU-377 F-07).

The ``source.target.*`` spec surfaces are mutually exclusive **doors** onto
one target description (Target Definition Matrix §1): the thermal surface
(ε, T), the reflective surface ρ, and the two point-intensity forms. The
resolve-time seam (``Sensor.validate_target_spec``, CU-244) refuses a pair,
which before this module left the operator choreographing N resets in the
right order — reflectance rejected until emissivity *and* temperature were
each reset by hand (usability-audit F-07). Under the CU-377 ruling a door
entry **is** the switch: committing a value into one door withdraws the
other doors' explicit inputs as part of the same logical action (the Gap 117
companion-reset pattern of :mod:`radiant.gui.architecture_switch`), undoable
as one step, and the editor names what it withdraws before the commit.

The door membership mirrors the guards in ``radiant.source.target_spec``
(``check_reflectance_conflicts``, ``check_point_intensity_conflicts``,
``check_user_intensity_conflicts``, ``check_emissivity_path_conflicts``).
They are literals here because ``radiant.gui`` may import only
``radiant.api`` + ``radiant.core`` (import rules) — the same convention as the
stage input forms (CU-120). Surfaces the audit did not name (the S8 radiance
CSV, the S11/S12 temperature forms, the S10 intensity CSV) keep the seam's
plain refusal; they are not doors of this switch.
"""

from __future__ import annotations

from typing import Final

#: Door key → the user-entry surfaces that open it.
DOORS: Final[dict[str, tuple[str, ...]]] = {
    "thermal": (
        "source.target.temperature",
        "source.target.emissivity",
        "source.target.emissivity_path",
    ),
    "reflective": (
        "source.target.reflectance",
        "source.target.reflectance_path",
        "source.target.albedo",
        "source.target.albedo_path",
    ),
    "point_blackbody": (
        "source.target.point_intensity_temperature_K",
        "source.target.point_intensity_area_m2",
        "source.target.point_intensity_emissivity",
    ),
    "point_band": ("source.target.point_intensity_band_W_per_sr",),
}

_DOOR_OF: Final[dict[str, str]] = {
    dotpath: door for door, dotpaths in DOORS.items() for dotpath in dotpaths
}


def door_of(dotpath: str) -> str | None:
    """The source door *dotpath* opens, or ``None`` when it is not a door surface."""
    return _DOOR_OF.get(dotpath)


def companion_resets_for(dotpath: str) -> tuple[str, ...]:
    """The other doors' surfaces a commit into *dotpath* withdraws (empty if not a door)."""
    door = door_of(dotpath)
    if door is None:
        return ()
    return tuple(
        other_path
        for other_door, dotpaths in DOORS.items()
        if other_door != door
        for other_path in dotpaths
    )


__all__ = ["DOORS", "companion_resets_for", "door_of"]
