"""Phase 6 screenshots — sun arrow, terminator-shaded Earth, background ring.

Run from the repo root:

    python -m dev_tools.geometry_gui.tests.dev_render_phase6
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene
from dev_tools.geometry_gui.app.state import SceneState

GOLDEN = Path(__file__).parent / "golden"


def _fig(state: SceneState, *, title: str) -> go.Figure:
    fig = go.Figure(data=build_scene(state))
    fig.update_layout(
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
    return fig


def _save(fig: go.Figure, name: str) -> None:
    path = GOLDEN / name
    fig.write_image(str(path), width=900, height=700)
    print(f"[ok] wrote {path}")


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)

    # 1. Sun overhead (theta_s = 0). Arrow up, full day-side facing camera.
    overhead = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=0.0,
        relative_azimuth_rad=0.0,
        background_kind="cold_space",
    )
    _save(
        _fig(overhead, title="Phase 6 — sun overhead (θ_s=0°), background=cold_space"),
        "phase6_sun_overhead.png",
    )

    # 2. Typical illumination: theta_s=60°, delta_phi=90°.
    typical = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(60.0),
        relative_azimuth_rad=math.radians(90.0),
        background_kind="ground",
    )
    _save(
        _fig(typical, title="Phase 6 — θ_s=60°, Δφ=90°, background=ground"),
        "phase6_sun_60_90.png",
    )

    # 3. Eclipse-ish: theta_s=180° (sun anti-zenith). Arrow points downward
    # through the Earth; near-side hemisphere is the night side.
    eclipse = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(180.0),
        relative_azimuth_rad=0.0,
        background_kind="at_aperture",
    )
    _save(
        _fig(eclipse, title="Phase 6 — θ_s=180° (eclipse), background=at_aperture"),
        "phase6_sun_eclipse.png",
    )


if __name__ == "__main__":
    main()
