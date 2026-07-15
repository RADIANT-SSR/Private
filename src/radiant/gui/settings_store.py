"""Session-persistence store — the GUI's ``QSettings``-backed preferences (Phase 9).

The one home for the small set of preferences RADIANT GUI v1 remembers across launches
(GUI plan Phase 9, arch doc §10): the **recent-files** list (File → Open Recent), the
chosen **theme** (light default / dark alternate — the View-menu toggle), and per-**panel**
show/hide state. Everything routes through a single :class:`~PySide6.QtCore.QSettings`
handle so there is one persistence surface, not a scatter of ``QSettings`` constructions.

No physics, no colour/font/size literal (GUI plan §4.9) — this module only reads and writes
opaque preference values. Tests inject a temp-file-backed :class:`QSettings` so the suite
never touches a developer's real settings.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

# The application-identity a default :class:`QSettings` is scoped to. Kept here (not a
# theme token — it is an identity string, not a visual value) so every surface that
# persists a preference agrees on the same store.
_ORG: str = "RADIANT"
_APP: str = "RADIANT GUI"

# Cap the recent-files list so the File → Open Recent submenu stays short (arch doc §10).
_RECENT_LIMIT: int = 8

_KEY_RECENT: str = "recent_files"
_KEY_THEME: str = "theme"
_KEY_PANEL: str = "panels"


class SettingsStore:
    """Thin, typed wrapper over :class:`QSettings` for the v1 GUI preferences.

    Parameters
    ----------
    settings:
        An existing :class:`QSettings` to use (tests pass a temp-file-backed one so
        they never mutate the developer's real settings). ``None`` opens the default
        RADIANT-scoped store.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings(_ORG, _APP)

    # -- recent files -------------------------------------------------------

    def recent_files(self) -> list[str]:
        """The remembered recent config paths, most-recent first (may be empty)."""
        raw = self._settings.value(_KEY_RECENT, [])
        if raw is None:
            return []
        if isinstance(raw, str):  # a single value round-trips as a bare string
            return [raw]
        return [str(item) for item in raw]

    def add_recent_file(self, path: str) -> None:
        """Push *path* to the front of the recent list (deduped, capped)."""
        path = str(path)
        existing = [p for p in self.recent_files() if p != path]
        updated = [path, *existing][:_RECENT_LIMIT]
        self._settings.setValue(_KEY_RECENT, updated)

    def clear_recent_files(self) -> None:
        """Forget every remembered recent file."""
        self._settings.setValue(_KEY_RECENT, [])

    # -- theme --------------------------------------------------------------

    def theme_name(self) -> str | None:
        """The persisted theme name (``"LIGHT"`` / ``"DARK"``), or ``None`` if unset."""
        raw = self._settings.value(_KEY_THEME, None)
        return None if raw is None else str(raw)

    def set_theme_name(self, name: str) -> None:
        """Persist the chosen theme *name* (the View-menu toggle's choice)."""
        self._settings.setValue(_KEY_THEME, str(name))

    # -- panel visibility ---------------------------------------------------

    def panel_visible(self, key: str, default: bool = True) -> bool:
        """Whether panel *key* was last left visible (defaults to *default*)."""
        raw = self._settings.value(f"{_KEY_PANEL}/{key}", default)
        if isinstance(raw, bool):
            return raw
        # QSettings may round-trip a bool as the string "true"/"false".
        return str(raw).lower() in ("true", "1")

    def set_panel_visible(self, key: str, visible: bool) -> None:
        """Persist panel *key*'s show/hide state."""
        self._settings.setValue(f"{_KEY_PANEL}/{key}", bool(visible))


__all__ = ["SettingsStore"]
