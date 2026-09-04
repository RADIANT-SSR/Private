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

    # Per-configuration accents (§8.1, multi-configuration Phase 4a). One stable
    # colour per configuration slot, indexed by position in the configuration set
    # (``ConfigurationSet.MAX_CONFIGS`` = 12, so exactly twelve entries). The same
    # index always yields the same hue in both themes, so a configuration keeps
    # its identity across a light/dark toggle. Used by the master configuration
    # selector, and (Phase 4d) the per-configuration Performance columns.
    config_accents: tuple[str, ...]


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
    # Twelve configuration accents — saturated mid-darks that read against the
    # light panel surfaces. A chip is drawn on a ``configurationTab``, whose
    # background cycles ``panel`` / ``panel_3`` (hover) / ``focus_soft``
    # (checked); the worst of those four states is the contrast that matters,
    # and every accent below holds >= 3:1 non-text contrast across all of them
    # (the tightest is the pre-existing amber at 2.99:1). Index 0 is the first
    # configuration in set order.
    #
    # Indices 0–7 are the original eight and are **frozen**: saved studies and
    # walkthrough figures already read a configuration's identity off its slot
    # colour, so a re-hue would silently re-colour existing work. Indices 8–11
    # were added when ``MAX_CONFIGS`` went 8 → 12 (owner-ratified 2026-09-01),
    # and were placed in the four widest gaps of the existing hue circle —
    # indigo 252° (between blue 219° and purple 286°), olive 82° (between amber
    # 42° and green 129°), magenta 310° (between purple 286° and pink 339°), and
    # emerald 158° (between green 129° and teal 180°).
    #
    # Hue spacing alone does not survive a red-green confusion, which collapses
    # the warm and the green families onto one yellow axis, so each new hue also
    # carries a **lightness** offset from both of its hue neighbours — the second
    # channel that stays legible under deuteranopia and protanopia: olive L 0.26
    # sits below green 0.33 and amber 0.37; emerald L 0.36 above green 0.33 and
    # teal 0.30; indigo L 0.32 below blue 0.42 and purple 0.39; magenta L 0.32
    # below purple 0.39 and pink 0.42. Emerald is the tightest of the four — its
    # lightness margin over green is only 0.03, so it leans on the 29°/22° hue
    # separation from green/teal, which is the one pair a red-green confusion
    # partially preserves (both read as desaturated cyan-greys of different
    # value, not as two yellows).
    config_accents=(
        "#2f5aa8",
        "#b8431a",
        "#2f7a3a",
        "#7a3a8e",
        "#a97c14",
        "#1f7a7a",
        "#a8305a",
        "#5a6270",
        "#39297a",
        "#4c671e",
        "#812271",
        "#298e69",
    ),
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
    # The same twelve hues lightened for the dark surfaces — index-for-index the
    # light set (same hue angle, lightness raised ~0.28 and saturation eased), so
    # a configuration's colour identity survives a theme toggle. Indices 8–11 are
    # the 8 → 12 extension and follow the light set's ordering within each hue
    # family, so the CVD lightness channel described there reads the same way
    # here: olive L 0.50 below green 0.61 and amber 0.58; emerald L 0.68 above
    # green 0.61 and teal 0.59; indigo L 0.64 below blue 0.70 and purple 0.73;
    # magenta L 0.62 below purple 0.73 and pink 0.69. Every chip clears 3:1
    # across all four ``configurationTab`` background states (``panel`` /
    # ``panel_3`` / ``focus_soft``); the tightest of the twelve is indigo at
    # 3.82:1.
    config_accents=(
        "#86a8df",
        "#e08157",
        "#7fb987",
        "#c79ad8",
        "#e0b249",
        "#6fc0c0",
        "#e07fa4",
        "#a8b0be",
        "#8977cf",
        "#8eb54a",
        "#cf6ebe",
        "#89d2b7",
    ),
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
