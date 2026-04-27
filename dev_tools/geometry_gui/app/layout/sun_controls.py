"""Sun slider group — solar zenith (theta_s) and relative azimuth (delta_phi)."""

from __future__ import annotations

from typing import Final

from dash import dcc, html

SUN_SLIDERS: Final[list[tuple[str, str, str, float, float, float, float]]] = [
    ("sun-zenith", "Solar zenith θ_s", "deg", 0.0, 180.0, 1.0, 35.0),
    ("sun-azimuth", "Relative azimuth Δφ", "deg", -180.0, 180.0, 1.0, 12.0),
]


def _slider_row(
    component_id: str,
    label: str,
    units: str,
    minv: float,
    maxv: float,
    step: float,
    default: float,
) -> html.Div:
    return html.Div(
        [
            html.Label(f"{label} [{units}]", htmlFor=component_id),
            dcc.Slider(
                id=component_id,
                min=minv,
                max=maxv,
                step=step,
                value=default,
                marks={minv: f"{minv:g}", maxv: f"{maxv:g}"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
        style={"marginBottom": "8px"},
    )


def sun_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Sun"),
            *[_slider_row(*row) for row in SUN_SLIDERS],
        ],
        style={"marginBottom": "16px"},
    )
