"""QApplication bootstrap and the :func:`launch_gui` entry point.

This module owns the single :class:`QApplication` lifecycle for the RADIANT GUI.
It is deliberately thin: it constructs (or reuses) the application object, applies
the design-system theme, builds the main window, and hands control to the Qt event
loop. All UI structure lives in :mod:`radiant.gui.main_window`; all styling lives in
:mod:`radiant.gui.themes` (the light theme is the v1 launch default, applied here at
bootstrap — arch doc §8, Phase 0 checkpoint amendment 1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.settings_store import SettingsStore
from radiant.gui.themes import DARK, LIGHT, apply_theme

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet
    from radiant.api.sensor import Sensor


def _persisted_theme(settings: SettingsStore):  # type: ignore[no-untyped-def]
    """The theme to launch with — the persisted View-menu choice, else the light default.

    Light is the v1 launch default (Phase 0 checkpoint amendment 1); a prior run's
    View → Dark/Light toggle is honoured via :class:`~radiant.gui.settings_store.SettingsStore`
    (Phase 9), so the app reopens in the theme the operator last chose.
    """
    return DARK if settings.theme_name() == DARK.name else LIGHT


def launch_gui(
    sensor: Sensor | None = None,
    path: str | None = None,
    *,
    config_set: ConfigurationSet | None = None,
) -> int:
    """Launch the RADIANT desktop GUI and run the Qt event loop.

    Parameters
    ----------
    sensor:
        An already-configured :class:`~radiant.api.sensor.Sensor` to open the
        GUI on (the script → GUI hand-off, arch doc §5). ``None`` opens an empty
        window with no sensor loaded — the state after ``radiant gui`` with no
        config argument. Mutually exclusive with *config_set* (the window takes
        at most one document).
    path:
        The config path the document was loaded from, if any — shown in the
        window title (with the dirty marker) and seeded into the recent-files
        list. The ``radiant gui <config>`` command passes it so the launched
        file is named.
    config_set:
        A ready-made :class:`~radiant.api.config_set.ConfigurationSet` to open
        the GUI on — the study hand-off (CU-342). The CLI loads every file
        through ``ConfigurationSet.load`` (the API decides the document kind,
        same one-reader dispatch as the GUI's File → Open), so a study file
        arrives here as the full set and a plain config as the degenerate
        one-configuration set.

    Returns
    -------
    int
        The Qt event-loop exit code (``0`` on a clean quit). Returned rather than
        passed to :func:`sys.exit` so callers (tests, the CLI) decide how to exit.

    Notes
    -----
    Reuses an existing :class:`QApplication` if one is already running (e.g. under
    ``pytest-qt``, which owns the app), otherwise creates one. When it creates the
    app it runs the event loop; when it reuses a test-owned app it shows the window
    and returns ``0`` without blocking, so ``qtbot``-driven tests stay in control.
    """
    existing = QApplication.instance()
    settings = SettingsStore()

    if existing is None:
        # We create the application, so we own the event loop and the styling:
        # install the design-system theme (persisted choice, else the light v1
        # default) before any window is shown. A host that owns the app (the reuse
        # branch below) owns its own styling, so we do not override it there.
        app = QApplication([])
        apply_theme(app, _persisted_theme(settings))
        window = RADIANTMainWindow(
            sensor=sensor, path=path, settings=settings, config_set=config_set
        )
        window.show()
        return int(app.exec())

    # A host (pytest-qt) already owns the loop; show the window, hand it back via
    # a reference the host holds, and do not block.
    window = RADIANTMainWindow(sensor=sensor, path=path, settings=settings, config_set=config_set)
    window.show()
    _retain_window(existing, window)
    return 0


def _retain_window(app: QCoreApplication, window: RADIANTMainWindow) -> None:
    """Keep a reference to *window* alive on the host-owned *app*.

    Without this, a window created under a test-owned :class:`QApplication` would
    be garbage-collected the moment :func:`launch_gui` returns. Stored on the app
    object (not a module global) so parallel apps do not clobber each other.
    """
    retained: list[RADIANTMainWindow] = getattr(app, "_radiant_windows", [])
    retained.append(window)
    app._radiant_windows = retained  # type: ignore[attr-defined]
