"""``QSettings``-backed persistence — window geometry, dock state, theme.

Phase 6 (PLAN_v2.md §14 step 6): window position, size, dock visibility,
splitter ratios, and the active theme survive a quit / relaunch via
``QSettings``. This module is the single owner of every settings key the
GUI reads or writes; new persisted state lands here, not at random call
sites in ``main.py``.

Settings live under organization ``RADIANT`` / app ``Geometry`` so a
future RADIANT GUI shell can scope its own settings under the same
organization without colliding.

Rule 19: own file. Persistence is its own concern, distinct from theme
application (``theme.py``) and from window construction (``main.py``).
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QByteArray, QSettings

from dev_tools.geometry_gui_v2.app.theme import DEFAULT_DARK_THEME

ORG_NAME: Final[str] = "RADIANT"
APP_NAME: Final[str] = "Geometry"

KEY_WINDOW_GEOMETRY: Final[str] = "window/geometry"
KEY_WINDOW_STATE: Final[str] = "window/state"
KEY_THEME: Final[str] = "appearance/theme"
KEY_DEFAULT_FRAME: Final[str] = "interaction/default_frame"


def _settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def save_window_state(geometry: QByteArray, state: QByteArray) -> None:
    """Persist the main window's geometry + dock layout."""
    s = _settings()
    s.setValue(KEY_WINDOW_GEOMETRY, geometry)
    s.setValue(KEY_WINDOW_STATE, state)


def load_window_state() -> tuple[QByteArray | None, QByteArray | None]:
    """Restore the persisted (geometry, state) tuple, or (None, None) if
    this is the first launch."""
    s = _settings()
    geom = s.value(KEY_WINDOW_GEOMETRY)
    state = s.value(KEY_WINDOW_STATE)
    return (
        geom if isinstance(geom, QByteArray) else None,
        state if isinstance(state, QByteArray) else None,
    )


def save_theme(theme_xml: str) -> None:
    _settings().setValue(KEY_THEME, theme_xml)


def load_theme() -> str:
    """Return the persisted theme key, or the dark default on first launch."""
    s = _settings()
    value = s.value(KEY_THEME, DEFAULT_DARK_THEME)
    return str(value) if value is not None else DEFAULT_DARK_THEME


def save_default_frame(frame_value: str) -> None:
    _settings().setValue(KEY_DEFAULT_FRAME, frame_value)


def load_default_frame(default: str = "body") -> str:
    s = _settings()
    value = s.value(KEY_DEFAULT_FRAME, default)
    return str(value) if value is not None else default
