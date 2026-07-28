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
  path_zenith        θ_o      ``theta_o_rad``                     zenith of the θ_o arc ray
  lower_zenith       ζ_low    ``theta_o_rad`` / ``eta_rad``       zenith of the ζ_low arc ray
  =================  =======  ==================================  ==============================

The last two are the ADR-0011 generalized-geometry arcs. Their rays are built with the
same :func:`~radiant.gui.viewer.projection.dir_from_az_zen` the schematic uses, and the
recomputation reads the zenith angle back off that ray, so a scene-side change that stops
drawing the arc at the stage angle fails the check. ζ_low has no key of its own: it is the
path zenith at the segment's *lower* endpoint, which is ``theta_o_rad`` for a down or level
scene and ``π − eta_rad`` for an up-looking one — the direction-keyed transform defined once
in :func:`radiant.gui.viewer.angle_catalog.lower_zenith_rad` and applied to the stage
outputs by :func:`stage_angle_rad`.

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
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from radiant.gui.viewer import angle_catalog
from radiant.gui.viewer.projection import compute_angles, dir_from_az_zen

if TYPE_CHECKING:
    from radiant.gui.viewer.viewer_state import ViewerState

# Explicit consistency tolerance (radians). Documented in the module docstring.
ANGLE_CONSISTENCY_ABS_TOL_RAD: Final[float] = 1e-9

# Annotation name → the ``stage_outputs["geometry"]`` key it must agree with.
# ``lower_zenith`` records its down/level source here; :func:`stage_angle_rad` applies the
# ADR-0011 direction-keyed transform that swaps it to ``eta_rad`` for an up-looking scene.
ANGLE_TRUTH_KEYS: Final[dict[str, str]] = {
    "off_nadir": "eta_rad",
    "sun_zenith": "theta_s_rad",
    "relative_azimuth": "delta_phi_rad",
    "path_zenith": "theta_o_rad",
    "lower_zenith": "theta_o_rad",
}


def stage_angle_rad(geometry: Mapping[str, Any], name: str) -> float:
    """The stage-truth value (radians) the named annotation must agree with.

    *geometry* is ``stage_outputs["geometry"]``. Every annotation but ``lower_zenith``
    reads one key verbatim; ζ_low is the lower endpoint's path zenith, so it goes through
    :func:`radiant.gui.viewer.angle_catalog.lower_zenith_rad` keyed by the stage-published
    ``los_direction`` (θ_o for down/level, ``π − η`` for up). Raises ``KeyError`` for an
    unknown *name* or a missing stage key — a programming error, never a silent default.
    """
    if name == "lower_zenith":
        return angle_catalog.lower_zenith_rad(
            float(geometry["theta_o_rad"]),
            float(geometry["eta_rad"]),
            str(geometry.get("los_direction", angle_catalog.LOS_DOWN)),
        )
    return float(geometry[ANGLE_TRUTH_KEYS[name]])


def _ray_zenith_rad(zenith_rad: float, azimuth_deg: float = 0.0) -> float:
    """Zenith angle read back off a ray the scene math builds at *zenith_rad*.

    Round-trips the angle through :func:`~radiant.gui.viewer.projection.dir_from_az_zen`
    and ``acos`` exactly as the schematic's arc placement does, so the check exercises the
    scene construction rather than restating the input. The azimuth places the ray in the
    scene and does not affect the zenith angle recovered here.
    """
    ray = dir_from_az_zen(azimuth_deg, math.degrees(zenith_rad))
    return float(math.acos(float(np.clip(ray[2], -1.0, 1.0))))


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
    if name == "path_zenith":
        return _ray_zenith_rad(state.theta_o_rad)
    if name == "lower_zenith":
        return _ray_zenith_rad(
            angle_catalog.lower_zenith_rad(
                state.theta_o_rad, state.observer_look_angle_rad, state.los_direction
            )
        )
    raise KeyError(f"angle_truth: no viewer-local recomputation for {name!r}")


__all__ = [
    "ANGLE_CONSISTENCY_ABS_TOL_RAD",
    "ANGLE_TRUTH_KEYS",
    "recompute_angle_rad",
    "stage_angle_rad",
]
