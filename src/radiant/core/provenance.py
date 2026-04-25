"""Run-time provenance helpers for RADIANT.

Per RADIANT_Master_Architecture.md §C13 ("Provenance Is Mandatory"), every
``ChainResult`` carries a complete provenance record: run ID, RADIANT
version, git commit, Python version, dependency versions, resolved
parameter set with per-parameter provenance, input file hashes, and
active model identifiers.

This module is the kit of pure helpers used by
:meth:`radiant.io.results.ChainResult.to_provenance_record` to assemble
that record:

- :func:`new_run_id` — generate a fresh UUID4 string.
- :func:`git_commit` — best-effort short SHA of HEAD (``"unknown"`` if
  not in a git repo or git is unavailable; never raises).
- :func:`python_version_string` — ``"3.11.7"``-style.
- :func:`dependency_versions` — ``{name: version}`` for the declared
  runtime dependencies (numpy, scipy, pyyaml, click); missing packages
  map to ``"unknown"`` rather than raising.
- :func:`hash_file` — SHA-256 hex digest of a file's bytes (used by
  :func:`radiant.io.config.load_config` to record the hash of every
  YAML it consumes).

All helpers are deterministic except :func:`new_run_id`. None of them
raise on edge cases — provenance must never block a chain run.

Lives under :mod:`radiant.core` so any module — including the rest of
``core`` — may import it without violating the import-linter "core has
no radiant imports" contract.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import logging
import subprocess
import sys
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Runtime dependencies declared in pyproject.toml. Kept here as the
# canonical list rather than parsed dynamically so that a pyproject
# parse failure doesn't silently empty the provenance record.
_RUNTIME_DEPENDENCIES: tuple[str, ...] = ("numpy", "scipy", "pyyaml", "click")


def new_run_id() -> str:
    """Return a fresh UUID4 string for a single chain run.

    Each call yields a different value. Used by :class:`ChainRunner.run`
    to mint a per-run identifier that the result carries forward.
    """
    return str(uuid.uuid4())


def git_commit() -> str:
    """Return the short SHA of ``HEAD`` for the current working tree.

    Best-effort: returns ``"unknown"`` if any of (a) we are not in a
    git repository, (b) the ``git`` binary is unavailable, (c) the
    subprocess fails for any reason. Never raises — provenance must
    not block a chain run.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("git_commit: subprocess failed (%s); returning 'unknown'", exc)
        return "unknown"

    if result.returncode != 0:
        logger.debug("git_commit: git rev-parse exited %d; returning 'unknown'", result.returncode)
        return "unknown"

    sha = result.stdout.strip()
    return sha if sha else "unknown"


def python_version_string() -> str:
    """Return ``MAJOR.MINOR.PATCH`` for the running Python interpreter."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def dependency_versions() -> dict[str, str]:
    """Return ``{name: version}`` for the declared runtime dependencies.

    Packages that cannot be located (uninstalled / not on the metadata
    path) map to ``"unknown"`` — the goal is a complete record, not a
    fragile one.
    """
    versions: dict[str, str] = {}
    for name in _RUNTIME_DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            logger.debug("dependency_versions: package '%s' not found; recording 'unknown'", name)
            versions[name] = "unknown"
    return versions


def hash_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of the file at ``path``.

    Reads the file in 64 KiB chunks so large files don't blow up
    memory. Raises :class:`FileNotFoundError` if the path does not
    exist (provenance for a hash request implies the caller already
    successfully read the file, so missing-file is a real error).
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()
