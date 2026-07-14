"""Render the default geometry scenario TWO ways for the Phase 6 visual-direction ADR.

(a) geometry_gui_v2 as-is  -> lit / PBR look (drive its real scene builder).
(b) flat-shaded / line-art restyle -> same geometry, edges on, flat shading,
    light background from the Phase 1 design tokens, no PBR.

Offscreen VTK path (confirmed working in this env: pyvista 0.47.3, vtk 9.6.1).
"""
from __future__ import annotations

import os
import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True

OUT = os.path.dirname(os.path.abspath(__file__))
WIN = (1100, 850)

# Phase 1 light-theme tokens (src/radiant/gui/themes/tokens.py LIGHT)
TOK_BG = "#ebeef2"      # bg
TOK_PANEL = "#fafbfc"   # panel
TOK_INK = "#1b2230"     # ink
TOK_ACCENT = "#b8431a"  # accent (terracotta)

# Mockup color roles (radiant_geometry_handoff.md §7)
SUN = "#C28A1F"     # amber
SENSOR = "#3A6FAA"  # cyan/blue (sensor family)
NORMAL = "#3A8A66"  # green (surface normal / zenith)
PHASE = "#b8431a"   # magenta/accent for phase/azimuth
TARGET = "#2EC4B6"  # teal target body


# ---------------------------------------------------------------------------
# (a) The real geometry_gui_v2 builder, exactly as it ships (lit / PBR).
# ---------------------------------------------------------------------------
def render_lit() -> None:
    from dev_tools.geometry_gui_v2.scene import build_scene
    from dev_tools.geometry_gui_v2.app.state import SceneState

    # Use a target scaled up a bit so the shape reads at the sub-pixel default.
    state = SceneState.default()
    p = pv.Plotter(off_screen=True, window_size=list(WIN))
    try:
        build_scene(state, plotter=p)
    except Exception as exc:  # labels solver can need a live rw; fall back
        print(f"  [lit] full builder raised ({exc!r}); retrying without labels")
        p.close()
        p = _lit_minimal()
    p.screenshot(os.path.join(OUT, "direction_a_lit_pbr.png"))
    p.close()
    print("  wrote direction_a_lit_pbr.png")


def _scene_geometry():
    """Representative not-to-scale schematic geometry, shared by both looks.

    Target at origin on a ground plane; sensor up-and-off-nadir; sun high.
    Vectors are unit-ish display lengths (NOT to scale) per the owner rule.
    """
    target_c = np.array([0.0, 0.0, 0.0])
    ground_z = -1.2
    sensor = np.array([2.6, -1.4, 3.4])      # up + cross-track
    sun = np.array([-2.2, 2.4, 3.8])
    ground_pt = np.array([0.0, 0.0, ground_z])  # sub-target ground point
    return target_c, ground_z, sensor, sun, ground_pt


def _add_vectors(p, flat: bool):
    tc, gz, sensor, sun, gpt = _scene_geometry()
    lw = 4 if flat else 3

    def arrow(a, b, color):
        d = b - a
        p.add_mesh(
            pv.Arrow(start=a, direction=d, scale=float(np.linalg.norm(d)),
                     tip_length=0.14, tip_radius=0.045, shaft_radius=0.016),
            color=color, smooth_shading=not flat,
            pbr=not flat, metallic=0.0 if flat else 0.1,
            roughness=1.0 if flat else 0.5,
        )

    # boresight (sensor -> target), sun ray (sun -> target), surface normal
    # (target -> up), sun-to-ground (sun -> ground point)
    arrow(sensor, tc, SENSOR)
    arrow(sun, tc, SUN)
    arrow(tc, tc + np.array([0.0, 0.0, 1.6]), NORMAL)
    arrow(sun, gpt, PHASE)


def _add_bodies(p, flat: bool):
    tc, gz, sensor, sun, gpt = _scene_geometry()

    # ground plane
    ground = pv.Plane(center=(0, 0, gz), direction=(0, 0, 1), i_size=6, j_size=6,
                      i_resolution=12, j_resolution=12)
    if flat:
        p.add_mesh(ground, color="#d7dbe2", opacity=0.5, show_edges=True,
                   edge_color="#b7bfcb", line_width=1, lighting=False)
    else:
        p.add_mesh(ground, color="#2b3038", opacity=0.5, show_edges=True,
                   edge_color="#3a4048", line_width=1)

    # target sphere
    sph = pv.Sphere(radius=0.6, center=tc, theta_resolution=48, phi_resolution=48)
    if flat:
        p.add_mesh(sph, color=TARGET, show_edges=True, edge_color=TOK_INK,
                   line_width=1, lighting=False, opacity=1.0)
    else:
        p.add_mesh(sph, color=TARGET, pbr=True, metallic=0.1, roughness=0.45,
                   smooth_shading=True, opacity=0.92)

    # sensor glyph
    sg = pv.Sphere(radius=0.13, center=sensor)
    p.add_mesh(sg, color=SENSOR, lighting=not flat)
    # sun glyph
    sn = pv.Sphere(radius=0.17, center=sun)
    p.add_mesh(sn, color=SUN, lighting=not flat)
    # ground point marker
    gm = pv.Sphere(radius=0.08, center=gpt)
    p.add_mesh(gm, color=PHASE, lighting=not flat)


def _lit_minimal() -> pv.Plotter:
    p = pv.Plotter(off_screen=True, window_size=list(WIN))
    p.set_background("#1F242B")  # geometry_gui_v2 VIEWPORT_BACKGROUND_COLOR
    p.enable_lightkit()
    _add_bodies(p, flat=False)
    _add_vectors(p, flat=False)
    p.camera_position = "iso"
    p.camera.azimuth = 25
    p.camera.elevation = 12
    return p


# ---------------------------------------------------------------------------
# (b) Flat-shaded / line-art restyle of the SAME scene, light theme bg.
# ---------------------------------------------------------------------------
def render_flat() -> None:
    p = pv.Plotter(off_screen=True, window_size=list(WIN))
    p.set_background(TOK_BG)  # Phase 1 light token
    # flat: no lightkit, ambient only so colors read as drawn (line-art)
    _add_bodies(p, flat=True)
    _add_vectors(p, flat=True)
    p.camera_position = "iso"
    p.camera.azimuth = 25
    p.camera.elevation = 12
    p.screenshot(os.path.join(OUT, "direction_b_flat_lineart.png"))
    p.close()
    print("  wrote direction_b_flat_lineart.png")


# For an apples-to-apples minimal comparison, also render (a) as the minimal
# lit version of the SAME representative scene.
def render_lit_minimal_matched() -> None:
    p = _lit_minimal()
    p.screenshot(os.path.join(OUT, "direction_a_lit_matched.png"))
    p.close()
    print("  wrote direction_a_lit_matched.png")


if __name__ == "__main__":
    print("Rendering (a) lit/PBR (real builder)...")
    render_lit()
    print("Rendering (a) lit/PBR (matched minimal scene)...")
    render_lit_minimal_matched()
    print("Rendering (b) flat/line-art restyle...")
    render_flat()
    print("done.")
