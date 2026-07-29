#!/usr/bin/env python
"""Extract and run all ```python code blocks from docs/guides/*.md.

Usage::

    python scripts/test_docs_code.py

Each markdown file gets a shared namespace so later blocks can reference
variables from earlier blocks in the same file. Files are independent.

Exit code 0 if all blocks pass, 1 if any fail.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Run from the repo root so relative paths in code blocks work
os.chdir(Path(__file__).resolve().parent.parent)

# Ensure src/ is importable
sys.path.insert(0, str(Path("src").resolve()))

GUIDES_DIR = Path("docs/guides")
PATTERN = re.compile(r"^```python(?P<info>[^\n]*)\n(?P<code>.*?)^```", re.MULTILINE | re.DOTALL)

#: Fence markers this checker understands, as ```python <marker>.
#:
#: ``fragment`` — an *illustrative* snippet that is not meant to run standalone
#: (a CORRECT-vs-WRONG print example, an axis-label example, a line that uses a
#: ``row`` from a table the prose describes). Skipped, and reported as skipped so
#: the count stays visible rather than silently shrinking coverage.
#:
#: Any other marker is a hard error (CU-221): a typo'd marker must not quietly
#: disable a check — that is the same failure this checker exists to prevent.
FRAGMENT_MARKER = "fragment"


class UnknownFenceMarker(Exception):
    """A ```python fence carries an info string this checker does not understand."""


def extract_blocks(path: Path) -> tuple[list[tuple[int, str]], int]:
    """Return ``(runnable_blocks, skipped_count)`` for one markdown file.

    ``runnable_blocks`` is a list of ``(line_number, code_string)``. A fence
    tagged ``` ```python fragment ``` is counted in ``skipped_count`` instead —
    see :data:`FRAGMENT_MARKER`.

    Raises
    ------
    UnknownFenceMarker
        If a fence carries any other info string.
    """
    text = path.read_text(encoding="utf-8")
    blocks: list[tuple[int, str]] = []
    skipped = 0
    for match in PATTERN.finditer(text):
        # Count newlines before the match to get line number
        line_no = text[: match.start()].count("\n") + 1
        marker = match.group("info").strip()
        if marker == FRAGMENT_MARKER:
            skipped += 1
            continue
        if marker:
            raise UnknownFenceMarker(
                f"{path}:{line_no}: unknown fence marker {marker!r} — "
                f"expected no marker (runnable) or {FRAGMENT_MARKER!r} (illustrative)"
            )
        blocks.append((line_no, match.group("code")))
    return blocks, skipped


def run_block(code: str, namespace: dict) -> str | None:
    """Execute a code block. Returns None on success, error string on failure."""
    try:
        exec(compile(code, "<docs>", "exec"), namespace)  # noqa: S102
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def main() -> int:
    md_files = sorted(GUIDES_DIR.glob("*.md"))
    if not md_files:
        print("No markdown files found in docs/guides/")
        return 1

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures: list[str] = []

    for md_path in md_files:
        try:
            blocks, file_skipped = extract_blocks(md_path)
        except UnknownFenceMarker as exc:
            print(f"  ERROR {exc}")
            return 1
        skipped += file_skipped
        if not blocks:
            continue

        # Shared namespace per file
        namespace: dict = {"__builtins__": __builtins__}

        for line_no, code in blocks:
            total += 1
            label = f"{md_path}:{line_no}"
            err = run_block(code, namespace)
            if err is None:
                passed += 1
                print(f"  PASS  {label}")
            else:
                failed += 1
                failures.append(f"  FAIL  {label}\n        {err}")
                print(f"  FAIL  {label}")
                print(f"        {err}")

    print(f"\n{'=' * 60}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}  Skipped (fragment): {skipped}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f)
        return 1

    print("\nAll code blocks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
