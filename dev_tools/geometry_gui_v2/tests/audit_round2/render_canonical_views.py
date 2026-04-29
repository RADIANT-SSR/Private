"""Render the 9 canonical views off-screen for round-2 audit.

Per ``PLAN_v2_remediation_round2.md`` §1 and §10, each R-task in round 2
is verified across the full canonical-view set, not just the default
cylinder. This module is the single entry point for that render.

The 9 views (per round-2 plan §10):
  1. box_default
  2. cone_default
  3. cylinder_default
  4. extended_default
  5. flat_plate_default
  6. geometry_diagram          (Phase 10 all-angle-groups view)
  7. point_source_default
  8. sphere_default
  9. sun_terminator            (theta_s = 60 deg, Delta_phi = 90 deg)

This is a renderer, not a test. It writes PNGs to the directory passed
in via ``--out``. Importable so R1-R9 can call it directly between
edits.

C7 holds: no Qt imports — uses ``pv.Plotter(off_screen=True)``.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import pathlib
from typing import Iterable

import pyvista as pv

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.scene.builder import build_scene
from dev_tools.geometry_gui_v2.scene.camera_views import camera_pose_for

WINDOW_SIZE = (1920, 1080)


def _state_for(view: str) -> SceneState:
    base = SceneState.default()
    if view == "box_default":
        return dataclasses.replace(base, target_shape="box")
    if view == "cone_default":
        return dataclasses.replace(base, target_shape="cone")
    if view == "cylinder_default":
        return dataclasses.replace(base, target_shape="cylinder")
    if view == "flat_plate_default":
        return dataclasses.replace(base, target_shape="flat_plate")
    if view == "sphere_default":
        return dataclasses.replace(base, target_shape="sphere")
    if view == "extended_default":
        # Force the extended-scene regime via override; physics inputs
        # left at defaults so the scene reads as the same baseline with
        # the extended-cell pixel footprint visible.
        return dataclasses.replace(base, regime_override="extended")
    if view == "point_source_default":
        return dataclasses.replace(base, regime_override="point_source")
    if view == "geometry_diagram":
        # All-angle-groups view: default sphere target with all the
        # angle arcs visible. Same as default state.
        return base
    if view == "sun_terminator":
        return dataclasses.replace(
            base,
            target_shape="sphere",
            solar_zenith_rad=math.radians(60.0),
            relative_azimuth_rad=math.radians(90.0),
        )
    raise ValueError(f"unknown canonical view: {view!r}")


CANONICAL_VIEWS: tuple[str, ...] = (
    "box_default",
    "cone_default",
    "cylinder_default",
    "extended_default",
    "flat_plate_default",
    "geometry_diagram",
    "point_source_default",
    "sphere_default",
    "sun_terminator",
)


def render_view(view: str, out_path: pathlib.Path) -> None:
    """Render one canonical view to a PNG."""
    state = _state_for(view)
    p = pv.Plotter(off_screen=True, window_size=WINDOW_SIZE)
    try:
        build_scene(state, plotter=p)
        # Use the existing canonical iso pose so the audit baseline is
        # reproducible and matches the phase-1 golden frame.
        p.camera_position = camera_pose_for("iso")
        p.show(auto_close=False)
        from PIL import Image

        img = p.screenshot(return_img=True)
        Image.fromarray(img).save(out_path)
    finally:
        p.close()


def render_all(out_dir: pathlib.Path, views: Iterable[str] = CANONICAL_VIEWS) -> list[pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[pathlib.Path] = []
    for v in views:
        path = out_dir / f"{v}.png"
        render_view(v, path)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        required=True,
        help="Output directory for PNGs.",
    )
    parser.add_argument(
        "--views",
        nargs="*",
        default=list(CANONICAL_VIEWS),
        help="Subset of canonical views to render (default: all 9).",
    )
    args = parser.parse_args()
    paths = render_all(args.out, args.views)
    for p in paths:
        print(f"  wrote {p}")


if __name__ == "__main__":
    main()
