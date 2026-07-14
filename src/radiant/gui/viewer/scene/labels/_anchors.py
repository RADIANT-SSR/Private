"""Anchor registry — every labeled primitive's 3D anchor + text + color.

Phase 4 (PLAN_v2.md §12 step 3): every label-emitting primitive registers
a single ``LabelAnchor`` here. The layout solver consumes the full list,
deconflicts in screen space, and the renderer places one
``LeaderLabel`` per anchor.

Rule 19 carve-out: shared helper for the labels/ family per CLAUDE.md
Rule 19's "tightly coupled computations that share internal state or
helper functions" exception. Each named label registration lives next
to its primitive (the per-vector / per-arc / per-glyph file owns *what*
it labels and *where*); this module is just the typed bag they pour
into.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from radiant.gui.viewer.scene import style
from radiant.gui.viewer.scene._directions import (
    background_direction_scene,
    observer_direction_scene,
    sun_direction_scene,
)
from radiant.gui.viewer.scene._display_distance import schematic_display_distance_m
from radiant.gui.viewer.scene._layout import (
    ARC_RADIUS_M,
    SCENE_BACKGROUND_DISTANCE_M,
    SCENE_OBSERVER_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)
from radiant.gui.viewer.scene.labels.typography import viewport_label
from radiant.gui.viewer.scene.target._pose import target_centroid_scene
from radiant.gui.viewer.viewer_state import ViewerState as SceneState

# Group names align with the right-panel's collapsible sections so the
# Phase-5 "show only the active group" hover behaviour can be wired in
# trivially: filter `LabelAnchor` list by `group`.
GROUP_OBJECTS: Final[str] = "objects"
GROUP_VECTORS: Final[str] = "vectors"
GROUP_ANGLES: Final[str] = "angles"


@dataclass(frozen=True)
class LabelAnchor:
    """One labeled primitive's 3D anchor + display text + family color.

    ``anchor_world`` is the canonical 3D point the label points *at*. The
    layout solver picks the actual label position in screen space, then
    the leader line connects the two.
    """

    name: str
    anchor_world: npt.NDArray[np.float64]
    text: str
    color: str
    group: str


def _midpoint(a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    return (a + b) * 0.5


def collect_anchors(state: SceneState) -> list[LabelAnchor]:
    """Return every Phase-4 label anchor for ``state``.

    Order matches the right-dock readout grouping (objects, vectors,
    angles). The text is the human-readable string that appears next to
    the leader line.
    """
    obs_dir = observer_direction_scene(state)
    sun_dir = sun_direction_scene(state)
    bg_dir = background_direction_scene(state)
    target_pos = np.array(target_centroid_scene(state), dtype=np.float64)
    # S5: glyph display positions are anchored at the lifted target
    # centroid and scale with target altitude — see
    # ``scene/_display_distance.py``. Pre-S5 these were
    # ``direction * SCENE_*_DISTANCE_M`` from the world origin, which
    # detached the leader-line anchor from the actual glyph position
    # at high target altitude.
    obs_pos = target_pos + obs_dir * schematic_display_distance_m(state, SCENE_OBSERVER_DISTANCE_M)
    sun_pos = target_pos + sun_dir * schematic_display_distance_m(state, SCENE_SUN_DISTANCE_M)
    bg_pos = target_pos + bg_dir * schematic_display_distance_m(state, SCENE_BACKGROUND_DISTANCE_M)

    surface_normal_end = np.array(
        [0.0, 0.0, max(1.5 * state.target_radius_m, 1.5)], dtype=np.float64
    )

    # S1 (round-3 remediation): viewport labels are minimal nouns +
    # symbol labels only. Data readouts (altitude, slant range, projected
    # area, regime tag) live in the right-dock ReadoutsPanel and the
    # left-dock ParametersPanel. The viewport never duplicates panel
    # content.

    # Angle midpoints sit on the great-arc midpoint at ``ARC_RADIUS_M``.
    zenith = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    off_nadir_mid = _slerp_mid(zenith, obs_dir) * ARC_RADIUS_M
    sun_zenith_mid = _slerp_mid(zenith, sun_dir) * ARC_RADIUS_M
    phase_mid = _slerp_mid(sun_dir, obs_dir) * ARC_RADIUS_M

    # T10 of the visual remediation: every symbol literal flows through
    # ``viewport_label()`` so the glossary YAML is the single source of
    # truth. Free-text composites (e.g. the off-nadir-angle readout) use
    # the typography helper for the symbol and append the formatted
    # value next to it.
    sym_n_B = viewport_label("surface_normal_background")
    sym_s_t = viewport_label("sun_vector_target")
    sym_s_B = viewport_label("sun_vector_background")
    sym_boresight = viewport_label("boresight")
    sym_theta_off = viewport_label("off_nadir_angle")
    sym_theta_s = viewport_label("solar_zenith_target")
    sym_alpha_t = viewport_label("phase_angle_target")
    name_satellite = viewport_label("object_satellite")
    name_sun = viewport_label("object_sun")
    name_target = viewport_label("object_target")
    name_background = viewport_label("object_background")

    has_background = state.background_kind != "none"

    anchors: list[LabelAnchor] = [
        # --- objects --------------------------------------------------
        LabelAnchor(
            name="lbl_target",
            anchor_world=np.array(target_centroid_scene(state), dtype=np.float64),
            text=name_target,
            color=style.TARGET_COLOR,
            group=GROUP_OBJECTS,
        ),
        LabelAnchor(
            name="lbl_observer",
            anchor_world=obs_pos,
            text=name_satellite,
            color=style.SATELLITE_FAMILY,
            group=GROUP_OBJECTS,
        ),
        LabelAnchor(
            name="lbl_sun",
            anchor_world=sun_pos,
            text=name_sun,
            color=style.SOLAR_FAMILY,
            group=GROUP_OBJECTS,
        ),
        # --- vectors --------------------------------------------------
        # S4: anchor at the midpoint of the *visible* line (target →
        # observer / target → sun), matching the new line origin in
        # ``vectors/boresight.py`` and ``vectors/sun_ray.py``. Pre-S4
        # these used ``_vector_midpoint(unit, scene_distance)`` —
        # midpoint of (origin → end_pos) — which detached the leader
        # anchor from the visible line whenever the target was lifted
        # above ground (high altitude).
        LabelAnchor(
            name="lbl_vec_boresight",
            anchor_world=_midpoint(target_pos, obs_pos),
            text=sym_boresight,
            color=style.SATELLITE_FAMILY,
            group=GROUP_VECTORS,
        ),
        LabelAnchor(
            name="lbl_vec_sun_ray",
            anchor_world=_midpoint(target_pos, sun_pos),
            text=sym_s_t,
            color=style.SOLAR_FAMILY,
            group=GROUP_VECTORS,
        ),
        # --- angle arcs -----------------------------------------------
        LabelAnchor(
            name="lbl_arc_off_nadir",
            anchor_world=off_nadir_mid,
            text=sym_theta_off,
            color=style.SATELLITE_FAMILY,
            group=GROUP_ANGLES,
        ),
        LabelAnchor(
            name="lbl_arc_sun_zenith",
            anchor_world=sun_zenith_mid,
            text=sym_theta_s,
            color=style.SOLAR_FAMILY,
            group=GROUP_ANGLES,
        ),
        LabelAnchor(
            name="lbl_arc_phase_angle",
            anchor_world=phase_mid,
            text=sym_alpha_t,
            color=style.TARGET_VECTOR_FAMILY,
            group=GROUP_ANGLES,
        ),
    ]

    # Phase-7 diet: only emit background-coupled labels when there *is* a
    # background. The matching primitives (glyph_background,
    # vec_sun_to_background, vec_surface_normal) follow the same gate so
    # we never anchor a label at a non-existent actor.
    if has_background:
        anchors.append(
            LabelAnchor(
                name="lbl_background",
                anchor_world=bg_pos,
                text=name_background,
                color=style.SURFACE_FAMILY,
                group=GROUP_OBJECTS,
            )
        )
        anchors.append(
            LabelAnchor(
                name="lbl_vec_surface_normal",
                anchor_world=surface_normal_end,
                text=sym_n_B,
                color=style.SURFACE_FAMILY,
                group=GROUP_VECTORS,
            )
        )
        anchors.append(
            LabelAnchor(
                name="lbl_vec_sun_to_background",
                anchor_world=_midpoint(sun_pos, bg_pos),
                text=sym_s_B,
                color=style.SOLAR_FAMILY,
                group=GROUP_VECTORS,
            )
        )

    return anchors


def _slerp_mid(a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Unit vector at the great-arc midpoint between ``a`` and ``b``."""
    a = a / max(np.linalg.norm(a), 1e-12)
    b = b / max(np.linalg.norm(b), 1e-12)
    cos_theta = float(np.clip(np.dot(a, b), -1.0, 1.0))
    theta = math.acos(cos_theta)
    if theta < 1e-3:
        return a.copy()
    if theta > math.pi - 1e-3:
        # Antipodal — the midpoint is degenerate; pick an arbitrary
        # perpendicular so the label has a stable position.
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(a, up)) > 0.95:
            up = np.array([1.0, 0.0, 0.0])
        perp = np.cross(a, up)
        return perp / max(np.linalg.norm(perp), 1e-12)
    sin_theta = math.sin(theta)
    s = math.sin(0.5 * theta) / sin_theta
    mid = (a + b) * s
    return mid / max(np.linalg.norm(mid), 1e-12)
