"""Mission-template discovery — one computation (Rule 19): find + describe templates.

The welcome screen offers every YAML under ``examples/templates/`` as a
one-click starting scenario (owner-confirmed brief, 2026-08-31). This module is
the Qt-free seam between that surface and the filesystem: it locates the
template directory, reads each file's ``_radiant.template`` metadata through
the public :func:`radiant.io.config.read_radiant_meta` seam, and returns
display-ready records. The GUI renders what this returns and loads the chosen
path through the ordinary File→Open pipeline — no template-specific load path
exists (one action ↔ one API call).

Discovery is repo-relative: templates ship in the repository's ``examples/``
tree (not in the wheel), so a from-source / editable install finds them by
walking up from this file to ``pyproject.toml``, and a bare wheel install —
where no repository exists — degrades to an empty list, which the welcome
screen renders as Blank + Recent only. The truth bar for the set itself
(every template loads, evaluates warning-free, and carries complete metadata)
is CI: ``tests/integration/test_mission_templates.py``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from radiant.api.config_io import read_template_meta
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


def templates_dir(start: Path | None = None) -> Path | None:
    """The repository's ``examples/templates`` directory, or ``None`` off-repo.

    Walks up from *start* (default: this file) to the ``pyproject.toml`` repo
    root — the same rooting the test suite uses — then checks for the
    directory. ``None`` (a wheel install, or a repo without templates) is a
    supported state, not an error: the welcome screen simply shows no cards.
    """
    probe = (start if start is not None else Path(__file__)).resolve()
    for candidate in (probe, *probe.parents):
        if (candidate / "pyproject.toml").exists():
            found = candidate / "examples" / "templates"
            return found if found.is_dir() else None
    return None


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
            # Expected for the inferrer-corpus files sharing the directory
            # (CU-338): not templates, silently invisible to the welcome screen.
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


__all__ = ["TemplateInfo", "discover_templates", "templates_dir"]
