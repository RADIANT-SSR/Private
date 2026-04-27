"""Scene orchestrator — turns a `SceneState` into a list of plotly traces.

Phase 8 redesign (PLAN.md §11): target-centric layout. Earlier phases placed
the target at the +Z pole of a unit-radius display Earth, which made the
target invisible at any realistic altitude. The redesign anchors the target
at the scene origin (display radius 1.0), draws Earth as a curved ground
patch below, and places observer + sun glyphs at fixed *illustrative*
distances along their true angular directions.

Coordinate convention (display-only, frozen by PLAN.md §11):
  * +Z is local zenith at the target.
  * +X is the along-track direction in which the observer is offset from
    nadir at non-zero look angle. Observer sits in the −X / +Z quadrant so
    the boresight extends through the target into +X / −Z (background
    point B).
  * +Y is the local-east axis used by the sun-direction spherical math
    (`sun_unit_vector_local`).

Per PLAN.md C7: distances in the rendered scene are illustrative, not
metric. Angles are physical and exact. Real altitudes and ranges appear in
glyph labels and the readout panel.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from radiant.core.geometry import euler_to_rotation_matrix
from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.scene_builder.background_marker import (
    background_marker_traces,
)
from dev_tools.geometry_gui.app.scene_builder.background_point import (
    background_point_position_display,
    background_point_traces,
)
from dev_tools.geometry_gui.app.scene_builder.body_axes import body_axes_traces
from dev_tools.geometry_gui.app.scene_builder.boresight_ray import (
    boresight_ray_traces,
)
from dev_tools.geometry_gui.app.scene_builder.ground_patch import (
    ground_patch_traces,
)
from dev_tools.geometry_gui.app.scene_builder.nadir_reference import (
    nadir_reference_traces,
)
from dev_tools.geometry_gui.app.scene_builder.observer_glyph import (
    OBSERVER_DISPLAY_DISTANCE,
    observer_glyph_traces,
)
from dev_tools.geometry_gui.app.scene_builder.off_nadir_arc import (
    off_nadir_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.phase_angle_arc import (
    phase_angle_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.pixel_cell_marker import (
    pixel_cell_traces,
)
from dev_tools.geometry_gui.app.scene_builder.point_source_marker import (
    point_source_traces,
)
from dev_tools.geometry_gui.app.scene_builder.silhouette_disk import (
    silhouette_disk_traces,
)
from dev_tools.geometry_gui.app.scene_builder.solar_zenith_arc import (
    solar_zenith_arc_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_arrow import (
    sun_unit_vector_scene,
)
from dev_tools.geometry_gui.app.scene_builder.sun_glyph import (
    sun_glyph_traces,
    sun_position_illustrative,
)
from dev_tools.geometry_gui.app.scene_builder.sun_ray_background import (
    sun_ray_background_traces,
)
from dev_tools.geometry_gui.app.scene_builder.sun_ray_target import (
    sun_ray_target_traces,
)
from dev_tools.geometry_gui.app.scene_builder.surface_normal_arrow import (
    SURFACE_NORMAL_AT_B,
    surface_normal_arrow_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_marker import (
    target_marker_traces,
)
from dev_tools.geometry_gui.app.scene_builder.target_shape_meshes import (
    target_shape_traces,
)
from dev_tools.geometry_gui.app.scene_builder.azimuth_arc import azimuth_arc_traces
from dev_tools.geometry_gui.app.scene_builder.elevation_arc import elevation_arc_traces
from dev_tools.geometry_gui.app.scene_builder.sun_zenith_arc import sun_zenith_arc_traces
from dev_tools.geometry_gui.app.scene_builder.sun_azimuth_arc import sun_azimuth_arc_traces
from dev_tools.geometry_gui.app.scene_builder.world_axes_triad import (
    world_axes_triad_traces,
)
from dev_tools.geometry_gui.app.scene_builder.off_nadir_projection import (
    off_nadir_projection_traces,
)
from dev_tools.geometry_gui.app.scene_builder.phase_angle_projection import (
    phase_angle_projection_traces,
)
from dev_tools.geometry_gui.app.scene_builder.solar_zenith_projection import (
    solar_zenith_projection_traces,
)
from dev_tools.geometry_gui.app.state import SceneState

# Phase 10 angle-group toggle keys. Order is presentation order in the UI.
ANGLE_GROUP_KEYS: Final[tuple[str, ...]] = (
    "observer",
    "target",
    "background",
    "sun",
    "world_axes",
    "projections",
)
DEFAULT_ANGLE_GROUPS: Final[frozenset[str]] = frozenset(
    {"observer", "target", "background"}
)

# Target sits at scene origin (PLAN.md §11). Display radius is the anchor
# unit of the figure: every other illustrative distance is expressed in
# multiples of TARGET_DISPLAY_RADIUS = 1.0.
TARGET_DISPLAY_RADIUS: Final[float] = 1.0

# Body-axis arrows scale with the target.
BODY_AXIS_DISPLAY_LENGTH: Final[float] = 1.5 * TARGET_DISPLAY_RADIUS


def target_position_display() -> npt.NDArray[np.float64]:
    """Target sits at the scene origin (PLAN.md §11 redesign)."""
    return np.zeros(3, dtype=np.float64)


def boresight_unit_display(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit vector observer→target in scene-display coordinates.

    The observer is placed in the −X / +Z quadrant (off-nadir along −X at
    look angle θ_look). Boresight points from the observer to the target,
    so it has +X and −Z components:

        boresight = (sin θ_look, 0, −cos θ_look)
    """
    theta = state.observer_look_angle_rad
    return np.array(
        [math.sin(theta), 0.0, -math.cos(theta)],
        dtype=np.float64,
    )


