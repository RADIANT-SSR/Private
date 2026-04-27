"""Target slider group — shape selector + size sliders + body attitude + fill fraction."""

from __future__ import annotations

from typing import Final

from dash import dcc, html

# (component_id, label, ui_units, min, max, step, default_ui_value)
TARGET_SLIDERS: Final[list[tuple[str, str, str, float, float, float, float]]] = [
    ("tgt-altitude", "Altitude", "km", 0.0, 5.0, 0.1, 0.0),
    ("tgt-radius", "Radius", "m", 0.01, 100.0, 0.1, 1.0),
    ("tgt-length", "Length", "m", 0.01, 100.0, 0.1, 2.0),
    ("tgt-width", "Width", "m", 0.01, 100.0, 0.1, 1.0),
    ("tgt-height", "Height", "m", 0.01, 100.0, 0.1, 1.0),
    ("tgt-base-radius", "Base radius (cone)", "m", 0.01, 100.0, 0.1, 1.0),
    ("tgt-yaw", "Yaw", "deg", -180.0, 180.0, 1.0, 0.0),
    ("tgt-pitch", "Pitch", "deg", -180.0, 180.0, 1.0, 0.0),
    ("tgt-roll", "Roll", "deg", -180.0, 180.0, 1.0, 0.0),
    ("tgt-fill-fraction", "Fill fraction", "—", 0.001, 1.0, 0.001, 1.0),
]

SHAPE_OPTIONS: Final[list[dict[str, str]]] = [
    {"label": "Sphere", "value": "sphere"},
    {"label": "Cylinder", "value": "cylinder"},
    {"label": "Flat plate", "value": "flat_plate"},
    {"label": "Box", "value": "box"},
    {"label": "Cone", "value": "cone"},
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


def target_controls() -> html.Div:
    return html.Div(
        [
            html.H4("Target"),
            html.Label("Shape", htmlFor="tgt-shape"),
            dcc.Dropdown(
                id="tgt-shape",
                options=SHAPE_OPTIONS,
                value="sphere",
                clearable=False,
                style={"marginBottom": "8px"},
            ),
            *[_slider_row(*row) for row in TARGET_SLIDERS],
        ],
        style={"marginBottom": "16px"},
    )
