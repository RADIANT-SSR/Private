"""Sensor slider group — focal length (m) and pixel pitch (µm)."""

from __future__ import annotations

from typing import Final

from dash import dcc, html

SENSOR_SLIDERS: Final[list[tuple[str, str, str, float, float, float, float]]] = [
    ("sen-focal", "Focal length", "m", 0.1, 10.0, 0.1, 1.0),
    ("sen-pixel-pitch", "Pixel pitch", "µm", 1.0, 50.0, 0.5, 10.0),
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


def sensor_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Sensor"),
            *[_slider_row(*row) for row in SENSOR_SLIDERS],
        ],
        style={"marginBottom": "16px"},
    )