def observer_position_display(state: SceneState) -> npt.NDArray[np.float64]:
    """Observer at `OBSERVER_DISPLAY_DISTANCE` opposite the boresight (illustrative)."""
    return target_position_display() - OBSERVER_DISPLAY_DISTANCE * boresight_unit_display(state)


def view_direction_unit_display(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit target→observer in display coords (negation of boresight)."""
    return -boresight_unit_display(state)


def target_body_to_scene_display(state: SceneState) -> npt.NDArray[np.float64]:
    """3×3 rotation that maps a target body-frame vector to display coordinates.

    Target's yaw/pitch/roll Euler angles rotate body → display. Mesh modules
    apply this matrix to body-frame vertices and translate by the target's
    display position (the origin in the Phase 8 layout).
    """
    return euler_to_rotation_matrix(
        state.target_yaw_rad,
        state.target_pitch_rad,
        state.target_roll_rad,
    )


def build_scene(
    state: SceneState,
    *,
    regime: RadiometricRegime | None = None,
    gsd_m: float | None = None,
    view_dir_scene: npt.NDArray[np.float64] | None = None,
    projected_area_m2: float | None = None,
    angle_groups: frozenset[str] | None = None,
) -> list[go.Mesh3d | go.Scatter3d | go.Cone]:
    """Compose the full target-centric scene with Phase-9 angle annotations.

    Trace order is fixed for deterministic snapshots:

      1. Ground patch (curved cap, day/night-shaded by sun direction)
      2. Background point B (boresight–ground intersection marker)
      3. Surface normal n_B at B
      4. Observer glyph (satellite icon at OBSERVER_DISPLAY_DISTANCE)
      5. Sun glyph (yellow disk at SUN_DISPLAY_DISTANCE)
      6. Target marker
      7. Boresight ray observer→target + dashed extension to B + `o` label
      8. Nadir reference at observer
      9. Off-nadir arc + label at observer
      10. Sun ray s_t (target → sun)
      11. Sun ray s_B (B → sun, dashed)
      12. Phase-angle arc α_t at target
      13. Solar-zenith arc θ_sun,B at B
      14. Target representation:
           * shape mesh + body axes (default / SUB_PIXEL)
           * pixel cell  (EXTENDED)
           * point dot   (POINT_SOURCE)
      15. Silhouette disk (Phase 5; SUB_PIXEL / default only)
      16. Background marker ring

    Parameters
    ----------
    regime
        Phase-4 dispatch hook. ``None`` keeps the Phase-2 contract — render
        the shape mesh + body axes — so existing scene-builder goldens stay
        valid.
    gsd_m
        Real-world ground-sample distance [m], surfaced on the pixel-cell
        trace name in EXTENDED mode. Required when ``regime == EXTENDED``.
    view_dir_scene
        Phase-5 backward-compat hook. **Ignored** in Phase 8 — the silhouette
        normal is now computed locally from the illustrative observer
        position so it always faces the on-screen observer glyph. Argument
        retained so existing callers do not break.
    projected_area_m2
        Phase-5 silhouette area input. Computed by `view_model.projected_area_m2`
        and shown verbatim on hover. Without it the silhouette is omitted.
    angle_groups
        Phase-10 multi-select angle filter. ``None`` falls back to
        ``DEFAULT_ANGLE_GROUPS`` (observer/target/background) so existing
        callers and goldens get the visible-by-default annotation set.
        Pass ``frozenset()`` for the bare-geometry view.
    """
    del view_dir_scene  # ignored in Phase 8 — see docstring.

    groups: frozenset[str] = (
        DEFAULT_ANGLE_GROUPS if angle_groups is None else angle_groups
    )

    target_pos = target_position_display()
    boresight = boresight_unit_display(state)
    observer_pos = observer_position_display(state)
    R_target = target_body_to_scene_display(state)
    sun_dir_scene = sun_unit_vector_scene(state)
    sun_pos = sun_position_illustrative(target_pos, sun_dir_scene)
    bg_pos = background_point_position_display(target_pos, boresight)

    view_dir_disp = -boresight  # target → observer (Phase 9 annotations)

    traces: list[go.Mesh3d | go.Scatter3d | go.Cone] = []

    # --- Always-on base scene (anchor objects + bare geometry) ---
    traces.extend(ground_patch_traces(sun_dir_scene=sun_dir_scene))
    traces.extend(background_point_traces(bg_pos))
    traces.extend(observer_glyph_traces(observer_pos, state.observer_altitude_m))
    traces.extend(sun_glyph_traces(sun_pos, state.solar_zenith_rad, state.relative_azimuth_rad))
    traces.extend(target_marker_traces(target_pos))
    traces.extend(boresight_ray_traces(observer_pos, target_pos, bg_pos, state.observer_look_angle_rad))

    # --- Group: world_axes (master Cartesian triad at origin) ---
    if "world_axes" in groups:
        traces.extend(world_axes_triad_traces())

    # --- Group: observer (angles measured at the observer) ---
    if "observer" in groups:
        traces.extend(nadir_reference_traces(observer_pos, target_pos))
        traces.extend(off_nadir_arc_traces(observer_pos, target_pos))
        traces.extend(azimuth_arc_traces(target_pos, boresight))
        traces.extend(elevation_arc_traces(target_pos, boresight))

    # --- Group: target (angles measured at the target) ---
    if "target" in groups:
        traces.extend(sun_ray_target_traces(target_pos, sun_pos))
        traces.extend(phase_angle_arc_traces(target_pos, view_dir_disp, sun_dir_scene))

    # --- Group: background (angles measured at point B) ---
    if "background" in groups:
        traces.extend(surface_normal_arrow_traces(bg_pos))
        traces.extend(sun_ray_background_traces(bg_pos, sun_dir_scene))
        traces.extend(solar_zenith_arc_traces(bg_pos, SURFACE_NORMAL_AT_B, sun_dir_scene))

    # --- Group: sun (sun-direction decomposition into θ_s + Δφ) ---
    if "sun" in groups:
        traces.extend(sun_zenith_arc_traces(target_pos, sun_dir_scene))
        traces.extend(sun_azimuth_arc_traces(target_pos, sun_dir_scene))

    # --- Group: projections (dashed companion arcs on reference planes) ---
    if "projections" in groups:
        traces.extend(off_nadir_projection_traces(observer_pos, target_pos))
        traces.extend(
            phase_angle_projection_traces(target_pos, view_dir_disp, sun_dir_scene)
        )
        traces.extend(
            solar_zenith_projection_traces(bg_pos, SURFACE_NORMAL_AT_B, sun_dir_scene)
        )

    if regime == RadiometricRegime.EXTENDED:
        if gsd_m is None:
            raise ValueError(
                "build_scene: regime=EXTENDED requires gsd_m (real-world GSD in meters)."
            )
        traces.extend(pixel_cell_traces(target_pos, gsd_m))
    elif regime == RadiometricRegime.POINT_SOURCE:
        traces.extend(point_source_traces(target_pos))
    else:
        traces.extend(
            target_shape_traces(state, target_pos, R_target, TARGET_DISPLAY_RADIUS)
        )
        traces.extend(
            body_axes_traces(target_pos, R_target, BODY_AXIS_DISPLAY_LENGTH)
        )
        if projected_area_m2 is not None:
            view_dir_disp = view_direction_unit_display(state)
            traces.extend(
                silhouette_disk_traces(target_pos, view_dir_disp, projected_area_m2)
            )

    traces.extend(background_marker_traces(state, target_pos))
    return traces
