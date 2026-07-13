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

Provenance sourcing (read this): the Sensor public API exposes per-parameter provenance
only through the human-readable :meth:`Sensor.explain` string (the structured
:class:`~radiant.core.parameters.ResolvedValue` lives behind the private
``Sensor._params``). Per GUI plan ground rule §4.1 the GUI must not reach into that
internal, so :func:`provenance_from_explain` parses the one public surface that carries
it. That text coupling is tracked as CU-105 (recommend a structured
``Sensor.provenance()``/resolved accessor to replace the parse).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from radiant.api.session import RadiantSession
from radiant.core.parameters import ParameterDef

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

_PROVENANCE_PREFIX = "Provenance:"


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


def provenance_from_explain(explain_text: str) -> str | None:
    """Extract the provenance token from a :meth:`Sensor.explain` string.

    Returns the raw ``Provenance`` value (e.g. ``"config_file"``, ``"derived"``)
    or ``None`` when the explanation carries no provenance line — the case for an
    unresolved parameter, which :meth:`Sensor.explain` reports as "not resolved".
    See the module docstring / CU-105 for why this parses text.
    """
    for line in explain_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_PROVENANCE_PREFIX):
            return stripped[len(_PROVENANCE_PREFIX) :].strip() or None
    return None


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
    "provenance_from_explain",
    "provenance_label",
    "is_derived",
    "chain_namespace_order",
    "ordered_namespaces",
    "group_by_namespace",
]
