"""Phase 3/4: full Dash app — controls panel, 3D figure, readout panel.

Single callback (`update_scene`) re-builds a `SceneState` from every UI input
on each fire, classifies the regime, and produces:

  * the 3D plotly Figure
  * a live "regime reason" string under the regime radio
  * a refreshed readout-panel text (regime + reason rows are live;
    Phase 5 will populate the numeric rows)
  * `disabled` props for shape-relevant size sliders, orientation sliders
    (sphere makes them inert), and the shape dropdown (extended regime).

There is no module-level mutable state — `SceneState` is the sole carrier
of GUI configuration (PLAN.md §4).

UI → canonical unit conversion happens here and only here:
  * altitudes:  km   → m
  * angles:     deg  → rad
  * pixel pitch: µm  → m
"""

from __future__ import annotations

import math
from typing import Final

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.layout import (
    SLIDER_INPUTS,
    controls_panel,
    readout_panel,
)
from dev_tools.geometry_gui.app.layout.angle_group_controls import (
    EMPTY_SELECTION_CAPTION,
)
from dev_tools.geometry_gui.app.layout.controls_panel import NON_SLIDER_INPUTS
from dev_tools.geometry_gui.app.layout.readout_panel import render_text
from dev_tools.geometry_gui.app.scene_builder._camera_frame import (
    camera_eye_from_traces,
)
from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.state import SceneState, ShapeKind
from dev_tools.geometry_gui.app.view_model import (
    classify_regime,
    compute_view_direction_scene,
    derived_readout,
    format_readout,
    multi_facet_explainer,
    projected_area_m2,
)

# Total positional inputs the callback receives, in this exact order.
ALL_INPUT_IDS: Final[tuple[str, ...]] = (*SLIDER_INPUTS, *NON_SLIDER_INPUTS)

# Sliders whose `disabled` state varies with shape and regime (8 total).
# `tgt-altitude` and `tgt-fill-fraction` are always enabled.
TARGET_DISABLE_IDS: Final[tuple[str, ...]] = (
    "tgt-radius",
    "tgt-length",
    "tgt-width",
    "tgt-height",
    "tgt-base-radius",
    "tgt-yaw",
    "tgt-pitch",
    "tgt-roll",
)

SIZE_SLIDERS: Final[frozenset[str]] = frozenset(
    {"tgt-radius", "tgt-length", "tgt-width", "tgt-height", "tgt-base-radius"}
)
ORIENTATION_SLIDERS: Final[frozenset[str]] = frozenset(
    {"tgt-yaw", "tgt-pitch", "tgt-roll"}
)

# Shape → relevant size-slider IDs (Phase 4 prompt §"Per-shape relevant size sliders").
SHAPE_RELEVANT_SIZES: Final[dict[ShapeKind, frozenset[str]]] = {
    "sphere": frozenset({"tgt-radius"}),
    "cylinder": frozenset({"tgt-radius", "tgt-length"}),
    "flat_plate": frozenset({"tgt-length", "tgt-width"}),
    "box": frozenset({"tgt-length", "tgt-width", "tgt-height"}),
    "cone": frozenset({"tgt-base-radius", "tgt-height"}),
}


def _state_from_inputs(values: dict[str, float | str]) -> SceneState:
    """Reconstruct a `SceneState` from raw UI values (display units)."""
    return SceneState(
        observer_altitude_m=float(values["obs-altitude"]) * 1_000.0,
        observer_look_angle_rad=math.radians(float(values["obs-look-angle"])),
        observer_yaw_rad=math.radians(float(values["obs-yaw"])),
        observer_pitch_rad=math.radians(float(values["obs-pitch"])),
        observer_roll_rad=math.radians(float(values["obs-roll"])),
        target_altitude_m=float(values["tgt-altitude"]) * 1_000.0,
        target_shape=values["tgt-shape"],  # type: ignore[arg-type]
        target_radius_m=float(values["tgt-radius"]),
        target_length_m=float(values["tgt-length"]),
        target_width_m=float(values["tgt-width"]),
        target_height_m=float(values["tgt-height"]),
        target_base_radius_m=float(values["tgt-base-radius"]),
        target_yaw_rad=math.radians(float(values["tgt-yaw"])),
        target_pitch_rad=math.radians(float(values["tgt-pitch"])),
        target_roll_rad=math.radians(float(values["tgt-roll"])),
        target_fill_fraction=float(values["tgt-fill-fraction"]),
        focal_length_m=float(values["sen-focal"]),
        pixel_pitch_m=float(values["sen-pixel-pitch"]) * 1e-6,
        solar_zenith_rad=math.radians(float(values["sun-zenith"])),
        relative_azimuth_rad=math.radians(float(values["sun-azimuth"])),
        regime_override=values["mode-regime"],  # type: ignore[arg-type]
        background_kind=values["mode-background"],  # type: ignore[arg-type]
    )


