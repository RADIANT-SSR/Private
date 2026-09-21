"""CU-151 — cross-platform MODTRAN binary-path default (Rule 30)."""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.atmosphere import _modtran_paths
from radiant.atmosphere._modtran_paths import (
    _POSIX_DEFAULT,
    _WINDOWS_DEFAULT,
    default_modtran_binary,
    default_modtran_binary_str,
)
from radiant.atmosphere._schema import MODTRAN_BINARY_PATH
from radiant.atmosphere.modtran import ModtranConfig


def test_prefers_modtran_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``modtran`` is on PATH, that resolved path wins on any platform."""
    monkeypatch.setattr(_modtran_paths.shutil, "which", lambda name: "/opt/modtran/bin/modtran")
    assert default_modtran_binary() == Path("/opt/modtran/bin/modtran")


def test_posix_fallback_when_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_modtran_paths.shutil, "which", lambda name: None)
    monkeypatch.setattr(_modtran_paths.sys, "platform", "linux")
    assert default_modtran_binary() == Path(_POSIX_DEFAULT)


def test_windows_fallback_when_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows without PATH, the default is a real Windows path, not a POSIX one."""
    monkeypatch.setattr(_modtran_paths.shutil, "which", lambda name: None)
    monkeypatch.setattr(_modtran_paths.sys, "platform", "win32")
    result = default_modtran_binary()
    assert result == Path(_WINDOWS_DEFAULT)
    assert not str(result).startswith("/usr")  # the CU-151 trap is gone


def test_str_form_matches_path_form(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_modtran_paths.shutil, "which", lambda name: None)
    monkeypatch.setattr(_modtran_paths.sys, "platform", "linux")
    assert default_modtran_binary_str() == str(default_modtran_binary())


def test_schema_default_is_empty_and_resolves_at_run_time() -> None:
    """The schema default is empty (CU-371 F-53); the loader resolves it to the
    same path the dataclass factory uses, and an explicit path is used verbatim."""
    from radiant.atmosphere.loaders import modtran_binary_path

    assert MODTRAN_BINARY_PATH.default == ""
    assert modtran_binary_path("") == ModtranConfig().binary_path
    assert modtran_binary_path("   ") == default_modtran_binary()
    assert modtran_binary_path("/custom/modtran") == Path("/custom/modtran")


def test_config_serialization_round_trip_preserves_binary_path() -> None:
    """A ModtranConfig binary_path survives an explicit set (Category B round-trip)."""
    cfg = ModtranConfig(binary_path=Path("/custom/modtran"))
    assert cfg.binary_path == Path("/custom/modtran")
