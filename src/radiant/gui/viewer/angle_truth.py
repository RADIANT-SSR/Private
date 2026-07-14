"""Viewer-local angle recomputation — the consistency check against stage truth.

**The stage is the single source of angle truth** (arch doc §6.3). The 2D schematic draws
angle arcs from the ported ``geometry.js`` direction/angle math
(:mod:`radiant.gui.viewer.projection`), which the viewer uses **only** for arc geometry /
placement — never as a second angle authority. This module recomputes each drawable,
stage-backed angle from that same scene math and names the ``stage_outputs["geometry"]``
key it must agree with, so a test can assert the two never diverge beyond an explicit
tolerance (divergence is a red build — CU-133).

The scene builds its directions exactly as :func:`radiant.gui.viewer.schematic_view.
build_scene` does — the sensor along azimuth 0 at zenith = η, the sun at the relative
azimuth at zenith = θ_s — so :func:`~radiant.gui.viewer.projection.compute_angles` on
those two unit vectors reproduces the stage angles by construction:

  =================  =======  ==================================  ==============================
  name               symbol   stage_outputs["geometry"] key       viewer-local recomputation
  =================  =======  ==================================  ==============================
  off_nadir          η        ``eta_rad``                         ``compute_angles(...).theta_v``
  sun_zenith         θ_s      ``theta_s_rad``                     ``compute_angles(...).theta_s``
  relative_azimuth   Δφ       ``delta_phi_rad``                   ``compute_angles(...).delta_phi``
  =================  =======  ==================================  ==============================

The phase-angle arc (α_t) is **excluded** — it is not a stage output, so there is nothing
to check it against (it renders symbol-only per §6.3).

Tolerance rationale: each recomputation round-trips a unit vector the scene builds as
``dir_from_az_zen`` through ``acos`` / ``atan2``; the round-trip is exact to floating
point (measured residual ~1e-15 rad). The consistency tolerance is set several orders
looser at ``ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9`` rad — tight enough that any *real*
divergence (a scene-math change that stops tracking the stage) fails the build, loose
enough to never flake on float noise.

Pure numpy/stdlib; no Qt, no physics stage — reads a :class:`ViewerState` only.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from radiant.gui.viewer.projection import compute_angles, dir_from_az_zen

if TYPE_CHECKING:
    from radiant.gui.viewer.viewer_state import ViewerState

# Explicit consistency tolerance (radians). Documented in the module docstring.
ANGLE_CONSISTENCY_ABS_TOL_RAD: Final[float] = 1e-9

# Annotation name → the ``stage_outputs["geometry"]`` key it must agree with.
ANGLE_TRUTH_KEYS: Final[dict[str, str]] = {
    "off_nadir": "eta_rad",
    "sun_zenith": "theta_s_rad",
    "relative_azimuth": "delta_phi_rad",
}


def recompute_angle_rad(state: ViewerState, name: str) -> float:
    """Recompute the named angle (radians) from the scene-direction math.

    *name* must be a key of :data:`ANGLE_TRUTH_KEYS`; raises ``KeyError`` otherwise (the
    catalog guarantees a valid name). The directions are built exactly as
    :func:`~radiant.gui.viewer.schematic_view.build_scene` builds them. The result is
    compared against the stage output by the consistency test — it is **not** used for
    display (§6.3).
    """
    sun_dir = dir_from_az_zen(
        math.degrees(state.relative_azimuth_rad), math.degrees(state.solar_zenith_rad)
    )
    sensor_dir = dir_from_az_zen(0.0, math.degrees(state.observer_look_angle_rad))
    angles = compute_angles(sun_dir, sensor_dir)
    if name == "off_nadir":
        return angles.theta_v_rad
    if name == "sun_zenith":
        return angles.theta_s_rad
    if name == "relative_azimuth":
        return angles.delta_phi_rad
    raise KeyError(f"angle_truth: no viewer-local recomputation for {name!r}")


__all__ = [
    "ANGLE_CONSISTENCY_ABS_TOL_RAD",
    "ANGLE_TRUTH_KEYS",
    "recompute_angle_rad",
]