def slider_disabled(
    slider_id: str, regime: RadiometricRegime, shape: ShapeKind
) -> bool:
    """Decide whether `slider_id` should be greyed out for the current state.

    Rules (Phase 4 prompt):
      * In EXTENDED or POINT_SOURCE regimes, no shape-related slider matters
        — disable every size and orientation slider.
      * In SUB_PIXEL (or any non-extended/point-source state), size sliders
        are enabled only when relevant to the chosen shape; orientation
        sliders are inert for spheres (projected area is orientation-invariant).
    """
    if regime in (RadiometricRegime.EXTENDED, RadiometricRegime.POINT_SOURCE):
        if slider_id in SIZE_SLIDERS or slider_id in ORIENTATION_SLIDERS:
            return True
        return False
    if slider_id in SIZE_SLIDERS:
        return slider_id not in SHAPE_RELEVANT_SIZES[shape]
    if slider_id in ORIENTATION_SLIDERS:
        return shape == "sphere"
    return False


def shape_dropdown_disabled(regime: RadiometricRegime) -> bool:
    """Phase-4 spec: shape dropdown is greyed only in EXTENDED regime."""
    return regime == RadiometricRegime.EXTENDED


def _figure_from_state(
    state: SceneState,
    regime: RadiometricRegime,
    gsd_m: float,
    angle_groups: frozenset[str],
) -> go.Figure:
    """Build the plotly figure from a `SceneState` and classified regime.

    In SUB_PIXEL / default the silhouette disk (Phase 5) is added by passing
    the live view direction and A_t into `build_scene`. EXTENDED and
    POINT_SOURCE override the shape representation entirely, so the silhouette
    is not relevant in those regimes. The `angle_groups` set (Phase 10) gates
    which annotation toggles render.
    """
    view_dir = compute_view_direction_scene(state)
    A_t = projected_area_m2(state)
    traces = build_scene(
        state,
        regime=regime,
        gsd_m=gsd_m,
        view_dir_scene=view_dir,
        projected_area_m2=A_t,
        angle_groups=angle_groups,
    )
    fig = go.Figure(data=traces)
    eye = camera_eye_from_traces(traces)
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis=dict(title="x"),
            yaxis=dict(title="y"),
            zaxis=dict(title="z"),
            camera=dict(
                up=dict(x=0.0, y=0.0, z=1.0),
                eye=eye,
            ),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        uirevision="locked",
    )
    return fig


# Ordered (component_id, prop) pairs for the callback's Output list.
ALL_OUTPUTS: Final[tuple[tuple[str, str], ...]] = (
    ("scene", "figure"),
    ("mode-regime-reason", "children"),
    ("readout-text", "children"),
    ("readout-explainer", "children"),
    ("angle-groups-empty-caption", "children"),
    *((sid, "disabled") for sid in TARGET_DISABLE_IDS),
    ("tgt-shape", "disabled"),
)


def update_scene(*values: float | str) -> tuple:
    """Single Dash callback target — order must match `ALL_INPUT_IDS`."""
    if len(values) != len(ALL_INPUT_IDS):
        raise ValueError(
            f"update_scene: got {len(values)} inputs, expected {len(ALL_INPUT_IDS)}. "
            f"Order must match dev_tools.geometry_gui.app.main.ALL_INPUT_IDS."
        )
    raw = dict(zip(ALL_INPUT_IDS, values))
    state = _state_from_inputs(raw)
    regime, reason = classify_regime(state)
    gsd_m, _ = derived_readout(state)["gsd"]
    angle_group_value = raw.get("angle-groups") or []
    angle_groups: frozenset[str] = frozenset(
        v for v in angle_group_value if isinstance(v, str)
    )
    fig = _figure_from_state(state, regime, gsd_m, angle_groups)
    readout_values = format_readout(state, regime, reason)
    readout_text = render_text(readout_values)
    explainer = f"Facet decomposition: {multi_facet_explainer(state.target_shape)}"
    empty_caption = EMPTY_SELECTION_CAPTION if not angle_groups else ""
    disabled_target = tuple(
        slider_disabled(sid, regime, state.target_shape) for sid in TARGET_DISABLE_IDS
    )
    return (
        fig,
        reason,
        readout_text,
        explainer,
        empty_caption,
        *disabled_target,
        shape_dropdown_disabled(regime),
    )


app: Dash = Dash(__name__)
app.title = "RADIANT Geometry GUI"

app.layout = html.Div(
    [
        html.H2("RADIANT Geometry GUI", style={"margin": "8px 12px"}),
        html.Div(
            [
                controls_panel(),
                html.Div(
                    [
                        dcc.Graph(
                            id="scene",
                            style={"height": "82vh"},
                            config={
                                "displayModeBar": True,
                                "scrollZoom": True,
                                "doubleClick": "reset",
                            },
                        ),
                        readout_panel(),
                    ],
                    style={
                        "width": "68%",
                        "padding": "12px",
                        "boxSizing": "border-box",
                    },
                ),
            ],
            style={"display": "flex", "flexDirection": "row"},
        ),
    ]
)

app.callback(
    [Output(component_id, prop) for component_id, prop in ALL_OUTPUTS],
    [Input(component_id, "value") for component_id in ALL_INPUT_IDS],
)(update_scene)


if __name__ == "__main__":
    # host=0.0.0.0 so the page reaches you even if the OS routes loopback
    # through iCloud Private Relay / a corporate proxy. Local-only network.
    app.run(debug=True, host="0.0.0.0", port=8050)
