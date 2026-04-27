"""Readout panel — labeled lines for every value in PLAN.md §7.

Phase 5 makes every line live: numeric rows are populated from
`view_model.format_readout(state, regime, reason)` (which itself calls
`derived_readout(state)`), and a per-shape facet-decomposition explainer
appears below the panel.

Hard rule (CLAUDE.md / user memory): every numeric value carries explicit
units. The unit text is part of the formatted string returned by
`format_readout`, never glued on at render time.
"""

from __future__ import annotations

from typing import Final

from dash import html

# Component ID → human label, in display order.
READOUT_LINES: tuple[tuple[str, str], ...] = (
    ("ro-slant-range", "Slant range"),
    ("ro-ground-range", "Ground range"),
    ("ro-gsd", "GSD"),
    ("ro-ifov", "IFOV"),
    ("ro-angular-extent", "Angular extent"),
    ("ro-fill-fraction", "Fill fraction (computed)"),
    ("ro-pixel-area", "Pixel area on ground"),
    ("ro-projected-area", "Projected area A_t"),
    ("ro-regime", "Regime"),
    ("ro-regime-reason", "Reason"),
    ("ro-view-azimuth", "View azimuth az"),
    ("ro-view-elevation", "View elevation el"),
    ("ro-solar-zenith", "Solar zenith theta_s"),
    ("ro-relative-azimuth", "Relative azimuth dphi"),
)

LABEL_WIDTH: Final[int] = 24

DEFAULT_TEXT: Final[str] = "\n".join(
    f"{label:<{LABEL_WIDTH}}: —" for _, label in READOUT_LINES
)

DEFAULT_EXPLAINER: Final[str] = "Facet decomposition: (waiting for first callback)"

# Phase 8 redesign (PLAN.md §11, constraint C7): the rendered scene uses
# illustrative distances so the target is visible. Angles are physical and
# exact — read the off-nadir, phase, solar-zenith arcs straight from the
# figure; read the slant range / ground range / GSD from the readout above.
SCENE_NOTE: Final[str] = (
    "Distances illustrative; angles physical "
    "(observer/sun glyphs at fixed display distances, see PLAN.md C7)"
)


def render_text(values: dict[str, str] | None = None) -> str:
    """Render the readout block.

    Each row is `"{label:<LABEL_WIDTH}: {value}"`. Missing keys render as
    "—" so the panel still draws if the callback hasn't fired yet.
    """
    live = values or {}
    return "\n".join(
        f"{label:<{LABEL_WIDTH}}: {live.get(component_id, '—')}"
        for component_id, label in READOUT_LINES
    )


def readout_panel() -> html.Div:
    return html.Div(
        [
            html.H4("Readout"),
            html.Pre(
                id="readout-text",
                children=DEFAULT_TEXT,
                style={
                    "fontFamily": "monospace",
                    "fontSize": "13px",
                    "padding": "8px",
                    "background": "#f4f4f4",
                    "border": "1px solid #ccc",
                    "marginTop": "8px",
                },
            ),
            html.Div(
                id="readout-explainer",
                children=DEFAULT_EXPLAINER,
                style={
                    "fontFamily": "monospace",
                    "fontSize": "12px",
                    "color": "#444",
                    "padding": "4px 8px",
                    "marginTop": "4px",
                },
            ),
            html.Div(
                children=SCENE_NOTE,
                style={
                    "fontFamily": "monospace",
                    "fontSize": "11px",
                    "color": "#666",
                    "fontStyle": "italic",
                    "padding": "4px 8px",
                },
            ),
        ]
    )
