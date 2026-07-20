"""Presentation helpers for the YAML detail tab (arch doc §4.5).

The YAML tab shows the **current config** the way the scripting API serialises it —
via the one public serialize surface, :meth:`~radiant.api.sensor.Sensor.save` — with
each parameter line tinted by its provenance (user-set / config / default / derived),
reusing the structured provenance path (:func:`radiant.gui.param_format.safe_provenance`).

Two pure (Qt-free) pieces live here so the mapping is unit-tested without a widget:

* :func:`serialize_yaml` — the YAML text, obtained by round-tripping through
  ``Sensor.save`` (there is no in-memory / string serialize surface on the public API;
  see Gap 88). ``Sensor.save`` writes the *inputs* scope, so the text round-trips
  through the loader exactly; defaults and derived values are re-applied on load and so
  do not appear as lines (a fully-resolved export would need a resolved-scope serialize
  surface the GUI cannot reach — Gap 88).
* :func:`line_provenance` — for each text line, the provenance token of the parameter it
  declares (or ``None`` for comments, blank lines, and the ``_radiant`` meta block),
  reconstructing each leaf's dot-path from YAML indentation.

The provenance→design-token mapping (:data:`PROVENANCE_TOKEN`) names a
:class:`~radiant.gui.themes.tokens.Theme` **attribute**, never a colour literal — the
widget resolves the colour through :func:`radiant.gui.themes.active_theme` so every value
still lives in ``themes/`` (GUI plan §4.9, review-blocking).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from radiant.gui.param_format import safe_provenance

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

logger = logging.getLogger(__name__)

# Provenance token (radiant.core.parameters.Provenance value) → the Theme colour
# attribute a line of that provenance is tinted with. Names an attribute of
# radiant.gui.themes.tokens.Theme; the widget reads the hex through active_theme(), so
# no colour literal lives outside themes/. Tokens not listed render in the default ink.
PROVENANCE_TOKEN: Mapping[str, str] = {
    "user_set": "accent",  # the user's own value — terracotta accent
    "config_file": "focus",  # supplied by the loaded YAML — focus blue
    "default": "muted",  # schema default — muted grey
    "derived": "ok",  # consistency-group derived — ok green
    "sampled": "warn",  # Monte-Carlo sampled — warn amber
}


def serialize_yaml(sensor: Sensor) -> str:
    """Return the current config serialised to YAML (inputs scope).

    One public call — ``Sensor.to_yaml(scope="inputs")`` (Gap 88 closed
    2026-07-16; the historical temp-file round trip through ``Sensor.save``
    is gone). The text round-trips through the loader exactly (the contract
    the YAML tab's export relies on).
    """
    return sensor.to_yaml(scope="inputs")


def dotpath_provenance(sensor: Sensor) -> dict[str, str]:
    """Map every schema dot-path to its provenance token via the structured accessor.

    Reads :func:`safe_provenance` (which wraps :meth:`Sensor.resolved`, CU-105) for each
    key in :meth:`Sensor.parameter_defs`. Unresolved parameters (``safe_provenance``
    returns "") are omitted.
    """
    mapping: dict[str, str] = {}
    for dotpath in sensor.parameter_defs():
        token = safe_provenance(sensor, dotpath)
        if token:
            mapping[dotpath] = token
    return mapping


def line_provenance(
    yaml_text: str,
    dotpath_tokens: Mapping[str, str],
) -> list[tuple[str, str | None]]:
    """Pair each YAML line with the provenance token of the parameter it declares.

    Reconstructs each leaf's dot-path from YAML indentation (``Sensor.save`` writes the
    inputs unflattened, so nested keys are exactly the dot-path segments), then looks the
    dot-path up in *dotpath_tokens*. Comment lines, blank lines, list items, mapping
    parents, and the ``_radiant`` meta block (no schema dot-path) pair with ``None``.
    """
    result: list[tuple[str, str | None]] = []
    stack: list[tuple[int, str]] = []  # (indent, key) of the open mapping parents
    for line in yaml_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            result.append((line, None))
            continue
        if ":" not in stripped:
            result.append((line, None))
            continue
        indent = len(line) - len(line.lstrip(" "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key, _sep, rest = stripped.partition(":")
        key = key.strip()
        dotpath = ".".join([k for _indent, k in stack] + [key])
        if rest.strip() == "":
            # A mapping parent — descend; parents are not leaf parameters.
            stack.append((indent, key))
            result.append((line, dotpath_tokens.get(dotpath)))
        else:
            result.append((line, dotpath_tokens.get(dotpath)))
    return result


__all__ = [
    "PROVENANCE_TOKEN",
    "serialize_yaml",
    "dotpath_provenance",
    "line_provenance",
]
