"""Build the README screenshot gallery.

Run from the repo root:

    python -m dev_tools.geometry_gui.docs_screenshots.render_gallery

Produces, under `dev_tools/geometry_gui/docs_screenshots/`:
  * `gallery_<shape>.png`         — sub-pixel scene per shape (5 files)
  * `gallery_extended.png`        — EXTENDED regime (pixel cell shown)
  * `gallery_point_source.png`    — POINT_SOURCE regime (single dot)
  * `gallery_sun_terminator.png`  — sun arrow + Earth night-side shading

This is a developer helper, not a pytest test.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import plotly.graph_objects as go

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.app.view_model import (
    classify_regime,
    compute_view_direction_scene,
    derived_readout,
    projected_area_m2,
)

OUT = Path(__file__).parent
SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def _layout(title: str) -> dict:
    return dict(
        title=title,
        scene=dict(
            aspectmode="data",
            xaxis=dict(title="x"),
            yaxis=dict(title="y"),
            zaxis=dict(title="z"),
            camera=dict(
                up=dict(x=0.0, y=0.0, z=1.0),
                eye=dict(x=2.0, y=2.0, z=1.6),
            ),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=True,
    )


def _save(fig: go.Figure, name: str) -> None:
    path = OUT / name
    fig.write_image(str(path), width=900, height=700)
    print(f"[ok] wrote {path}")


def _shape_state(shape: str) -> SceneState:
    return dataclasses.replace(
        SceneState.default(),
        target_shape=shape,  # type: ignore[arg-type]
        target_yaw_rad=math.radians(20.0),
        target_pitch_rad=math.radians(-10.0),
        target_roll_rad=math.radians(7.0),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # Per-shape gallery (sub-pixel default).
    for shape in SHAPES:
        state = _shape_state(shape)
        regime, _reason = classify_regime(state)
        traces = build_scene(
            state,
            regime=regime,
            view_dir_scene=compute_view_direction_scene(state),
            projected_area_m2=projected_area_m2(state),
        )
        fig = go.Figure(data=traces)
        fig.update_layout(**_layout(f"{shape} — sub-pixel default state"))
        _save(fig, f"gallery_{shape}.png")

    # EXTENDED — large flat plate.
    extended = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=15.0,
        target_width_m=15.0,
    )
    gsd_m, _ = derived_readout(extended)["gsd"]
    fig_ext = go.Figure(
        data=build_scene(extended, regime=RadiometricRegime.EXTENDED, gsd_m=gsd_m)
    )
    fig_ext.update_layout(**_layout("EXTENDED regime — pixel cell on ground"))
    _save(fig_ext, "gallery_extended.png")

    # POINT_SOURCE — tiny plate.
    point = dataclasses.replace(
        SceneState.default(),
        target_shape="flat_plate",
        target_length_m=0.1,
        target_width_m=0.1,
    )
    fig_pt = go.Figure(
        data=build_scene(point, regime=RadiometricRegime.POINT_SOURCE)
    )
    fig_pt.update_layout(**_layout("POINT_SOURCE regime — single emitter"))
    _save(fig_pt, "gallery_point_source.png")

    # Sun terminator — typical illumination.
    sun = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(60.0),
        relative_azimuth_rad=math.radians(90.0),
        background_kind="ground",
    )
    fig_sun = go.Figure(data=build_scene(sun))
    fig_sun.update_layout(
        **_layout("Sun arrow + terminator-shaded Earth (θ_s=60°, Δφ=90°)")
    )
    _save(fig_sun, "gallery_sun_terminator.png")

    # Phase 10 geometry-diagram — every angle group enabled (all annotations
    # visible in one shot, matching the 2D reference diagram).
    diagram = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(35.0),
        relative_azimuth_rad=math.radians(60.0),
        background_kind="ground",
    )
    all_groups = frozenset(
        {"observer", "target", "background", "sun", "world_axes", "projections"}
    )
    fig_diagram = go.Figure(
        data=build_scene(
            diagram,
            view_dir_scene=compute_view_direction_scene(diagram),
            projected_area_m2=projected_area_m2(diagram),
            angle_groups=all_groups,
        )
    )
    fig_diagram.update_layout(
        **_layout("Geometry diagram — all angle groups (Phase 10)")
    )
    _save(fig_diagram, "gallery_geometry_diagram.png")


if __name__ == "__main__":
    main()
