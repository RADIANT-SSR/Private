"""The GUI suite must never touch the real user preferences (walkthrough item 1).

The reported symptom was "the last few times I've opened it, it goes into the
default theme": a dark theme chosen in the View menu kept reverting to the light
default between launches. The persistence itself was fine — the value really was
written, and a fresh launch really did read it back. What reset it was the *test
suite*.

``SettingsStore`` builds its store with ``QSettings(organization, application)``,
and that constructor ignores :meth:`QSettings.setDefaultFormat`. On macOS it
resolves to ``NativeFormat`` and writes to the user's real
``com.RADIANT.RADIANT GUI.plist`` regardless of the ``setPath`` redirection the
CU-115 isolation fixture installs. Any GUI test that built a window without
injecting a settings store therefore wrote to the developer's own preferences —
and ``test_configured_parameters`` toggles the theme, so every run stamped a new
theme over the developer's choice.

These tests pin the isolation itself, so the leak cannot come back unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QSettings  # noqa: E402

from radiant.gui.settings_store import SettingsStore  # noqa: E402

# Where the real preferences live on each platform. A test-created store whose
# backing file is inside one of these trees has escaped its sandbox.
_REAL_PREF_MARKERS = ("Library/Preferences", ".config", "AppData")


class TestDefaultStoreIsSandboxed:
    """A bare ``SettingsStore()`` — the production default — must land in tmp."""

    def test_backing_file_is_not_the_users_real_preferences(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        store = SettingsStore()
        backing = Path(store._settings.fileName())  # noqa: SLF001
        assert not any(marker in str(backing) for marker in _REAL_PREF_MARKERS), (
            f"SettingsStore() escaped the test sandbox and is writing to {backing}"
        )

    def test_backing_file_lives_under_the_test_tmp_dir(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        store = SettingsStore()
        backing = Path(store._settings.fileName())  # noqa: SLF001
        assert tmp_path in backing.parents

    def test_uses_the_portable_ini_backend(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """NativeFormat is what defeats the redirection — the sandbox must not use it."""
        store = SettingsStore()
        assert store._settings.format() == QSettings.Format.IniFormat  # noqa: SLF001


class TestThemeWritesStayInTheSandbox:
    """The specific write that was clobbering the developer's theme."""

    def test_theme_write_is_not_visible_to_the_real_store(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        SettingsStore().set_theme_name("light")
        real = QSettings("RADIANT", "RADIANT GUI")
        # Whatever the real store holds, it is not this test's doing: the sandboxed
        # store must be a different backing file entirely.
        assert real.fileName() != SettingsStore()._settings.fileName()  # noqa: SLF001

    def test_each_test_gets_a_fresh_store(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Per-test tmp_path means no theme leaks from one test into the next."""
        assert SettingsStore().theme_name() is None


class TestInjectedStoreStillHonoured:
    """The sandbox must not break the injection path tests already rely on."""

    def test_explicit_qsettings_is_used_verbatim(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        explicit = tmp_path / "explicit.ini"
        store = SettingsStore(QSettings(str(explicit), QSettings.Format.IniFormat))
        store.set_theme_name("dark")
        assert Path(store._settings.fileName()) == explicit  # noqa: SLF001
        assert (
            SettingsStore(QSettings(str(explicit), QSettings.Format.IniFormat)).theme_name()
            == "dark"
        )
