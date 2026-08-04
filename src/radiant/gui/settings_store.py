"""Session-persistence store — the GUI's ``QSettings``-backed preferences (Phase 9).

The one home for the small set of preferences RADIANT GUI v1 remembers across launches
(GUI plan Phase 9, arch doc §10): the **recent-files** list (File → Open Recent), the
chosen **theme** (light default / dark alternate — the View-menu toggle), and per-**panel**
show/hide state. Everything routes through a single :class:`~PySide6.QtCore.QSettings`
handle so there is one persistence surface, not a scatter of ``QSettings`` constructions.

**Backend (CU-233).** The store is built with an explicit ``IniFormat`` /
``UserScope`` :class:`QSettings`, the same backend
:class:`~radiant.gui.widgets.pinned_panel.PinnedPanel` chose: portable across
macOS and Windows (Rule 30), and — decisively — redirectable by
:meth:`QSettings.setPath`, which is what lets the test suite sandbox it. The
two-argument ``QSettings(organization, application)`` constructor this class used
before **ignores** :meth:`QSettings.setDefaultFormat` and resolves to
``NativeFormat``, so no redirection reached it and every GUI test that built a
window without injecting a store overwrote the real user's preferences.

No physics, no colour/font/size literal (GUI plan §4.9) — this module only reads and writes
opaque preference values. Tests inject a temp-file-backed :class:`QSettings` so the suite
never touches a developer's real settings.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QSettings

# The application-identity a default :class:`QSettings` is scoped to. Kept here (not a
# theme token — it is an identity string, not a visual value) so every surface that
# persists a preference agrees on the same store.
_ORG: str = "RADIANT"
_APP: str = "RADIANT GUI"

# Cap the recent-files list so the File → Open Recent submenu stays short (arch doc §10).
_RECENT_LIMIT: int = 8

_KEY_RECENT: str = "recent_files"
_KEY_RECENT_SCRIPTS: str = "recent_scripts"
_KEY_THEME: str = "theme"
_KEY_PANEL: str = "panels"
_KEY_ANGLES_DEG: str = "display_units/angles_in_degrees"
_KEY_SWEEP_SPEC: str = "sweep/last_spec"


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
        # IniFormat explicitly, matching PinnedPanel (CU-115) — NOT the two-argument
        # QSettings(org, app) constructor, which ignores QSettings.setDefaultFormat()
        # and resolves to NativeFormat. That made this store unreachable by the
        # suite's setPath redirection, so GUI tests wrote the developer's real
        # preferences and kept resetting their chosen theme (CU-233).
        self._settings = (
            settings
            if settings is not None
            else QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _ORG, _APP)
        )

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

    # -- recent scripts (the scripting-window Editor, §4.6.1 Pass 2) --------

    def recent_scripts(self) -> list[str]:
        """The remembered recently-opened ``.py`` script paths, most-recent first (may be empty).

        Kept separate from :meth:`recent_files` (config YAMLs) so the scripting window's
        Editor **Open Recent** lists scripts and the main window's lists configs — two distinct
        recent lists, one persistence surface.
        """
        raw = self._settings.value(_KEY_RECENT_SCRIPTS, [])
        if raw is None:
            return []
        if isinstance(raw, str):  # a single value round-trips as a bare string
            return [raw]
        return [str(item) for item in raw]

    def add_recent_script(self, path: str) -> None:
        """Push *path* to the front of the recent-scripts list (deduped, capped)."""
        path = str(path)
        existing = [p for p in self.recent_scripts() if p != path]
        updated = [path, *existing][:_RECENT_LIMIT]
        self._settings.setValue(_KEY_RECENT_SCRIPTS, updated)

    def clear_recent_scripts(self) -> None:
        """Forget every remembered recent script."""
        self._settings.setValue(_KEY_RECENT_SCRIPTS, [])

    # -- theme --------------------------------------------------------------

    def theme_name(self) -> str | None:
        """The persisted theme name (``"LIGHT"`` / ``"DARK"``), or ``None`` if unset."""
        raw = self._settings.value(_KEY_THEME, None)
        return None if raw is None else str(raw)

    def set_theme_name(self, name: str) -> None:
        """Persist the chosen theme *name* (the View-menu toggle's choice)."""
        self._settings.setValue(_KEY_THEME, str(name))

    # -- display units (CU-326) ---------------------------------------------

    def angles_in_degrees(self) -> bool:
        """Whether angles display in degrees (owner-ruled shipped default: True)."""
        raw = self._settings.value(_KEY_ANGLES_DEG, True)
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("true", "1")

    def set_angles_in_degrees(self, enabled: bool) -> None:
        """Persist the angles-in-degrees display preference (View-menu toggle)."""
        self._settings.setValue(_KEY_ANGLES_DEG, bool(enabled))

    # -- sweep dialog (CU-325) ----------------------------------------------

    def last_sweep_spec(self) -> dict[str, Any] | None:
        """The persisted last-run sweep form contents, or ``None``.

        Display-side fields only (parameter names, typed range strings, flags) —
        never computed values. A corrupt entry reads as ``None`` rather than
        raising (the dialog then falls back to current-value seeding).
        """
        raw = self._settings.value(_KEY_SWEEP_SPEC, None)
        if raw is None:
            return None
        try:
            spec = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return None
        return spec if isinstance(spec, dict) else None

    def set_last_sweep_spec(self, spec: dict[str, Any]) -> None:
        """Persist the sweep form contents that just ran (Sarah's re-open loop)."""
        self._settings.setValue(_KEY_SWEEP_SPEC, json.dumps(spec))

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
