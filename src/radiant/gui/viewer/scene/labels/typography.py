"""Typography helpers for label rendering.

Every user-facing label in the application MUST resolve through
``viewport_label()`` (3D viewport, VTK math-text) or ``panel_label()``
(Qt panel, HTML with ``<sub>``). Hardcoded label strings are a
visual-remediation regression and the T10 grep test will catch them.

The single source of truth is ``glossary.yaml`` next to this module.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_GLOSSARY_PATH = Path(__file__).parent / "glossary.yaml"


@lru_cache(maxsize=1)
def _glossary() -> dict[str, dict[str, str]]:
    with _GLOSSARY_PATH.open() as f:
        return yaml.safe_load(f)


def viewport_label(key: str) -> str:
    """Return the label string for the 3D viewport (VTK math-text form).

    Raises ``KeyError`` if the key is not in the glossary.
    """
    return _glossary()[key]["latex"]


def panel_label(key: str) -> str:
    """Return the label string for Qt panels (HTML form, with ``<sub>``)."""
    return _glossary()[key]["html"]


def description(key: str) -> str:
    """Return the human-readable description (for tooltips, help overlay)."""
    return _glossary()[key]["description"]


def all_keys() -> list[str]:
    """Return all glossary keys (for tests and the help overlay)."""
    return list(_glossary().keys())
