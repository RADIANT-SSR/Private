#!/usr/bin/env python
"""Verify (or fix) the per-package counts in ``docs/architecture/RADIANT_File_Tree.md``.

CU-229: the ``### `<pkg>/` — N source + M tests`` headings had drifted by up to 3×
(``performance/`` claimed 28+16 against an actual 52+36). They are the only
quantitative claim in that document, and a reader uses them to judge whether the
tree listing beneath is complete — so a stale count is worse than none.

A hand-maintained count of a growing tree is a Rule-20 drift generator by
construction, so the numbers are now **generated and gated** rather than
maintained. ``scripts/check_org_rules.py`` calls :func:`check` on every run.

Counting rule (stated here because the doc states it too, and the two must agree):

* **source** — ``*.py`` directly in ``src/radiant/<pkg>/``, excluding
  ``__init__.py``. Sub-packages (``optics/psf/``, ``gui/widgets/``) are listed
  separately in the document and are not counted here.
* **tests** — ``test_*.py`` directly in ``src/radiant/<pkg>/tests/``.

Usage::

    python scripts/check_file_tree_counts.py           # verify (exit 1 on drift)
    python scripts/check_file_tree_counts.py --fix     # rewrite the headings
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC = _REPO_ROOT / "docs" / "architecture" / "RADIANT_File_Tree.md"
_PKG_ROOT = _REPO_ROOT / "src" / "radiant"

#: ``### `<pkg>/` — N source + M test(s)`` — the heading form under audit. Headings
#: without a count (e.g. a package documented by prose alone) are left untouched.
_HEADING = re.compile(
    r"^### `(?P<pkg>[a-z_]+)/` — (?P<n>\d+) source \+ (?P<m>\d+) tests?$",
    re.MULTILINE,
)


def counts_for(pkg: str) -> tuple[int, int]:
    """``(source, tests)`` for *pkg* under the rule in the module docstring."""
    pkg_dir = _PKG_ROOT / pkg
    source = sum(1 for p in pkg_dir.glob("*.py") if p.name != "__init__.py")
    tests = len(list((pkg_dir / "tests").glob("test_*.py")))
    return source, tests


def _plural(n: int) -> str:
    return "test" if n == 1 else "tests"


def check(*, fix: bool = False) -> list[str]:
    """Return a list of drift messages; rewrite the doc when *fix* is set."""
    text = _DOC.read_text(encoding="utf-8")
    problems: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        pkg = match.group("pkg")
        if not (_PKG_ROOT / pkg).is_dir():
            problems.append(f"{_DOC.name}: heading names package '{pkg}/', which does not exist")
            return match.group(0)
        source, tests = counts_for(pkg)
        claimed = (int(match.group("n")), int(match.group("m")))
        if claimed != (source, tests):
            problems.append(
                f"{_DOC.name}: `{pkg}/` claims {claimed[0]} source + {claimed[1]} "
                f"tests, tree has {source} + {tests}"
            )
        return f"### `{pkg}/` — {source} source + {tests} {_plural(tests)}"

    updated = _HEADING.sub(_replace, text)
    if fix and updated != text:
        _DOC.write_text(updated, encoding="utf-8")
        return []
    return problems


def main() -> int:
    fix = "--fix" in sys.argv[1:]
    problems = check(fix=fix)
    if problems:
        print(f"check_file_tree_counts: {len(problems)} stale count(s)\n")
        for p in problems:
            print(f"  - {p}")
        print("\nRegenerate with: python scripts/check_file_tree_counts.py --fix")
        return 1
    print("check_file_tree_counts: OK" if not fix else "check_file_tree_counts: counts rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
