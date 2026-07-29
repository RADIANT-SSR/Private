"""Presentation helpers for the schema-driven parameter tree (arch doc §4.3).

Everything here turns the *public* :class:`~radiant.api.sensor.Sensor` surface —
:meth:`Sensor.parameter_defs`, :meth:`Sensor.get_input`, :meth:`Sensor.explain` — into
the text a tree row shows: the value with its unit suffix (R-UNITS, GUI plan §4.6), the
⚡ derived marker, and the provenance ("source") label. It also derives the namespace
ordering (geometry-first, then chain order) from the live chain rather than transcribing
a stage list (Gap 70).

These are pure functions with no Qt dependency, so the row-formatting contract is unit
tested directly (``tests/test_parameter_tree.py``) without a widget. No colour, font, or
size literal lives here — those belong to :mod:`radiant.gui.themes` (GUI plan §4.9).

Provenance sourcing: per-parameter provenance comes from the structured public
:meth:`Sensor.resolved` accessor (a :class:`~radiant.core.parameters.ResolvedValue`
carrying ``provenance``), read via :func:`safe_provenance`. This replaced the earlier
:meth:`Sensor.explain`-string parse (CU-105, resolved).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

import numpy as np

from radiant.api.session import RadiantSession
from radiant.api.units import convert, inverse_convert
from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterDef

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The ⚡ marker the mockup (§4.3) puts on derived rows. A glyph, not a style token.
DERIVED_BADGE = "⚡"

# The em-dash shown when a parameter is present in the schema but left unresolved
# (a required-unless parameter superseded by an alternative, so it has no value).
UNSET_TEXT = "—"

# Short, human labels for the "Source" (provenance) column, keyed on the
# ``Provenance`` enum *value* strings (radiant.core.parameters.Provenance). The
# arch-doc §4.3 badge vocabulary is user-set / default / derived; config_file is
# the YAML-supplied form of a user value and sampled is the Monte-Carlo form.
PROVENANCE_LABELS: Mapping[str, str] = {
    "user_set": "user-set",
    "config_file": "config",
    "default": "default",
    "derived": "derived",
    "sampled": "sampled",
}


def format_value(value: Any, unit: str) -> str:
    """Render a resolved parameter *value* with its *unit* suffix.

    Every dimensional value carries its unit (R-UNITS); a dimensionless parameter
    (empty ``unit``) shows the bare number. ``None`` (an unresolved parameter)
    renders as an em-dash. Floats use the shortest round-trip-ish ``g`` form so
    ``0.3`` and ``500000`` read cleanly; bools render lowercase; everything else
    (enums, ints, strings) uses ``str``.
    """
    if value is None:
        return UNSET_TEXT
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value)
    return f"{text} {unit}" if unit else text


def display_in_unit(
    value: Any,
    source_unit: str,
    display_unit: str,
    canonical_unit: str,
) -> Any:
    """Re-express *value* (given in *source_unit*) in *display_unit* — via the public seam.

    The GUI shows a canonical/input value in whatever unit the user chose for a row
    (owner feedback 2026-07-13: "the displayed units should be what the user chose").
    This performs **no ad-hoc unit maths** — it routes through the public
    :mod:`radiant.api.units` registry (``convert`` to the canonical unit, then
    ``inverse_convert`` out to the display unit). Round-tripping through the canonical
    unit is sound for every *registered* unit, affine ones included: the registry holds
    a multiplicative table **and** an affine ``(scale, offset)`` table
    (``radiant.core.units._AFFINE_CONVERSIONS`` — ``degC``/``degF`` ↔ ``K``, the only
    affine dimension), and ``convert`` / ``inverse_convert`` both dispatch through it.
    Do not re-derive a display value by dividing by a factor read out of the
    multiplicative table: that is exactly what breaks on a temperature row (CU-230 —
    this docstring previously asserted the affine table did not exist).

    Raises :class:`KeyError` when either leg is unregistered (a one-way or offset unit);
    the caller falls back to displaying *source_unit* for that row rather than inventing
    a conversion (Rule 2 — conversions happen only where the registry supports them).
    """
    if value is None or source_unit == display_unit:
        return value
    canonical = convert(float(value), source_unit, canonical_unit)
    return inverse_convert(canonical, canonical_unit, display_unit)


def safe_provenance(sensor: Sensor, dotpath: str) -> str:
    """Provenance token for *dotpath*, or "" when the sensor cannot resolve yet.

    Reads the structured :meth:`Sensor.resolved` accessor (CU-105) and returns the
    ``Provenance`` value string ("user_set", "config_file", "derived", …). On a config
    that cannot resolve (a blank File → New with required parameters unset) the accessor
    raises, and on a present-but-unresolved parameter it raises ``KeyError``; either way
    a display surface that only wants a provenance label gets "" instead of a crash
    (CU-140 guard tests).
    """
    try:
        return sensor.resolved(dotpath).provenance.value
    except (RadiantError, KeyError):
        return ""


def field_display_text(
    sensor: Sensor,
    dotpath: str,
    display_units: Mapping[str, str],
) -> str:
    """The value+unit text for *dotpath* in its chosen display unit (— if unset).

    The single formatter shared by every schema-driven field surface (the Geometry
    Inputs-tab :class:`~radiant.gui.widgets.geometry_mode_form.GeometryModeForm` and the
    Schematic-tab target dimension/RPY rows), so a value reads identically wherever it is
    shown. Reads the resolved input value off the public :meth:`Sensor.get_input` surface,
    then re-expresses it in whatever unit the user picked for the row (*display_units*,
    the shared session store) via the public registry seam — falling back to the schema
    ``input_unit`` when the target unit is not soundly convertible (Rule 2).
    """
    pdef = sensor.parameter_def(dotpath)
    try:
        value = sensor.get_input(dotpath)
    except (KeyError, RadiantError):
        # KeyError: present-but-unresolved parameter. RadiantError: the whole config
        # cannot resolve yet (a blank File → New) — the field shows unset, not a crash
        # (found 2026-07-16 with the CU-140 guard tests).
        value = None
    target = display_units.get(dotpath)
    if target is None or target == pdef.input_unit:
        return format_value(value, pdef.input_unit)
    try:
        shown = display_in_unit(value, pdef.input_unit, target, pdef.canonical_unit)
    except KeyError:
        return format_value(value, pdef.input_unit)
    return format_value(shown, target)


def provenance_label(provenance: str | None) -> str:
    """Short display label for a provenance token (empty for ``None``/unknown)."""
    if provenance is None:
        return ""
    return PROVENANCE_LABELS.get(provenance, provenance)


def is_derived(provenance: str | None) -> bool:
    """True when a parameter's value was derived from a consistency group."""
    return provenance == "derived"


