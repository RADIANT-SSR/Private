"""Mode toggles — regime override (radio) and background kind (radio).

Phase 4 also wires a live "reason" string under the regime radio. The reason
is computed by `view_model.classify_regime` and pushed by the single Dash
callback in `main.py`. The id `mode-regime-reason` is the canonical handle.
"""

from __future__ import annotations

from typing import Final

from dash import dcc, html

REGIME_OPTIONS: Final[list[dict[str, str]]] = [
    {"label": "auto", "value": "auto"},
    {"label": "extended", "value": "extended"},
    {"label": "sub-pixel", "value": "sub_pixel"},
    {"label": "point source", "value": "point_source"},
]

BACKGROUND_OPTIONS: Final[list[dict[str, str]]] = [
    {"label": "none", "value": "none"},
    {"label": "cold space", "value": "cold_space"},
    {"label": "ground", "value": "ground"},
    {"label": "at-aperture", "value": "at_aperture"},
]


def mode_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Mode"),
            html.Label("Regime override"),
            dcc.RadioItems(
                id="mode-regime",
                options=REGIME_OPTIONS,
                value="auto",
                inline=True,
            ),
            html.Div(
                id="mode-regime-reason",
                children="(reason will appear here once the callback fires)",
                style={
                    "fontSize": "12px",
                    "fontStyle": "italic",
                    "color": "#444",
                    "marginTop": "4px",
                    "marginBottom": "8px",
                },
            ),
            html.Label("Background"),
            dcc.RadioItems(
                id="mode-background",
                options=BACKGROUND_OPTIONS,
                value="none",
                inline=True,
            ),
        ],
        style={"marginBottom": "16px"},
    )
