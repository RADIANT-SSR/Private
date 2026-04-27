"""Assembles every control group + publishes the canonical slider input order.

`SLIDER_INPUTS` is the authoritative ordered list of `(component_id, prop)`
pairs that the Dash callback consumes. Keeping it here means a single source
of truth — the callback in `main.py` and the test in `test_layout.py` both
read this constant.
"""

from __future__ import annotations

from typing import Final

from dash import html

from dev_tools.geometry_gui.app.layout.angle_group_controls import (
    angle_group_controls,
)
from dev_tools.geometry_gui.app.layout.mode_controls import mode_controls
from dev_tools.geometry_gui.app.layout.observer_controls import (
    OBSERVER_SLIDERS,
    observer_controls,
)
from dev_tools.geometry_gui.app.layout.sensor_controls import (
    SENSOR_SLIDERS,
    sensor_controls,
)
from dev_tools.geometry_gui.app.layout.sun_controls import SUN_SLIDERS, sun_controls
from dev_tools.geometry_gui.app.layout.target_controls import (
    TARGET_SLIDERS,
    target_controls,
)

# Ordered slider IDs — must match the callback's positional argument order.
SLIDER_INPUTS: Final[tuple[str, ...]] = (
    *(row[0] for row in OBSERVER_SLIDERS),
    *(row[0] for row in TARGET_SLIDERS),
    *(row[0] for row in SUN_SLIDERS),
    *(row[0] for row in SENSOR_SLIDERS),
)

# Non-slider inputs that also feed the callback (dropdown + 2 radios + checklist).
NON_SLIDER_INPUTS: Final[tuple[str, ...]] = (
    "tgt-shape",
    "mode-regime",
    "mode-background",
    "angle-groups",
)


def controls_panel() -> html.Div:
    return html.Div(
        [
            observer_controls(),
            target_controls(),
            sensor_controls(),
            sun_controls(),
            mode_controls(),
            angle_group_controls(),
        ],
        style={
            "width": "32%",
            "padding": "12px",
            "boxSizing": "border-box",
            "overflowY": "auto",
            "maxHeight": "92vh",
        },
    )
