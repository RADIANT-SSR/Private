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

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    classify_regime,
    derived_readout,
)
from dev_tools.geometry_gui_v2.scene import style
from dev_tools.geometry_gui_v2.scene._directions import (
    background_direction_scene,
    observer_direction_scene,
    sun_direction_scene,
)
from dev_tools.geometry_gui_v2.scene._layout import (
    ARC_RADIUS_M,
    SCENE_BACKGROUND_DISTANCE_M,
    SCENE_OBSERVER_DISTANCE_M,
    SCENE_SUN_DISTANCE_M,
)
from dev_tools.geometry_gui_v2.scene.labels.typography import viewport_label


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


def _vector_midpoint(unit: npt.NDArray[np.float64], distance: float) -> npt.NDArray[np.float64]:
    return unit * (distance * 0.5)


def collect_anchors(state: SceneState) -> list[LabelAnchor]:
    """Return every Phase-4 label anchor for ``state``.

    Order matches the right-dock readout grouping (objects, vectors,
    angles). The text is the human-readable string that appears next to
    the leader line.
    """
    obs_dir = observer_direction_scene(state)
    sun_dir = sun_direction_scene(state)
    bg_dir = background_direction_scene(state)
    obs_pos = obs_dir * SCENE_OBSERVER_DISTANCE_M
    sun_pos = sun_dir * SCENE_SUN_DISTANCE_M
    bg_pos = bg_dir * SCENE_BACKGROUND_DISTANCE_M

    surface_normal_end = np.array(
        [0.0, 0.0, max(1.5 * state.target_radius_m, 1.5)], dtype=np.float64
    )

    derived = derived_readout(state)
    slant_km = derived["slant_range"][0] / 1_000.0
    proj_area = derived["projected_area"][0]
    regime, _reason = classify_regime(state)

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
    sym_a_t = viewport_label("projected_area")
    sym_n_B = viewport_label("surface_normal_background")
    sym_s_t = viewport_label("sun_vector_target")
    sym_s_B = viewport_label("sun_vector_background")
    sym_boresight = viewport_label("boresight")
    sym_theta_off = viewport_label("off_nadir_angle")
    sym_theta_s = viewport_label("solar_zenith_target")
    sym_alpha_t = viewport_label("phase_angle_target")

    return [
        # --- objects --------------------------------------------------
        LabelAnchor(
            name="lbl_target",
            anchor_world=np.zeros(3, dtype=np.float64),
            text=f"Target  {sym_a_t} = {proj_area:.3g} m^2  ({regime.value})",
            color=style.TARGET_COLOR,
            group=GROUP_OBJECTS,
        ),
        LabelAnchor(
            name="lbl_observer",
            anchor_world=obs_pos,
            text=f"Observer  ({slant_km:.0f} km)",
            color=style.SATELLITE_FAMILY,
            group=GROUP_OBJECTS,
        ),
        LabelAnchor(
            name="lbl_sun",
            anchor_world=sun_pos,
            text=f"Sun  ({sym_theta_s} = {math.degrees(state.solar_zenith_rad):.0f} deg)",
            color=style.SOLAR_FAMILY,
            group=GROUP_OBJECTS,
        ),
        LabelAnchor(
            name="lbl_background",
            anchor_world=bg_pos,
            text="Background",
            color=style.SURFACE_FAMILY,
            group=GROUP_OBJECTS,
        ),
        # --- vectors --------------------------------------------------
        LabelAnchor(
            name="lbl_vec_boresight",
            anchor_world=_vector_midpoint(obs_dir, SCENE_OBSERVER_DISTANCE_M),
            text=sym_boresight,
            color=style.SATELLITE_FAMILY,
            group=GROUP_VECTORS,
        ),
        LabelAnchor(
            name="lbl_vec_surface_normal",
            anchor_world=surface_normal_end,
            text=sym_n_B,
            color=style.SURFACE_FAMILY,
            group=GROUP_VECTORS,
        ),
        LabelAnchor(
            name="lbl_vec_sun_ray",
            anchor_world=_vector_midpoint(sun_dir, SCENE_SUN_DISTANCE_M),
            text=sym_s_t,
            color=style.SOLAR_FAMILY,
            group=GROUP_VECTORS,
        ),
        LabelAnchor(
            name="lbl_vec_sun_to_background",
            anchor_world=_midpoint(sun_pos, bg_pos),
            text=sym_s_B,
            color=style.SOLAR_FAMILY,
            group=GROUP_VECTORS,
        ),
        # --- angle arcs -----------------------------------------------
        LabelAnchor(
            name="lbl_arc_off_nadir",
            anchor_world=off_nadir_mid,
            text=f"{sym_theta_off} = {math.degrees(state.observer_look_angle_rad):.0f} deg",
            color=style.SATELLITE_FAMILY,
            group=GROUP_ANGLES,
        ),
        LabelAnchor(
            name="lbl_arc_sun_zenith",
            anchor_world=sun_zenith_mid,
            text=f"{sym_theta_s} = {math.degrees(state.solar_zenith_rad):.0f} deg",
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


def _slerp_mid(
    a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
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
