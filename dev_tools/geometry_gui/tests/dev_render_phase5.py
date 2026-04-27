"""Phase-5 screenshot helper — silhouette disk + readout text dump.

Run from the repo root:

    python -m dev_tools.geometry_gui.tests.dev_render_phase5

Produces:
  * `golden/phase5_silhouette_sphere.png`     — 1 m sphere, silhouette face-on
  * `golden/phase5_silhouette_plate60.png`    — 2x3 plate at 60°, half area
  * `golden/phase5_readout_dump.txt`          — full readout text + explainer

This is a developer helper, not a pytest test.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.app.view_model import (
    classify_regime,
    compute_view_direction_scene,
    format_readout,
    multi_facet_explainer,
    projected_area_m2,
)
from dev_tools.geometry_gui.app.layout.readout_panel import render_text

GOLDEN = Path(__file__).parent / "golden"


def _fig(state: SceneState) -> go.Figure:
    regime, _ = classify_regime(state)
    traces = build_scene(
        state,
        regime=regime,
        view_dir_scene=compute_view_direction_scene(state),
        projected_area_m2=projected_area_m2(state),
    )
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            aspectmode="manual",
            xaxis=dict(title="x", range=[-0.15, 0.15]),
            yaxis=dict(title="y", range=[-0.15, 0.15]),
            zaxis=dict(title="z", range=[0.95, 1.15]),
            camera=dict(
                up=dict(x=0.0, y=0.0, z=1.0),
                eye=dict(x=1.5, y=1.5, z=1.7),
            ),
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        showlegend=True,
    )
    return fig


def _dump_readout(state: SceneState, label: str) -> str:
    regime, reason = classify_regime(state)
    values = format_readout(state, regime, reason)
    panel = render_text(values)
    explainer = f"Facet decomposition: {multi_facet_explainer(state.target_shape)}"
    A_t = projected_area_m2(state)
    return (
        f"=== {label} ===\n"
        f"shape={state.target_shape}, regime={regime.value}\n"
        f"projected_area_m2(state) = {A_t} m^2\n"
        f"--- readout panel ---\n{panel}\n"
        f"--- explainer ---\n{explainer}\n\n"
    )


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)

    sphere_state = SceneState.default()  # 1 m sphere → A_t = π m^2
    plate_state = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=2.0,
        target_width_m=3.0,
        observer_look_angle_rad=0.0,
        target_pitch_rad=math.radians(60.0),
    )

    fig_sphere = _fig(sphere_state)
    fig_sphere.update_layout(title="Phase 5 — sphere R=1 m, silhouette face-on (A_t = π m²)")
    fig_sphere.write_image(str(GOLDEN / "phase5_silhouette_sphere.png"), width=900, height=700)
    print(f"[ok] wrote {GOLDEN / 'phase5_silhouette_sphere.png'}")

    fig_plate = _fig(plate_state)
    fig_plate.update_layout(title="Phase 5 — 2x3 plate at 60° from normal (A_t = 3 m²)")
    fig_plate.write_image(str(GOLDEN / "phase5_silhouette_plate60.png"), width=900, height=700)
    print(f"[ok] wrote {GOLDEN / 'phase5_silhouette_plate60.png'}")

    dump_path = GOLDEN / "phase5_readout_dump.txt"
    with dump_path.open("w") as fh:
        fh.write(_dump_readout(sphere_state, "Default sphere (1 m radius)"))
        fh.write(_dump_readout(plate_state, "Flat plate 2x3, 60° tilt"))
    print(f"[ok] wrote {dump_path}")


if __name__ == "__main__":
    main()
