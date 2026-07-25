"""Build/version provenance — answer "which RADIANT am I actually running?".

The Windows first-deploy report traced several "already-fixed" bugs to a process
importing an **older** ``radiant`` than the deployed checkout (an editable-install
``.pth`` pointing at a stale tree, or a wheel built from an older commit). Nothing in
the product surfaced *where* the loaded package lives or *what commit* it is, so the
mismatch was invisible.

:func:`build_info` returns exactly that: the package version, the on-disk location the
``radiant`` package is imported from, and — when that location sits inside a git
checkout — the short commit SHA and dirty flag. The CLI ``--version`` output and the GUI
window title both render it, so "am I on ``main``?" is a glance, not a guess.

Git resolution is best-effort and never raises: no git binary, no repository, or a
detached/odd state simply yields ``sha=None`` (a wheel install has no ``.git`` and that
is the normal, correct answer). Cross-platform (Rule 30): paths via ``pathlib``,
``subprocess.run`` with a cross-platform ``timeout`` (no signal-based alarm).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import radiant


@dataclass(frozen=True)
class BuildInfo:
    """Resolved version provenance for the running ``radiant`` package."""

    version: str
    location: Path
    git_sha: str | None
    git_dirty: bool

    def one_line(self) -> str:
        """A compact single-line summary for the GUI title / logs."""
        if self.git_sha is not None:
            suffix = f"+{self.git_sha}" + ("-dirty" if self.git_dirty else "")
            return f"v{self.version} ({suffix})"
        return f"v{self.version}"

    def multi_line(self) -> str:
        """A multi-line summary for ``radiant --version`` — includes the load path."""
        lines = [f"radiant {self.version}", f"  loaded from: {self.location}"]
        if self.git_sha is not None:
            state = "dirty" if self.git_dirty else "clean"
            lines.append(f"  git commit:  {self.git_sha} ({state})")
        else:
            lines.append("  git commit:  n/a (not a git checkout — installed package)")
        return "\n".join(lines)


def _resolve_git(location: Path) -> tuple[str | None, bool]:
    """Best-effort short SHA + dirty flag for the checkout containing *location*.

    Returns ``(None, False)`` for any failure (no git, no repo, timeout) — a version
    string must never crash the CLI or GUI startup (Rule 17 carve-out: this is
    provenance metadata, not physics; a missing SHA is a legitimate answer).
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=location,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if sha.returncode != 0:
            return None, False
        short = sha.stdout.strip() or None
        if short is None:
            return None, False
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=location,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        dirty = status.returncode == 0 and bool(status.stdout.strip())
        return short, dirty
    except (OSError, subprocess.SubprocessError):
        # git absent, not a repo, or timed out — provenance is simply unavailable.
        return None, False


def build_info() -> BuildInfo:
    """Resolve the running package's version + load location + git provenance."""
    location = Path(radiant.__file__).resolve().parent
    sha, dirty = _resolve_git(location)
    return BuildInfo(
        version=radiant.__version__,
        location=location,
        git_sha=sha,
        git_dirty=dirty,
    )
