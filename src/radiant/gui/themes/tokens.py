"""The single owner of every RADIANT GUI visual token.

This module is the *one* home for every colour, font, spacing, and radius value
in the GUI (GUI plan §4.9, review-blocking): **no other file under
``radiant.gui`` may contain a colour, font-family, or size literal.** A mechanical
discipline test (``tests/test_theme.py::test_no_style_literals_outside_themes``)
enforces that rule for every later phase.

The values below are pulled verbatim from ``RADIANT_GUI_Architecture.md`` §8, which
in turn distilled them from the mockup CSS
(``dev_tools/gui_mockups/radiant_ui/radiant_mid_fi.html`` ``:root`` light block and
``body.dark`` override). The **light** :data:`LIGHT` set is the v1 launch default
(Phase 0 checkpoint amendment 1, 2026-07-12); the **dark** :data:`DARK` set is the
alternate. Both share the same token *names* so the QSS generator
(:func:`~radiant.gui.themes.stylesheet.build_stylesheet`) maps one template over either
set, and the Phase 9 View-menu toggle swaps them by re-applying a different :class:`Theme`.

Typography note (font availability): IBM Plex Sans / IBM Plex Mono are the design
target (§8.2) but are **not** bundled and may be absent on the host (they are on this
build machine). The font stacks below therefore lead with IBM Plex and fall back to
the platform UI font / Menlo so the app renders correctly everywhere; bundling the OFL
font files is a later decision (see the Phase 1 checkpoint punch-list / CU-103).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Theme:
    """A complete, immutable colour token set (one of light or dark).

    Field names mirror the CSS-var names in the mockup (``bg``, ``panel``,
    ``panel_2`` for ``--panel-2``, …) so the QSS generator and the arch-doc §8
    table line up 1:1. Two instances ship: :data:`LIGHT` and :data:`DARK`.

    The five ``syntax_*`` fields are the embedded-console highlight roles
    (§8.1, ``radiant_scripting.html``); they are per-theme like everything else.
    """

    name: str

    # Surfaces (§8.1)
    bg: str
    panel: str
    panel_2: str
    panel_3: str
    panel_4: str

    # Borders
    line: str
    line_2: str

    # Text
    ink: str
    ink_2: str
    muted: str
    muted_2: str

    # Accent
    accent: str
    accent_soft: str

    # Health / status
    ok: str
    ok_soft: str
    warn: str
    warn_soft: str
    err: str
    err_soft: str
    stale: str
    stale_soft: str
    focus: str
    focus_soft: str

    # Console syntax-highlight roles (§8.1)
    syntax_keyword: str
    syntax_string: str
    syntax_number: str
    syntax_function: str
    syntax_comment: str


# -- Light theme — v1 launch default (§8.1 light block) --------------------------
LIGHT = Theme(
    name="light",
    bg="#ebeef2",
    panel="#fafbfc",
    panel_2="#f1f3f6",
    panel_3="#e6e9ee",
    # panel-4 (deepest inset / console) is not in the §8.1 light list; the mockup
    # console reuses panel-3 as its deepest surface in light mode. Kept explicit
    # so the token exists in both themes.
    panel_4="#dfe3ea",
    line="#cfd5de",
    line_2="#b7bfcb",
    ink="#1b2230",
    ink_2="#384050",
    muted="#6b7380",
    muted_2="#8a93a1",
    accent="#b8431a",
    accent_soft="#f6e2d6",
    ok="#2f7a3a",
    ok_soft="#dcebdd",
    warn="#a97c14",
    warn_soft="#f5ebcf",
    err="#a8302a",
    err_soft="#f3dbd7",
    stale="#9aa3b0",
    stale_soft="#e6e9ee",
    focus="#2f5aa8",
    focus_soft="#dde6f4",
    syntax_keyword="#8a2a8e",
    syntax_string="#2f6b3a",
    syntax_number="#a04018",
    syntax_function="#2a5abf",
    syntax_comment="#8a93a1",
)


# -- Dark theme — alternate (§8.1 dark block) -----------------------------------
DARK = Theme(
    name="dark",
    bg="#0f1216",
    panel="#171a21",
    panel_2="#1d2029",
    panel_3="#262a35",
    panel_4="#323744",
    line="#2b3140",
    line_2="#3a4254",
    ink="#e6e9ef",
    ink_2="#c3c9d4",
    muted="#8b94a4",
    muted_2="#6e7685",
    accent="#e08157",
    accent_soft="#3a2218",
    ok="#7fb987",
    ok_soft="#1f2f22",
    warn="#e0b249",
    warn_soft="#3a2f16",
    err="#e07874",
    err_soft="#3a1e1c",
    stale="#666b77",
    stale_soft="#242832",
    focus="#86a8df",
    focus_soft="#1e2a3e",
    syntax_keyword="#d69fd8",
    syntax_string="#97c49e",
    syntax_number="#e0a075",
    syntax_function="#9bb8e3",
    syntax_comment="#6a7385",
)


# -- Window traffic-light dots (§8.1: raw hex, macOS chrome, *not* themed) -------
# These are the window-decoration dots only; stage *health* dots use the themed
# ok/warn/err/stale tokens above. Exposed as named constants so even these raw
# values live here, not in a widget file.
WINDOW_DOT_RED = "#ec6a5e"
WINDOW_DOT_YELLOW = "#f4bf4f"
WINDOW_DOT_GREEN = "#61c555"


# -- Typography (§8.2) ----------------------------------------------------------
# Font *stacks* (theme-independent). IBM Plex leads; the remainder are graceful
# fallbacks for hosts without it (see module docstring / CU-103).
FONT_SANS = '"IBM Plex Sans", "Helvetica Neue", "Segoe UI", "Cantarell", sans-serif'
FONT_MONO = '"IBM Plex Mono", "Menlo", "Consolas", "DejaVu Sans Mono", monospace'

FONT_SIZE_BASE_PT = 13  # base UI text, §8.2 (px in CSS; pt in Qt — 1:1 at 96 dpi)

# Named type roles (family, size in px, weight) — §8.2 table. Sizes are strings so
# the QSS generator drops them straight in with a "px" suffix.
TYPE_APP_TITLE = (FONT_SANS, "18px", 600)
TYPE_PANEL_TITLE = (FONT_SANS, "12.5px", 600)
TYPE_STAGE_EYEBROW = (FONT_SANS, "10.5px", 500)
TYPE_STAGE_TITLE = (FONT_SANS, "14px", 600)
TYPE_KPI_LABEL = (FONT_SANS, "10.5px", 500)
TYPE_KPI_VALUE = (FONT_MONO, "17px", 600)
TYPE_KPI_UNIT = (FONT_SANS, "11px", 400)
TYPE_CAPTION = (FONT_SANS, "11px", 400)


# -- Spacing, radius, borders (§8.3) --------------------------------------------
RADIUS_PANEL = "8px"  # cards / panels 8–9 px
RADIUS_CONTROL = "5px"  # buttons & inputs 4–5 px
RADIUS_CHIP = "3px"  # chips / kbd / badges 2–3 px
RADIUS_PILL = "9px"  # pill badges

PAD_PANEL = "12px 14px"  # panels / strip
PAD_BUTTON = "6px 14px"  # buttons
PAD_INPUT = "5px 8px"  # inputs
PAD_KPI = "4px 14px"  # KPI cells
PAD_STAGE = "10px 12px"  # stage buttons
# In-cell tree/table editors (the delegate spawns these over a short row): the
# 5px vertical of PAD_INPUT clips the glyphs to illegible slivers in a ~20px row
# (Phase 2 checkpoint bug, 2026-07-12). Near-zero vertical padding keeps the
# digits fully visible; the 6px horizontal keeps the text off the cell border.
PAD_CELL_EDITOR = "1px 6px"

GAP_DEFAULT = "6px"  # default inter-control gap
BORDER_WIDTH = "1px"  # 1 px solid line everywhere


__all__ = [
    "Theme",
    "LIGHT",
    "DARK",
    "WINDOW_DOT_RED",
    "WINDOW_DOT_YELLOW",
    "WINDOW_DOT_GREEN",
    "FONT_SANS",
    "FONT_MONO",
    "FONT_SIZE_BASE_PT",
    "TYPE_APP_TITLE",
    "TYPE_PANEL_TITLE",
    "TYPE_STAGE_EYEBROW",
    "TYPE_STAGE_TITLE",
    "TYPE_KPI_LABEL",
    "TYPE_KPI_VALUE",
    "TYPE_KPI_UNIT",
    "TYPE_CAPTION",
    "RADIUS_PANEL",
    "RADIUS_CONTROL",
    "RADIUS_CHIP",
    "RADIUS_PILL",
    "PAD_PANEL",
    "PAD_BUTTON",
    "PAD_INPUT",
    "PAD_KPI",
    "PAD_STAGE",
    "PAD_CELL_EDITOR",
    "GAP_DEFAULT",
    "BORDER_WIDTH",
]
