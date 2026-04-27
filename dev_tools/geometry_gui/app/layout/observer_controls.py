"""Observer slider group — altitude (km), look angle (deg), yaw/pitch/roll (deg)."""

from __future__ import annotations

from typing import Final

from dash import dcc, html

# (component_id, label, ui_units, min, max, step, default_ui_value)
OBSERVER_SLIDERS: Final[list[tuple[str, str, str, float, float, float, float]]] = [
    ("obs-altitude", "Altitude", "km", 100.0, 36_000.0, 50.0, 600.0),
    ("obs-look-angle", "Look angle (off-nadir)", "deg", 0.0, 60.0, 0.5, 20.0),
    ("obs-yaw", "Yaw", "deg", -30.0, 30.0, 0.5, 0.0),
    ("obs-pitch", "Pitch", "deg", -30.0, 30.0, 0.5, 0.0),
    ("obs-roll", "Roll", "deg", -30.0, 30.0, 0.5, 0.0),
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
                marks={
                    minv: f"{minv:g}",
                    maxv: f"{maxv:g}",
                },
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
        style={"marginBottom": "8px"},
    )


def observer_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Observer"),
            *[_slider_row(*row) for row in OBSERVER_SLIDERS],
        ],
        style={"marginBottom": "16px"},
    )
