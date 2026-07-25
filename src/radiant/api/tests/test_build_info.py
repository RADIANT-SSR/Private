"""Tests for radiant.api.build_info — version/load-path/git provenance (WS-A3)."""

from __future__ import annotations

from pathlib import Path

import radiant
from radiant.api.build_info import BuildInfo, build_info


def test_build_info_version_matches_package() -> None:
    """The reported version is the package's own ``__version__``."""
    assert build_info().version == radiant.__version__


def test_build_info_location_is_the_package_dir() -> None:
    """The load path points at the imported ``radiant`` package (has __init__.py)."""
    info = build_info()
    assert isinstance(info.location, Path)
    assert (info.location / "__init__.py").is_file()
    assert info.location == Path(radiant.__file__).resolve().parent


def test_one_line_starts_with_version() -> None:
    """The compact label leads with ``vX.Y.Z`` for the window title."""
    assert build_info().one_line().startswith(f"v{radiant.__version__}")


def test_multi_line_reveals_load_path() -> None:
    """The CLI summary names the load path — the stale-install tell (WS-A3)."""
    text = build_info().multi_line()
    assert "loaded from:" in text
    assert str(build_info().location) in text
    assert "git commit:" in text


def test_git_resolution_is_best_effort_never_raises() -> None:
    """A location with no git repo yields sha=None, not an exception (Rule 17 carve-out)."""
    from radiant.api.build_info import _resolve_git

    sha, dirty = _resolve_git(Path("/"))  # not a git checkout
    assert sha is None
    assert dirty is False


def test_one_line_without_sha_is_bare_version() -> None:
    """When git provenance is absent, the label is just the version (no ``+`` suffix)."""
    info = BuildInfo(version="9.9.9", location=Path("/tmp"), git_sha=None, git_dirty=False)
    assert info.one_line() == "v9.9.9"
    assert "git commit:  n/a" in info.multi_line()
