"""Viewer-local angle recomputation — the consistency check against stage truth.

**The stage is the single source of angle truth** (arch doc §6.3, GUI plan Phase 7 task
2). The 3D scene draws angle arcs from the ported ``geometry.js`` direction math
(:mod:`radiant.gui.viewer.scene._directions`), which the viewer uses **only** for
camera / projection / picking — never as a second angle authority. This module recomputes
each drawable angle from that same scene-direction math and exposes the
``stage_outputs["geometry"]`` key it must agree with, so a test can assert the two never
diverge beyond an explicit tolerance (divergence is a red build).

Only the two angles the scene can honestly draw *and* that the stage emits are here:

  ============  =======  ==================================  ==============================
  name          symbol   stage_outputs["geometry"] key       viewer-local recomputation
  ============  =======  ==================================  ==============================
  off_nadir     η        ``eta_rad``                         ``acos(ẑ · obs_dir)``
  sun_zenith    θ_s      ``theta_s_rad``                     ``acos(ẑ · sun_dir)``
  ============  =======  ==================================  ==============================

The phase-angle arc (α_t) is **excluded** — it is not a stage output, so there is nothing
to check it against (see ``arcs/phase_angle.py``).

Tolerance rationale: each recomputation is ``acos`` of the ``z`` component of a unit
vector the scene builds as ``[sinθ·…, …, cosθ]``; the round-trip through construction and
``acos`` is exact to floating-point (measured residual ~1e-15 rad). The consistency
tolerance is set two orders of magnitude looser at ``ANGLE_CONSISTENCY_ABS_TOL_RAD =
1e-9`` rad — tight enough that any *real* divergence (a scene-math change that stops
tracking the stage) fails the build, loose enough to never flake on float noise.

Pure numpy/stdlib; no Qt, no physics stage — reads a :class:`ViewerState` only.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

import numpy as np

from radiant.gui.viewer.scene._directions import (
    observer_direction_scene,
    sun_direction_scene,
)

if TYPE_CHECKING:
    from radiant.gui.viewer.viewer_state import ViewerState

# Explicit consistency tolerance (radians). Documented in the module docstring.
ANGLE_CONSISTENCY_ABS_TOL_RAD: Final[float] = 1e-9

# Annotation name → the ``stage_outputs["geometry"]`` key it must agree with.
ANGLE_TRUTH_KEYS: Final[dict[str, str]] = {
    "off_nadir": "eta_rad",
    "sun_zenith": "theta_s_rad",
}

_ZENITH: Final[np.ndarray] = np.array([0.0, 0.0, 1.0], dtype=np.float64)


def recompute_angle_rad(state: ViewerState, name: str) -> float:
    """Recompute the named angle (radians) from the scene-direction math.

    *name* must be a key of :data:`ANGLE_TRUTH_KEYS`; raises ``KeyError`` otherwise (the
    catalog guarantees a valid name). The result is compared against the stage output by
    the consistency test — it is **not** used for display.
    """
    if name == "off_nadir":
        direction = observer_direction_scene(state)
    elif name == "sun_zenith":
        direction = sun_direction_scene(state)
    else:
        raise KeyError(f"angle_truth: no viewer-local recomputation for {name!r}")
    cos_angle = float(np.clip(np.dot(_ZENITH, direction), -1.0, 1.0))
    return math.acos(cos_angle)


__all__ = [
    "ANGLE_CONSISTENCY_ABS_TOL_RAD",
    "ANGLE_TRUTH_KEYS",
    "recompute_angle_rad",
]
