"""Mission-template discovery — one computation (Rule 19): find + describe templates.

The welcome screen offers every bundled mission template as a one-click
starting scenario (owner-confirmed brief, 2026-08-31). This module is the
Qt-free seam between that surface and the template store: it locates the
directory, reads each file's ``_radiant.template`` metadata through the public
:func:`radiant.api.config_io.read_template_meta` seam, and returns
display-ready records. The GUI renders what this returns and loads the chosen
path through the ordinary File→Open pipeline — no template-specific load path
exists (one action ↔ one API call).

Discovery is package-relative (CU-349): the six templates ship inside the
wheel at ``radiant/data/templates/`` and are resolved relative to the
``radiant.data`` module — the same convention every reference-table loader
uses, never the repo root (Rule 30). A from-source checkout and a bare
``pip install`` therefore behave identically; the empty-welcome-screen wheel
state this module used to document as supported was the CU-349 defect. This
module lives in ``radiant.api`` (not ``gui``) because the gui→data import is
forbidden while api→data is not; the GUI consumes it through the api surface.
The truth bar for the set itself (every template loads, evaluates
warning-free, and carries complete metadata) is CI:
``tests/integration/test_mission_templates.py``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from radiant.api.config_io import read_example_meta, read_template_meta
from radiant.core.exceptions import RadiantError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateInfo:
    """One mission template, display-ready.

    Attributes
    ----------
    path:
        The template YAML (feed to the ordinary open pipeline).
    name:
        Display name ("Ground → Air MWIR Detection").
    blurb:
        One-line mission description.
    specs:
        The mono specs line ("MWIR 3–5 µm · up-looking 60° zenith · point source").
    tune_next:
        3–5 parameter dot-paths this mission most expects the analyst to tune.
    """

    path: Path
    name: str
    blurb: str
    specs: str
    tune_next: tuple[str, ...] = field(default_factory=tuple)


def templates_dir() -> Path | None:
    """The bundled ``radiant/data/templates`` directory, or ``None`` if absent.

    Module-relative (the ``radiant.data`` tables convention, Rule 30): the
    same path serves a source checkout and an installed wheel. ``None`` means
    a broken installation (the package data was stripped); the welcome screen
    degrades to Blank + Recent rather than erroring, and CI pins the bundled
    set's presence.
    """
    import radiant.data

    found = Path(radiant.data.__file__).resolve().parent / "templates"
    return found if found.is_dir() else None


def discover_templates(directory: Path | None = None) -> tuple[TemplateInfo, ...]:
    """Every template in *directory* (default: :func:`templates_dir`), sorted by name.

    A file whose ``_radiant.template`` block is missing or unreadable is
    skipped with a logged warning rather than breaking the welcome screen —
    the CI truth bar is where a malformed template fails loudly.
    """
    root = directory if directory is not None else templates_dir()
    if root is None or not root.is_dir():
        return ()
    found: list[TemplateInfo] = []
    for path in sorted(root.glob("*.yaml")):
        try:
            meta = read_template_meta(path)
        except RadiantError as exc:
            logger.warning("mission template %s unreadable, skipped: %s", path.name, exc)
            continue
        if not isinstance(meta, dict) or not meta.get("name"):
            # A bundled file without template metadata is not a template
            # (the CU-339 corpus split means none should exist here).
            logger.debug("config %s carries no _radiant.template metadata, skipped", path.name)
            continue
        tune_next = meta.get("tune_next") or ()
        found.append(
            TemplateInfo(
                path=path,
                name=str(meta["name"]),
                blurb=str(meta.get("blurb", "")),
                specs=str(meta.get("specs", "")),
                tune_next=tuple(str(t) for t in tune_next),
            )
        )
    found.sort(key=lambda info: info.name)
    return tuple(found)


def examples_dir() -> Path | None:
    """The bundled ``radiant/data/examples`` directory, or ``None`` if absent.

    Module-relative like :func:`templates_dir` (Gap 126): the worked examples
    ship in the wheel beside the templates.
    """
    import radiant.data

    found = Path(radiant.data.__file__).resolve().parent / "examples"
    return found if found.is_dir() else None


def discover_examples(directory: Path | None = None) -> tuple[TemplateInfo, ...]:
    """Every bundled worked example, sorted by name (Gap 126).

    Same record shape and skip semantics as :func:`discover_templates` —
    the welcome screen renders both groups from one card type; an example's
    ``tune_next`` doubles as its "look at" hints. Data-only subdirectories
    (the OLI-2 CSV folder) carry no YAML and are naturally invisible.
    """
    root = directory if directory is not None else examples_dir()
    if root is None or not root.is_dir():
        return ()
    found: list[TemplateInfo] = []
    for path in sorted(root.glob("*.yaml")):
        try:
            meta = read_example_meta(path)
        except RadiantError as exc:
            logger.warning("worked example %s unreadable, skipped: %s", path.name, exc)
            continue
        if not isinstance(meta, dict) or not meta.get("name"):
            logger.debug("config %s carries no _radiant.example metadata, skipped", path.name)
            continue
        tune_next = meta.get("tune_next") or ()
        found.append(
            TemplateInfo(
                path=path,
                name=str(meta["name"]),
                blurb=str(meta.get("blurb", "")),
                specs=str(meta.get("specs", "")),
                tune_next=tuple(str(t) for t in tune_next),
            )
        )
    found.sort(key=lambda info: info.name)
    return tuple(found)


__all__ = [
    "TemplateInfo",
    "discover_examples",
    "discover_templates",
    "examples_dir",
    "templates_dir",
]
