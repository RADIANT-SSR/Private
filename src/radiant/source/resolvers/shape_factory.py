"""Factory that builds a TargetShape from the source schema scalars.

Step 1.2 of the Target Definition Matrix Implementation Plan: dispatches
``geometry.target.shape`` onto the concrete shape class and wires the
dimensional + orientation scalars from ``_schema.py`` into the
constructor.

Per Rule 19 this is the only computation in this module — no I/O, no
descriptor assembly, no conditional fallbacks to ``projected_area_m2``.
The calling site (``_inferrer._build_target_descriptor``) is
responsible for Q3 precedence (shape-wins-over-A_t with a UserWarning)
so the factory stays a pure data transform.

The factory enforces that every dimensional input required by the
selected shape is strictly positive (Rule 15 — ParameterBoundsError
with what/why/action/context).  This is the physics-boundary validation
that Step 1.1 deliberately deferred from the schema (where
``0.0`` is the "not set" sentinel for every dimensional scalar).
"""

from __future__ import annotations

from typing import Any

from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.source.shape import TargetShape
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere

_SHAPE_NOT_SET = "none"


def _require_positive(params: ParameterSet, name: str, shape: str) -> float:
    """Return a dimensional scalar or raise ParameterBoundsError if ≤ 0."""
    value: float = params.get(name)
    if value <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"{name} = {value} m is non-positive but shape='{shape}' "
                f"requires it to be strictly positive"
            ),
            why=(
                "Geometric primitives are defined only for positive "
                "dimensions; a zero or negative value collapses the "
                "shape and makes projected area ill-defined."
            ),
            action=(f"Set {name} > 0 m in the scenario input, or select a different shape."),
            context={"param": name, "value": value, "shape": shape},
        )
    return value


def _orientation_rad(params: ParameterSet) -> tuple[float, float, float]:
    """Read the (yaw, pitch, roll) tuple from schema scalars."""
    return (
        float(params.get("geometry.target.shape_yaw_rad")),
        float(params.get("geometry.target.shape_pitch_rad")),
        float(params.get("geometry.target.shape_roll_rad")),
    )


def build_shape(params: ParameterSet) -> TargetShape | None:
    """Return a ``TargetShape`` instance or ``None`` when no shape is set.

    Reads the resolved ``geometry.target.shape*`` scalars from ``params``
    and dispatches on the ``geometry.target.shape`` enum (see
    [_schema.py](../_schema.py) ``SHAPE``).  Orientation is the ZYX
    Euler triple ``(shape_yaw_rad, shape_pitch_rad, shape_roll_rad)``
    per Rule 3.

    Returns
    -------
    TargetShape | None
        ``None`` when ``shape == "none"`` (back-compat: caller falls
        back to ``geometry.target.projected_area_m2``).  Otherwise a
        concrete primitive from [radiant.source.shapes](../shapes/).

    Raises
    ------
    ParameterBoundsError
        When a dimensional scalar required by the selected shape is
        zero or negative.
    """
    shape_name: str = params.get("geometry.target.shape")
    if shape_name == _SHAPE_NOT_SET:
        return None

    orientation = _orientation_rad(params)
    built: Any  # narrowed per-branch; TargetShape is a Protocol

    if shape_name == "sphere":
        radius_m = _require_positive(params, "geometry.target.shape_radius_m", shape_name)
        built = Sphere(radius_m=radius_m, orientation_rad=orientation)
    elif shape_name == "cylinder":
        radius_m = _require_positive(params, "geometry.target.shape_radius_m", shape_name)
        length_m = _require_positive(params, "geometry.target.shape_length_m", shape_name)
        built = Cylinder(
            radius_m=radius_m,
            length_m=length_m,
            orientation_rad=orientation,
        )
    elif shape_name == "flat_plate":
        length_m = _require_positive(params, "geometry.target.shape_length_m", shape_name)
        width_m = _require_positive(params, "geometry.target.shape_width_m", shape_name)
        built = FlatPlate(
            length_m=length_m,
            width_m=width_m,
            orientation_rad=orientation,
        )
    elif shape_name == "box":
        length_m = _require_positive(params, "geometry.target.shape_length_m", shape_name)
        width_m = _require_positive(params, "geometry.target.shape_width_m", shape_name)
        height_m = _require_positive(params, "geometry.target.shape_height_m", shape_name)
        built = Box(
            length_m=length_m,
            width_m=width_m,
            height_m=height_m,
            orientation_rad=orientation,
        )
    elif shape_name == "cone":
        base_radius_m = _require_positive(params, "geometry.target.shape_base_radius_m", shape_name)
        height_m = _require_positive(params, "geometry.target.shape_height_m", shape_name)
        built = Cone(
            base_radius_m=base_radius_m,
            height_m=height_m,
            orientation_rad=orientation,
        )
    else:  # pragma: no cover — schema enum guards this.
        raise ParameterBoundsError(
            what=f"geometry.target.shape = {shape_name!r} is not recognised",
            why="The shape enum is fixed by the v1 catalog (Matrix §3).",
            action=(
                "Set shape to one of: sphere, cylinder, flat_plate, "
                "box, cone, or 'none' for back-compat."
            ),
            context={"shape": shape_name},
        )

    return built


__all__ = ["build_shape"]
