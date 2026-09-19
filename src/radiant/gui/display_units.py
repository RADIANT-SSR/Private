"""Global display-unit preference — one computation (Rule 19): unit resolution for display.

Owner ruling 2026-08-03 (CU-326): the GUI carries a **global, display-only**
unit preference — angles render in degrees by default — layered *under* the
existing per-row display-unit overrides and *over* the schema ``input_unit``.
Resolution order for any row or field::

    per-row override  →  global preference  →  schema input_unit

Canonical storage is untouched (Rule 2: the preference changes what is *shown*
and how typed values are *interpreted*, never what is stored — the API performs
the single conversion at the ``sensor.set(unit=…)`` boundary, exactly as the
per-row overrides already do).

Scope is deliberately narrow: only parameters whose schema ``input_unit`` is
``rad`` map to ``deg``. Parameters authored in ``mrad``/``µrad`` (jitter,
IFOV-scale angles) keep their schema unit — re-expressing 0.005 mrad as
2.9e-4 deg would be *worse* legibility, and the schema chose those units
deliberately.

The active state follows the :func:`~radiant.gui.themes.stylesheet.active_theme`
precedent: a module-level value set by the main window (from
:class:`~radiant.gui.settings_store.SettingsStore` at startup, then by the
View-menu toggle), read by every display surface. Widgets never hold their own
copy, so the panel, the stage forms, and the editors cannot disagree.

This module also owns display-side **unit cosmetics** (:func:`pretty_unit`):
ASCII exponent forms from the schema render typeset (``m2`` → ``m²``) — the
instrument look lives or dies on this (Visible Unit Rule).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from radiant.core.parameters import ParameterDef

#: The global preference when "angles in degrees" is ON (the shipped default):
#: schema input-unit → preferred display unit.
_ANGLES_IN_DEGREES: Final[dict[str, str]] = {"rad": "deg"}

#: Settings key for the persisted toggle (read/written by the main window).
ANGLES_IN_DEGREES_KEY: Final[str] = "display_units/angles_in_degrees"

# The active mapping. Default ON per the owner ruling; the main window overwrites
# from settings at startup and on every View-menu toggle.
_active: dict[str, str] = dict(_ANGLES_IN_DEGREES)


def set_angles_in_degrees(enabled: bool) -> None:
    """Install the global preference state (main-window/settings seam)."""
    global _active
    _active = dict(_ANGLES_IN_DEGREES) if enabled else {}


def angles_in_degrees() -> bool:
    """Whether the angles-in-degrees preference is currently active."""
    return bool(_active)


def global_display_unit(input_unit: str) -> str | None:
    """The globally preferred display unit for *input_unit*, or ``None``.

    ``None`` means "no preference — use the schema unit". Per-row overrides are
    resolved by the caller *before* consulting this.
    """
    return _active.get(input_unit)


def default_display_unit(input_unit: str) -> str:
    """The unit a row displays in with **no** per-row override: preference, else schema."""
    return global_display_unit(input_unit) or input_unit


#: The units the angles toggle governs — an override in one of these is the toggle's
#: business, not a per-row choice that should outrank it.
_GOVERNED_ANGLE_UNITS: Final[frozenset[str]] = frozenset({"rad", *_ANGLES_IN_DEGREES.values()})


def drop_governed_overrides(
    store: dict[str, str], defs: Mapping[str, ParameterDef]
) -> tuple[str, ...]:
    """Drop per-row overrides the angles toggle governs; return the dot-paths cleared.

    CU-372 F-37: the unit chosen in a Parameter Editor commit becomes the row's sticky
    display unit, and that override *outranked* the global toggle — a row edited while
    degrees were on kept reading ``deg`` after the toggle went off, and a value then
    typed "in radians" landed in degrees. The toggle is the outer authority for the
    rad↔deg choice: flipping it clears every override that is itself ``rad`` or
    ``deg`` on a ``rad``-schema row, so those rows follow the toggle again. An
    override in any other unit (``mrad`` on a rad row, ``km`` on a length row) is a
    genuine per-row choice and survives.
    """
    cleared = tuple(
        dotpath
        for dotpath, unit in store.items()
        if unit in _GOVERNED_ANGLE_UNITS
        and dotpath in defs
        and (defs[dotpath].input_unit or "") == "rad"
    )
    for dotpath in cleared:
        del store[dotpath]
    return cleared


#: ASCII → typeset display forms for unit strings. Display-side only; the
#: registry and schema keep their ASCII spellings.
_PRETTY_UNITS: Final[dict[str, str]] = {
    "m2": "m²",
    "m^2": "m²",
    "m3": "m³",
    "m^3": "m³",
    "um": "µm",
    "urad": "µrad",
}


def pretty_unit(unit: str) -> str:
    """Typeset display form of a unit string (``m2`` → ``m²``); unknown → unchanged."""
    return _PRETTY_UNITS.get(unit, unit)
