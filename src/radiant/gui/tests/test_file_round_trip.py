"""File round-trip tests — New / Open / Open Recent / Save / Save As (GUI plan Phase 9).

Drives the File menu end to end, offscreen, on the shipped example config: the window
title tracks the current file + a dirty marker, Open swaps the sensor through the shared
adopt path, Save round-trips through ``Sensor.save`` / ``Sensor.load``, Open Recent is
persisted via an injected temp ``QSettings``, and a bad file surfaces an actionable error
(Rule 15) without disturbing the live sensor.

Category D: the UX round trip. Golden results are untouched — the GUI is a view over the
scripting API — so the regression half is the separate full-chain suite.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog

from radiant.api.sensor import Sensor
from radiant.gui import main_window as mw
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.settings_store import SettingsStore

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000


def _settings(tmp_path: Path) -> SettingsStore:
    """A temp-file-backed settings store so tests never touch real QSettings."""
    return SettingsStore(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _window(qtbot, tmp_path: Path, *, path: str | None = None):  # type: ignore[no-untyped-def]
    """Build a window on the example config with injected temp settings, await load."""
    sensor = Sensor.load(_EXAMPLE)
    window = RADIANTMainWindow(sensor, path=path, settings=_settings(tmp_path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestTitleAndDirty:
    def test_title_shows_file_no_dirty_on_load(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A loaded config shows its file name and no dirty marker."""
        window = _window(qtbot, tmp_path, path=str(_EXAMPLE))
        assert window.windowTitle().startswith("mwir_leo_minimal.yaml — RADIANT")
        assert "*" not in window.windowTitle()

    def test_edit_sets_dirty_marker(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Any accepted parameter edit sets the title's leading ``*``."""
        window = _window(qtbot, tmp_path, path=str(_EXAMPLE))
        window.sensor.set(_APERTURE, 0.6)
        window._on_parameter_edited(_APERTURE)
        assert window.windowTitle().startswith("* ")
        assert window.windowTitle().startswith("* mwir_leo_minimal.yaml — RADIANT")


class TestSaveRoundTrip:
    def test_save_clears_dirty_and_round_trips(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Save writes the config, clears the marker, and reloads to identical values."""
        window = _window(qtbot, tmp_path, path=str(_EXAMPLE))
        window.sensor.set(_APERTURE, 0.6)
        window._on_parameter_edited(_APERTURE)
        assert window.windowTitle().startswith("* ")

        out = tmp_path / "roundtrip.yaml"
        window._save_to_path(out)

        assert "*" not in window.windowTitle()
        assert window.windowTitle().startswith("roundtrip.yaml — RADIANT")
        reloaded = Sensor.load(str(out))
        assert reloaded.get(_APERTURE) == window.sensor.get(_APERTURE) == 0.6


class TestOpenSwapsSensor:
    def test_open_swaps_sensor_and_updates_title(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Opening a file swaps the live sensor, updates the title, clears dirty."""
        window = _window(qtbot, tmp_path)  # launched with no path (untitled)
        assert window.windowTitle().startswith("untitled — RADIANT")

        # Write a distinct config to open (a changed aperture) and open it.
        other = tmp_path / "other.yaml"
        edited = Sensor.load(_EXAMPLE)
        edited.set(_APERTURE, 0.42)
        edited.save(other)

        first = window.sensor
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._open_path(str(other))
        assert window.sensor is not first  # a genuinely new sensor object
        assert window.sensor.get(_APERTURE) == 0.42
        assert window.windowTitle().startswith("other.yaml — RADIANT")
        assert "*" not in window.windowTitle()


class TestOpenRecent:
    def test_recent_files_persist_and_menu_populates(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Opened/saved files land in the persisted recent list and its submenu."""
        settings = _settings(tmp_path)
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE), path=str(_EXAMPLE), settings=settings)
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass

        # Save-As a second file, then confirm both are remembered, most-recent first.
        out = tmp_path / "second.yaml"
        window._save_to_path(out)

        recent = settings.recent_files()
        assert str(out) == recent[0]
        assert str(_EXAMPLE) in recent
        # The Open Recent submenu is enabled and lists an action per remembered file.
        assert window._recent_menu.isEnabled()
        assert len(window._recent_menu.actions()) == len(recent)


class TestBadFileLoad:
    def test_missing_file_shows_error_and_keeps_sensor(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Opening a missing file surfaces an error dialog and leaves the sensor intact."""
        window = _window(qtbot, tmp_path, path=str(_EXAMPLE))
        original = window.sensor

        shown: list[str] = []

        class _StubDialog(QDialog):
            """A real QDialog: `exec_dialog` deleteLater()s what it runs (CU-216)."""

            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
                super().__init__()
                shown.append("shown")

            def exec(self) -> int:
                return 0

        # A missing file raises FileNotFoundError (OSError) → the unexpected-error dialog.
        monkeypatch.setattr(mw, "UnexpectedErrorDialog", _StubDialog)
        monkeypatch.setattr(mw, "ActionableErrorDialog", _StubDialog)
        window._open_path(str(tmp_path / "does_not_exist.yaml"))

        assert shown, "a bad file must surface an error dialog (Rule 15)"
        assert window.sensor is original  # the live sensor was never swapped out
