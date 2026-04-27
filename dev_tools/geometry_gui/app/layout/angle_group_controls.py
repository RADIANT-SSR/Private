"""Angle-group checklist — multi-select toggle for which annotations render.

Phase 10 (PLAN.md §11). Six independent toggles, any combination legal,
empty selection legal (yields the bare-geometry view). Defaults to
`observer + target + background`. The selected set is wired into the
single Dash callback as one new Input and passed to
`build_scene(state, *, angle_groups=...)`.

Rule 19: own file. The Checklist's `value` is consumed verbatim by the
callback to construct a `frozenset[str]`.
"""

from __future__ import annotations

from typing import Final

from dash import dcc, html

ANGLE_GROUP_OPTIONS: Final[list[dict[str, str]]] = [
    {"label": "Observer (off-nadir, az, el, nadir)", "value": "observer"},
    {"label": "Target (α_t, s_t)", "value": "target"},
    {"label": "Background (n_B, s_B, θ_sun,B)", "value": "background"},
    {"label": "Sun (θ_s, Δφ)", "value": "sun"},
    {"label": "World axes (X/Y/Z triad)", "value": "world_axes"},
    {"label": "Projections (planar shadows)", "value": "projections"},
]

DEFAULT_ANGLE_GROUP_VALUES: Final[list[str]] = ["observer", "target", "background"]

# Phase 11(f): caption shown beneath the checklist when no group is
# selected. The empty-scene view is deliberate — this caption tells the
# developer that the absence of arcs is by design rather than a callback
# error.
EMPTY_SELECTION_CAPTION: Final[str] = "(no annotations selected — bare geometry)"


def angle_group_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Angle groups"),
            dcc.Checklist(
                id="angle-groups",
                options=ANGLE_GROUP_OPTIONS,
                value=DEFAULT_ANGLE_GROUP_VALUES,
                inputStyle={"marginRight": "6px"},
                labelStyle={"display": "block", "marginBottom": "2px"},
            ),
            html.Div(
                id="angle-groups-empty-caption",
                children="",
                style={
                    "fontFamily": "monospace",
                    "fontSize": "11px",
                    "color": "#666",
                    "fontStyle": "italic",
                    "marginTop": "4px",
                },
            ),
        ],
        style={"marginBottom": "16px"},
    )
