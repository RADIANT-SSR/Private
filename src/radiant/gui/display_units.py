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

from typing import Final

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
