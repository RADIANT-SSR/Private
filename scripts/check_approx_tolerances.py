"""Lint test suites for ``pytest.approx`` calls missing an explicit tolerance.

Enforces CLAUDE.md Rule 18: "``pytest.approx`` always uses explicit ``rel=`` or
``abs=`` tolerance — never the default." A bare ``pytest.approx(x)`` silently
uses ``rel=1e-6``, which is too loose to catch some sign/factor/unit errors and
too tight for others; the audit (2026-07, findings B1-6 / B2-7) found 29 such
calls, fixed in R1.10. This makes that a CI tripwire so new bare calls fail the
build instead of accumulating (audit unenforced-risk #3, R2.3).

Uses ``ast`` so only real call sites are matched (never strings or comments). A
call is compliant when it passes a tolerance either as a keyword (``rel=`` /
``abs=``) or positionally — ``pytest.approx(expected, rel, abs, …)`` — i.e. when
it has a second positional argument. Both ``pytest.approx(...)`` and a bare
``approx(...)`` (``from pytest import approx``) are recognized.

Scans every ``*.py`` under ``src/radiant/**/tests/`` and the top-level
``tests/`` tree. Exit 0 = clean; exit 1 = violations printed with file:line.
Runs in the CI ``static`` job.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _iter_test_files() -> list[Path]:
    files: list[Path] = []
    src = REPO / "src" / "radiant"
    if src.is_dir():
        files.extend(p for p in src.rglob("*.py") if "/tests/" in p.as_posix())
    tests_root = REPO / "tests"
    if tests_root.is_dir():
        files.extend(tests_root.rglob("*.py"))
    return sorted(set(files))


def _is_approx_call(node: ast.Call) -> bool:
    """True if ``node`` calls ``pytest.approx`` or a bare imported ``approx``."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "approx"
    if isinstance(func, ast.Name):
        return func.id == "approx"
    return False


def _has_tolerance(node: ast.Call) -> bool:
    """True if the approx call supplies rel/abs (keyword or positional).

    pytest.approx signature is ``approx(expected, rel=None, abs=None, ...)`` —
    a second positional argument is ``rel``, so ``len(args) >= 2`` counts.
    """
    if any(kw.arg in ("rel", "abs") for kw in node.keywords if kw.arg is not None):
        return True
    return len(node.args) >= 2


def _check_file(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # never silently skip a file
        return [f"{path.relative_to(REPO)}:{exc.lineno}: could not parse ({exc.msg})"]
    rel = path.relative_to(REPO)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_approx_call(node) and not _has_tolerance(node):
            violations.append(
                f"{rel}:{node.lineno}: pytest.approx() without an explicit rel=/abs= "
                "tolerance (Rule 18)"
            )
    return violations


def main() -> int:
    violations: list[str] = []
    for path in _iter_test_files():
        violations.extend(_check_file(path))

    if violations:
        print("pytest.approx tolerance lint FAILED:\n")
        for v in violations:
            print(f"  {v}")
        print(
            f"\n{len(violations)} bare pytest.approx call(s). Add an explicit rel= or abs= "
            "(Rule 18) — never rely on the default 1e-6."
        )
        return 1
    print("pytest.approx tolerance lint: clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
