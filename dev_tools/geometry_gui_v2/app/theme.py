"""qt-material theme registry + applicator.

Phase 6 (PLAN_v2.md §14 step 1): the desktop window opens in
``dark_teal.xml`` by default; the Settings dialog lets the user switch to
``light_blue.xml`` or follow OS appearance.

This module owns the list of supported themes and the single call site
that hands a stylesheet to ``QApplication``. Keeping it small means a
future Phase-6 refresh that swaps qt-material for a different stylesheet
provider only touches this file.

Rule 19: own file. Theme application is its own concern, distinct from
window construction (``main.py``) and from settings persistence
(``window_persistence.py``).
"""

from __future__ import annotations

from typing import Final

# The two themes the Phase-6 spec calls out by name. The full qt-material
# catalog is ~25 themes; the GUI only exposes these two plus "system"
# (uses the OS native style by *not* applying a stylesheet).
DEFAULT_DARK_THEME: Final[str] = "dark_teal.xml"
DEFAULT_LIGHT_THEME: Final[str] = "light_blue.xml"
SYSTEM_THEME_KEY: Final[str] = "system"

# Display name → stylesheet xml file (or ``SYSTEM_THEME_KEY``).
SUPPORTED_THEMES: Final[dict[str, str]] = {
    "Dark (teal)": DEFAULT_DARK_THEME,
    "Light (blue)": DEFAULT_LIGHT_THEME,
    "Follow OS": SYSTEM_THEME_KEY,
}


def apply_theme(app, theme_xml: str) -> None:  # type: ignore[no-untyped-def]
    """Apply ``theme_xml`` (qt-material stylesheet name) to ``app``.

    ``theme_xml == SYSTEM_THEME_KEY`` clears any prior stylesheet so the
    OS native style takes over. Unknown theme names raise ``ValueError``
    so a corrupted ``QSettings`` value surfaces immediately.
    """
    if theme_xml == SYSTEM_THEME_KEY:
        app.setStyleSheet("")
        return
    if theme_xml not in SUPPORTED_THEMES.values():
        raise ValueError(
            f"apply_theme: unknown theme {theme_xml!r}. "
            f"Expected one of: {sorted(SUPPORTED_THEMES.values())}."
        )
    # qt_material must be imported after Qt — that's why this happens here
    # at call time, not at module import.
    from qt_material import apply_stylesheet

    apply_stylesheet(app, theme=theme_xml)
