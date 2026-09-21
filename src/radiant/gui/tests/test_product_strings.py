"""CU-371: product strings carry no process language (audit F-52/F-53, II-003, II-015).

Operators read the GUI's notes, tooltips, refusals and warnings in every session, and
the manuals quote them; a string that says "Gap 65", "ADR-0010 D-E", "v1-minimal
(owner-ratified …)" or "Rule 8" is talking to the project's tracking system, not to
the operator. This test walks the **string literals** (never docstrings — those are
for developers) of every GUI module and of the library modules whose messages the
audit named, and fails on the first process token. It failed on the pre-fix code with
33 GUI hits and 19 library hits.

Qt-free: a source scan, so it runs anywhere the package is importable.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import radiant

_SRC = Path(radiant.__file__).resolve().parent

#: Tracking-system vocabulary that must not reach an operator.
_TOKEN = re.compile(
    r"\b(?:Gap|CU|ADR)[- ]?\d"  # Gap 65, CU-122, ADR-0010
    r"|owner[- ]ratified"
    r"|v1[-.]minimal|\bv1\.x\b|post-v1"
    r"|\bRule \d|\bplan §|\bPhase [A-Z0-9]\b"
)

#: The library modules whose user-facing messages the audit named (readout saturation
#: warnings, the horizon guard, the configuration-set cap and shape errors).
_LIBRARY_FILES = (
    "readout/stage.py",
    "core/viewing_triangle.py",
    "io/config_set_section.py",
    "api/config_set.py",
    "spectral_integration/stage.py",
    "optics/transmission_modes.py",
)

#: The stylesheet's string is CSS whose comments cite the design history; it is never
#: rendered as text.
_EXCLUDED = ("gui/themes/stylesheet.py",)


def _scanned_files() -> list[Path]:
    gui = sorted(
        p
        for p in (_SRC / "gui").rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.as_posix().endswith(_EXCLUDED)
    )
    return gui + [_SRC / rel for rel in _LIBRARY_FILES]


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr):
                value = getattr(body[0], "value", None)
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    ids.add(id(value))
    return ids


def process_language_hits(path: Path) -> list[str]:
    """``"<file>:<line>: <excerpt>"`` for every string literal carrying a process token."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(tree)
    hits: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings:
            continue
        match = _TOKEN.search(node.value)
        if match:
            start = max(0, match.start() - 30)
            excerpt = node.value[start : match.end() + 20].replace("\n", " ")
            hits.append(f"{path.relative_to(_SRC)}:{node.lineno}: …{excerpt}…")
    return hits


def test_no_process_language_in_product_strings() -> None:
    hits = [hit for path in _scanned_files() for hit in process_language_hits(path)]
    assert not hits, "process language in product strings:\n  " + "\n  ".join(hits)


def test_scan_reaches_the_named_surfaces() -> None:
    """The scan covers the modules the audit named (a moved file must not silently drop out)."""
    names = {p.name for p in _scanned_files()}
    assert {"stage_views.py", "platform_inputs_form.py", "stage.py", "viewing_triangle.py"} <= names
