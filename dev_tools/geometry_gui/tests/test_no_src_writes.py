"""C1 gate test — no commit in repo history bundles a /src change with a
dev_tools/geometry_gui/ change.

PLAN.md §3 hard constraint C1: this developer tool must never modify /src.
The lightweight enforcement is a `git log` audit: if any commit's changeset
contains files from BOTH `src/` and `dev_tools/geometry_gui/`, the tool's
isolation has been broken and merge must be blocked.

The test passes today (the tool only ever creates files under
`dev_tools/geometry_gui/`). It will fail the moment a future contributor
bundles a /src change with a GUI change.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PREFIX = "src/"
GUI_PREFIX = "dev_tools/geometry_gui/"


def _git_available() -> bool:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _commits_touching_both_paths() -> list[str]:
    """Return SHAs of any commit that modified files in BOTH /src and the GUI tool."""
    raw = subprocess.check_output(
        [
            "git",
            "log",
            "--all",
            "--name-only",
            "--pretty=format:COMMIT %H",
            "--",
            "src/",
            "dev_tools/geometry_gui/",
        ],
        cwd=REPO_ROOT,
        text=True,
    )

    offenders: list[str] = []
    current_sha: str | None = None
    saw_src = False
    saw_gui = False
    for line in raw.splitlines():
        if line.startswith("COMMIT "):
            if current_sha is not None and saw_src and saw_gui:
                offenders.append(current_sha)
            current_sha = line.split(" ", 1)[1].strip()
            saw_src = False
            saw_gui = False
            continue
        if not line.strip():
            continue
        if line.startswith(SRC_PREFIX):
            saw_src = True
        elif line.startswith(GUI_PREFIX):
            saw_gui = True
    if current_sha is not None and saw_src and saw_gui:
        offenders.append(current_sha)
    return offenders


def test_no_commit_bundles_src_and_gui_changes() -> None:
    if not _git_available():
        pytest.skip("git is not available in this environment")
    offenders = _commits_touching_both_paths()
    assert offenders == [], (
        "C1 violation — these commits touch both /src and dev_tools/geometry_gui/:\n"
        + "\n".join(f"  {sha}" for sha in offenders)
        + "\n\nSplit each into two commits (one /src, one GUI) to restore C1."
    )
