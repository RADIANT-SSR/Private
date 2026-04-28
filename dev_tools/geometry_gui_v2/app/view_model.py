"""View-model layer — pure functions over ``SceneState``.

No PyVista, no Qt, no I/O. Every public function below takes a ``SceneState``
and returns a value derived deterministically from it.

Imports are restricted to public RADIANT symbols (``radiant.core.*``,
``radiant.source.shapes.*``). Two pieces of math are intentionally
re-implemented locally rather than imported from private modules
(per CLAUDE.md Rule 11 and PLAN_v2.md C6 — no underscored ``radiant``
symbols in this dev tool):

  * ``view_direction_body`` — the 4-line ZYX-transpose that mirrors the
    private ``radiant.source.shapes._helpers.view_to_body``.
  * ``classify_regime`` — mirrors the four-branch decision in the private
    ``radiant.source.stage._classify_regime``, restated per CLAUDE.md
    Rule 10. This is math, not API.

C3 invariant (PLAN_v2.md §3): ``projected_area_m2(state)`` is computed by
calling ``TargetShape.projected_area(...)`` directly. There is no parallel
implementation of projected area anywhere in this tool.

Lifted from v1 (``dev_tools/geometry_gui/app/view_model.py``) per
PLAN_v2.md §6. Only the package import path changed.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt

from radiant.core.geometry import (
    ObserverGeometry,
    SceneGeometry,
    TargetGeometry,
    euler_to_rotation_matrix,
)
from radiant.core.regime import RadiometricRegime
from radiant.source.shape import TargetShape
from radiant.source.shapes.box import Box
from radiant.source.shapes.cone import Cone
from radiant.source.shapes.cylinder import Cylinder
from radiant.source.shapes.flat_plate import FlatPlate
from radiant.source.shapes.sphere import Sphere

from dev_tools.geometry_gui_v2.app.state import SceneState

# Boresight unit vector in the observer body frame: +Z by RADIANT convention
# (CLAUDE.md §"Coordinate System"). The observer→target ray points at +Z, so
# target→observer points at −Z in the same frame.
_OBSERVER_BORESIGHT_BODY: Final[npt.NDArray[np.float64]] = np.array(
    [0.0, 0.0, 1.0], dtype=np.float64
)


# ---------------------------------------------------------------------------
# Scene-frame geometry wrappers
# ---------------------------------------------------------------------------


def build_scene_geometry(state: SceneState) -> SceneGeometry:
    """Wrap observer / target altitudes & attitudes into a ``SceneGeometry``.

    Delegates to the public ``radiant.core.geometry`` constructors — slant
    range, ground range, GSD and IFOV come from ``SceneGeometry``'s own methods,
    not from a parallel implementation here.
    """
    observer = ObserverGeometry(
        altitude_m=state.observer_altitude_m,
        look_angle_rad=state.observer_look_angle_rad,
        yaw_rad=state.observer_yaw_rad,
        pitch_rad=state.observer_pitch_rad,
        roll_rad=state.observer_roll_rad,
    )
    target = TargetGeometry(altitude_m=state.target_altitude_m)
    return SceneGeometry(observer=observer, target=target)


# ---------------------------------------------------------------------------
# Shape construction
# ---------------------------------------------------------------------------


def build_target_shape(state: SceneState) -> TargetShape:
    """Instantiate a concrete ``TargetShape`` from ``SceneState``.

    The shape is built with ``orientation_rad=(0, 0, 0)``. The view-model
    owns the scene→body rotation explicitly via ``view_direction_body``, so
    handing the shape a pre-rotated body-frame vector and a zero-orientation
    shape avoids double-rotating.
    """
    kind = state.target_shape
    if kind == "sphere":
        return Sphere(radius_m=state.target_radius_m)
    if kind == "cylinder":
        return Cylinder(
            radius_m=state.target_radius_m, length_m=state.target_length_m
        )
    if kind == "flat_plate":
        return FlatPlate(
            length_m=state.target_length_m, width_m=state.target_width_m
        )
    if kind == "box":
        return Box(
            length_m=state.target_length_m,
            width_m=state.target_width_m,
            height_m=state.target_height_m,
        )
    if kind == "cone":
        return Cone(
            base_radius_m=state.target_base_radius_m,
            height_m=state.target_height_m,
        )
    raise ValueError(
        f"build_target_shape: unknown target_shape={kind!r}. "
        f"Expected one of sphere/cylinder/flat_plate/box/cone."
    )


# ---------------------------------------------------------------------------
# View-direction unit vectors
# ---------------------------------------------------------------------------


def compute_view_direction_scene(state: SceneState) -> npt.NDArray[np.float64]:
    """Unit 3-vector target→observer expressed in the scene frame.

    Convention (CLAUDE.md §"Coordinate System"):
      * +Z in the observer body frame is the boresight (toward target).
      * observer → target is +Z; target → observer is −Z, both in body frame.
      * The scene frame is the inertial frame in which the observer's
        attitude is expressed. Rotating the body-frame −Z vector by
        ``R_observer = R_z(yaw) R_y(pitch) R_x(roll)`` (ZYX) yields the
        scene-frame direction from target to observer.

    Returns a unit-norm vector by construction (the rotation is orthogonal).
    """
    R_observer = euler_to_rotation_matrix(
        state.observer_yaw_rad,
        state.observer_pitch_rad,
        state.observer_roll_rad,
    )
    return R_observer @ (-_OBSERVER_BORESIGHT_BODY)


def view_direction_body(state: SceneState) -> npt.NDArray[np.float64]:
    """Same target→observer vector, expressed in the *target* body frame.

    Re-implements the 4-line transpose of ``radiant.source.shapes._helpers.view_to_body``
    locally (C6 — no underscored ``radiant`` symbols). ``R_target`` rotates
    body→scene; its transpose rotates scene→body. The shapes were instantiated
    with ``orientation_rad=(0, 0, 0)`` (see ``build_target_shape``), so the
    body-frame vector returned here flows straight into ``shape.projected_area``
    without further rotation.
    """
    v_scene = compute_view_direction_scene(state)
    R_target = euler_to_rotation_matrix(
        state.target_yaw_rad,
        state.target_pitch_rad,
        state.target_roll_rad,
    )
    return R_target.T @ v_scene


# ---------------------------------------------------------------------------
# Projected area — the C3 invariant link to radiometry
# ---------------------------------------------------------------------------


def projected_area_m2(state: SceneState) -> float:
    """Projected target area [m²] as the radiometry would see it.

    The whole point of this dev tool: the on-screen number comes from the
    same call site the radiometric chain would make.
    """
    shape = build_target_shape(state)
    return shape.projected_area(view_direction_body(state))


# ---------------------------------------------------------------------------
# Regime classification (Rule 10, restated locally)
# ---------------------------------------------------------------------------


def classify_regime(state: SceneState) -> tuple[RadiometricRegime, str]:
    """Classify the target into a ``RadiometricRegime`` and explain why.

    Mirrors the Rule-10 decision tree as restated in CLAUDE.md and as
    implemented in ``radiant.source.stage._classify_regime`` (private — not
    imported per Rule 11):

      1. Explicit ``regime_override`` ≠ "auto" → return that regime.
      2. ``fill_fraction`` < 1.0 → SUB_PIXEL (user told us so).
      3. ``ang_ext ≥ 2 · ifov`` → EXTENDED.
      4. ``ang_ext ≤ 0.25 · ifov`` → POINT_SOURCE.
      5. otherwise → SUB_PIXEL.

    Returns the regime and a one-line, human-readable reason that the
    readout panel shows verbatim.
    """
    if state.regime_override != "auto":
        regime = RadiometricRegime(state.regime_override)
        return regime, f"user override: {state.regime_override}"

    if state.target_fill_fraction < 1.0:
        return (
            RadiometricRegime.SUB_PIXEL,
            f"fill_fraction = {state.target_fill_fraction:.3f} < 1.0",
        )

    ang_ext = _angular_extent_rad(state)
    ifov = state.pixel_pitch_m / state.focal_length_m

    if ang_ext >= 2.0 * ifov:
        return RadiometricRegime.EXTENDED, "ang_ext >= 2*ifov"
    if ang_ext <= 0.25 * ifov:
        return RadiometricRegime.POINT_SOURCE, "ang_ext <= 0.25*ifov"
    return RadiometricRegime.SUB_PIXEL, "0.25*ifov < ang_ext < 2*ifov"


def _angular_extent_rad(state: SceneState) -> float:
    """Angular extent of the target as seen from the observer [rad].

    Defined (matching ``_classify_regime``) as ``sqrt(A_t) / slant_range``.
    Returns +inf when the slant range collapses to zero (degenerate
    observer/target stack-up); the regime classifier reads that as
    "fully extended" by Rule 10.
    """
    A = projected_area_m2(state)
    slant = build_scene_geometry(state).slant_range_m
    if slant <= 0.0:
        return math.inf
    return math.sqrt(A) / slant


# ---------------------------------------------------------------------------
# Readout panel values (one labeled scalar each, every value carries units)
# ---------------------------------------------------------------------------


def display_view_azimuth_rad(state: SceneState) -> float:
    """View-direction azimuth on the local horizontal plane [rad].

    Defined from the *display-frame* boresight ``(sin θ_look, 0, −cos θ_look)``,
    i.e. matches the on-figure ``az`` arc at the target. View = −boresight, so
    az = atan2(view_y, view_x). For the canonical observer in the −X/+Z
    quadrant (θ_look > 0) az = π (180°). The display value is what the user
    reads off the figure, so the readout reflects that.
    """
    theta = state.observer_look_angle_rad
    view_x = -math.sin(theta)
    view_y = 0.0
    if view_x == 0.0 and view_y == 0.0:
        return 0.0
    return math.atan2(view_y, view_x)


def display_view_elevation_rad(state: SceneState) -> float:
    """View-direction elevation above local horizon [rad].

    el = arcsin(view_z) where view = −boresight = (..., ..., cos θ_look).
    Matches the on-figure ``el`` arc.
    """
    theta = state.observer_look_angle_rad
    return math.asin(max(-1.0, min(1.0, math.cos(theta))))


def derived_readout(state: SceneState) -> dict[str, tuple[float, str]]:
    """Labeled scalars + units strings for the readout panel.

    Hard rule (CLAUDE.md / user memory): every numeric value rendered
    in the GUI carries explicit units. This dict is the single source
    of truth for those (value, unit) pairs.
    """
    geom = build_scene_geometry(state)
    gsd = geom.gsd_m(state.focal_length_m, state.pixel_pitch_m)
    ifov = geom.ifov_rad(state.focal_length_m, state.pixel_pitch_m)
    A_t = projected_area_m2(state)
    pixel_area = gsd * gsd
    fill_eff = min(1.0, A_t / pixel_area) if pixel_area > 0.0 else 0.0
    return {
        "slant_range": (geom.slant_range_m, "m"),
        "ground_range": (geom.ground_range_m, "m"),
        "gsd": (gsd, "m"),
        "ifov": (ifov, "rad"),
        "angular_extent": (_angular_extent_rad(state), "rad"),
        "pixel_area": (pixel_area, "m^2"),
        "projected_area": (A_t, "m^2"),
        "fill_fraction_effective": (fill_eff, "(dimensionless)"),
        "view_azimuth": (display_view_azimuth_rad(state), "rad"),
        "view_elevation": (display_view_elevation_rad(state), "rad"),
        "solar_zenith": (state.solar_zenith_rad, "rad"),
        "relative_azimuth": (state.relative_azimuth_rad, "rad"),
    }


# ---------------------------------------------------------------------------
# Display formatting (units on every line — Jason's hard memory rule)
# ---------------------------------------------------------------------------


# Component-id → preferred display unit & format. Keeps every numeric line
# unit-bearing without sprinkling format strings through the Qt panel code.
_READOUT_FORMATTERS: Final[dict[str, tuple[str, "callable[[float], str]"]]] = {  # type: ignore[name-defined]
    "ro-slant-range": ("km", lambda v: f"{v / 1_000.0:.3f} km"),
    "ro-ground-range": ("km", lambda v: f"{v / 1_000.0:.3f} km"),
    "ro-gsd": ("m", lambda v: f"{v:.4g} m"),
    "ro-ifov": ("µrad", lambda v: f"{v * 1e6:.3f} µrad"),
    "ro-angular-extent": (
        "µrad",
        lambda v: "∞ rad" if not math.isfinite(v) else f"{v * 1e6:.3f} µrad",
    ),
    "ro-fill-fraction": (
        "(dimensionless)",
        lambda v: f"{v:.3f} (dimensionless)",
    ),
    "ro-pixel-area": ("m^2", lambda v: f"{v:.4g} m^2"),
    "ro-projected-area": ("m^2", lambda v: f"{v:.4g} m^2"),
    "ro-view-azimuth": ("deg", lambda v: f"{math.degrees(v):.2f} deg"),
    "ro-view-elevation": ("deg", lambda v: f"{math.degrees(v):.2f} deg"),
    "ro-solar-zenith": ("deg", lambda v: f"{math.degrees(v):.2f} deg"),
    "ro-relative-azimuth": ("deg", lambda v: f"{math.degrees(v):.2f} deg"),
}


def format_readout(
    state: SceneState,
    regime: RadiometricRegime,
    regime_reason: str,
) -> dict[str, str]:
    """Return component-id → fully formatted, unit-bearing display string.

    Sole formatter for the Phase-4 readout panel. Numeric rows pull from
    ``derived_readout(state)`` so the value shown on screen is exactly the
    value the radiometric chain would consume (C3 invariant).

    Solar zenith and relative azimuth are pulled directly from ``SceneState``
    (no derived computation) and rendered in degrees for human friendliness.
    """
    derived = derived_readout(state)
    out: dict[str, str] = {}
    for component_id, (unit_label, formatter) in _READOUT_FORMATTERS.items():
        del unit_label  # the formatter writes the unit; this entry is for docs only
        key = component_id.removeprefix("ro-").replace("-", "_")
        if key == "fill_fraction":
            key = "fill_fraction_effective"
        value, _native_unit = derived[key]
        out[component_id] = formatter(value)
    out["ro-regime"] = regime.value
    out["ro-regime-reason"] = regime_reason
    return out


# ---------------------------------------------------------------------------
# Multi-facet explainer
# ---------------------------------------------------------------------------


_FACET_TEXT: Final[dict[str, str]] = {
    "sphere": "single-projection (orientation-invariant)",
    "flat_plate": "single facet (uses |cos theta|, so reverse view = front view)",
    "box": "six axis-aligned facets (sum of three positive-cos contributions)",
    "cylinder": "lateral side + 2 end caps",
    "cone": "lateral side + circular base",
}


def multi_facet_explainer(shape: str) -> str:
    """Return the per-shape facet-decomposition string shown under the readout.

    Picks the line from ``_FACET_TEXT``, which is keyed on ``SceneState.target_shape``
    (matching the dropdown ids). Unknown shapes return a generic placeholder
    so the readout never crashes if someone adds a shape without updating
    this map.
    """
    return _FACET_TEXT.get(shape, "facet decomposition not documented")
