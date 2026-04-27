"""Phase 3/4 callback smoke test — call `update_scene` with defaults.

The callback function is plain Python; we invoke it directly with the same
positional input order Dash uses (`ALL_INPUT_IDS`). This avoids needing a
running Dash server while still exercising the full code path:
  raw UI values → SceneState → classify_regime → scene_builder.build_scene → go.Figure

Phase 4 expanded the callback's return value to a tuple of:
  (figure, regime_reason, readout_text, *target_slider_disabled, shape_dropdown_disabled)
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.basedatatypes import BaseTraceType

from dev_tools.geometry_gui.app.layout.angle_group_controls import (
    DEFAULT_ANGLE_GROUP_VALUES,
)
from dev_tools.geometry_gui.app.layout.mode_controls import (
    BACKGROUND_OPTIONS,
    REGIME_OPTIONS,
)
from dev_tools.geometry_gui.app.layout.observer_controls import OBSERVER_SLIDERS
from dev_tools.geometry_gui.app.layout.sensor_controls import SENSOR_SLIDERS
from dev_tools.geometry_gui.app.layout.sun_controls import SUN_SLIDERS
from dev_tools.geometry_gui.app.layout.target_controls import (
    SHAPE_OPTIONS,
    TARGET_SLIDERS,
)
from dev_tools.geometry_gui.app.main import (
    ALL_INPUT_IDS,
    ALL_OUTPUTS,
    update_scene,
)


def _default_inputs() -> list[float | str]:
    """Build the positional default-input list in `ALL_INPUT_IDS` order."""
    slider_defaults: dict[str, float] = {}
    for row in (*OBSERVER_SLIDERS, *TARGET_SLIDERS, *SUN_SLIDERS, *SENSOR_SLIDERS):
        component_id, *_, default = row
        slider_defaults[component_id] = default

    non_slider_defaults: dict[str, object] = {
        "tgt-shape": SHAPE_OPTIONS[0]["value"],
        "mode-regime": REGIME_OPTIONS[0]["value"],
        "mode-background": BACKGROUND_OPTIONS[0]["value"],
        "angle-groups": list(DEFAULT_ANGLE_GROUP_VALUES),
    }
    merged: dict[str, object] = {**slider_defaults, **non_slider_defaults}
    return [merged[component_id] for component_id in ALL_INPUT_IDS]


def _figure(out: tuple) -> go.Figure:
    """First element of the callback's tuple is the figure (per ALL_OUTPUTS)."""
    return out[0]


def test_callback_returns_figure_with_traces() -> None:
    out = update_scene(*_default_inputs())
    fig = _figure(out)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0, "expected at least one trace from build_scene"


def test_callback_traces_are_plotly_types() -> None:
    """Every returned trace should be a real plotly trace."""
    fig = _figure(update_scene(*_default_inputs()))
    for trace in fig.data:
        assert isinstance(trace, BaseTraceType), (
            f"trace {type(trace).__name__} is not a plotly trace"
        )


def test_callback_changes_with_shape_dropdown() -> None:
    """Switching the target shape produces a different vertex count in the scene."""
    base_inputs = _default_inputs()
    sphere_fig = _figure(update_scene(*base_inputs))

    box_inputs = list(base_inputs)
    box_inputs[ALL_INPUT_IDS.index("tgt-shape")] = "box"
    box_fig = _figure(update_scene(*box_inputs))

    def _vertex_count(fig: go.Figure) -> int:
        total = 0
        for trace in fig.data:
            xs = getattr(trace, "x", None)
            if xs is not None:
                total += len(xs)
        return total

    assert _vertex_count(sphere_fig) != _vertex_count(box_fig), (
        "sphere vs box should produce different vertex counts in the scene"
    )


def test_callback_input_count_matches_layout() -> None:
    """ALL_INPUT_IDS lists 19 sliders + 4 non-slider controls (Phase 10:
    angle-groups checklist added)."""
    assert len(ALL_INPUT_IDS) == 23


def test_callback_output_arity_matches_outputs_table() -> None:
    """update_scene returns one element per Output declared in ALL_OUTPUTS."""
    out = update_scene(*_default_inputs())
    assert len(out) == len(ALL_OUTPUTS)


def test_callback_default_state_is_sub_pixel_with_reason() -> None:
    """Default state classifies as SUB_PIXEL via the in-between branch."""
    out = update_scene(*_default_inputs())
    reason = out[1]
    assert "0.25*ifov" in reason and "ang_ext" in reason


def test_callback_extended_override_disables_shape_dropdown() -> None:
    """Forcing regime=extended via the radio greys out the shape dropdown."""
    inputs = list(_default_inputs())
    inputs[ALL_INPUT_IDS.index("mode-regime")] = "extended"
    out = update_scene(*inputs)
    # Last entry is shape-dropdown disabled — see ALL_OUTPUTS in main.py.
    assert out[-1] is True


def test_callback_sphere_disables_orientation_sliders() -> None:
    """Default sphere case: yaw/pitch/roll are inert (disabled)."""
    out = update_scene(*_default_inputs())
    # Map disabled tail to slider IDs via ALL_OUTPUTS metadata.
    disabled_pairs = [
        (cid, val) for (cid, prop), val in zip(ALL_OUTPUTS[3:], out[3:]) if prop == "disabled"
    ]
    disabled = {cid: val for cid, val in disabled_pairs}
    for axis in ("tgt-yaw", "tgt-pitch", "tgt-roll"):
        assert disabled[axis] is True


def test_callback_rejects_wrong_arity() -> None:
    import pytest

    with pytest.raises(ValueError, match="expected"):
        update_scene(1.0, 2.0)