def chain_namespace_order() -> tuple[str, ...]:
    """The chain-order stage namespaces (geometry first), read from the live chain.

    The top-level parameter namespaces are exactly the chain's stage names
    (``geometry``, ``source``, …, ``spectral_integration``, …, ``performance``),
    so the ordering is taken from :attr:`RadiantSession.stage_names` rather than
    transcribed — this stays correct if a stage is reordered or renamed and avoids
    the ``spectral`` vs ``spectral_integration`` token drift (CU-106). The tiny
    wavelength grid only satisfies the constructor; no chain is evaluated.
    """
    return RadiantSession(np.asarray([1.0, 2.0], dtype=np.float64)).stage_names


def ordered_namespaces(dotpaths: Iterable[str]) -> list[str]:
    """Namespaces present in *dotpaths*, chain-ordered, unknown ones appended.

    Namespaces are *discovered* from the schema (the first dot-path segment), then
    ordered by :func:`chain_namespace_order`; any namespace the chain does not name
    (a future ``sensor.*`` group, say) is appended in sorted order so nothing is
    silently dropped.
    """
    present: list[str] = []
    for dotpath in dotpaths:
        namespace = dotpath.split(".", 1)[0]
        if namespace not in present:
            present.append(namespace)
    canonical = chain_namespace_order()
    ordered = [ns for ns in canonical if ns in present]
    extras = sorted(ns for ns in present if ns not in canonical)
    return ordered + extras


def group_by_namespace(
    defs: Mapping[str, ParameterDef],
) -> dict[str, list[tuple[str, ParameterDef]]]:
    """Group ``{dotpath: ParameterDef}`` by first-segment namespace.

    Preserves the schema's insertion order within each namespace so rows read in
    the order the owning stage's ``_schema.py`` declares them.
    """
    grouped: dict[str, list[tuple[str, ParameterDef]]] = {}
    for dotpath, pdef in defs.items():
        namespace = dotpath.split(".", 1)[0]
        grouped.setdefault(namespace, []).append((dotpath, pdef))
    return grouped


__all__ = [
    "DERIVED_BADGE",
    "UNSET_TEXT",
    "PROVENANCE_LABELS",
    "format_value",
    "display_in_unit",
    "field_display_text",
    "safe_provenance",
    "provenance_label",
    "is_derived",
    "chain_namespace_order",
    "ordered_namespaces",
    "group_by_namespace",
]
