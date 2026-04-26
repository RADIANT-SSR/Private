"""Schema-layer tests for the source stage shape-selection parameters.

Step 1.1 of the Target Definition Matrix Implementation Plan registers
the ``source.target.shape*`` scalars so YAML loaders / ``params.set``
accept them.  This file locks the schema contract:

    * the ``source.target.shape`` enum accepts the v1 shape catalog
      (``sphere``, ``cylinder``, ``flat_plate``, ``box``, ``cone``);
    * unknown shape names (``pyramid``) are rejected at
      ``ParameterSet.resolve()``;
    * the defaults resolve cleanly (back-compat sentinel ``"none"`` plus
      the dimensional scalar sentinel ``0.0``);
    * dimensional scalars reject non-numeric input (e.g., a dict
      passed accidentally) and out-of-bounds values.

Wiring these parameters into descriptor construction (Q3 precedence
with ``projected_area_m2``, view-direction-dependent projection) is
Step 1.2; those behaviours are **not** tested here.
"""

from __future__ import annotations

import pytest

from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.source._schema import (
    ALL_PARAMETERS,
    validate_reflectance_albedo_exclusive,
)


def _fresh_params() -> ParameterSet:
    """Return a source-only ParameterSet with every registered default."""
    return ParameterSet(list(ALL_PARAMETERS))


# ---------------------------------------------------------------------------
# Defaults (back-compat — shape not provided)
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_shape_defaults_resolve() -> None:
    """Schema accepts ``shape`` at its default (back-compat path)."""
    params = _fresh_params()
    params.resolve()

    assert params.get("source.target.shape") == "none"
    assert params.get("source.target.shape_radius_m") == 0.0
    assert params.get("source.target.shape_length_m") == 0.0
    assert params.get("source.target.shape_width_m") == 0.0
    assert params.get("source.target.shape_height_m") == 0.0
    assert params.get("source.target.shape_base_radius_m") == 0.0
    assert params.get("source.target.shape_yaw_rad") == 0.0
    assert params.get("source.target.shape_pitch_rad") == 0.0
    assert params.get("source.target.shape_roll_rad") == 0.0


# ---------------------------------------------------------------------------
# Accept: sphere with a positive radius
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_shape_accepts_sphere_with_radius() -> None:
    """``shape="sphere"`` + ``shape_radius_m=1.0`` resolves without raising."""
    params = _fresh_params()
    params.set("source.target.shape", "sphere")
    params.set("source.target.shape_radius_m", 1.0)
    params.resolve()

    assert params.get("source.target.shape") == "sphere"
    assert params.get("source.target.shape_radius_m") == pytest.approx(1.0, abs=0.0)


# ---------------------------------------------------------------------------
# Accept: every shape in the catalog
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape_name", ["sphere", "cylinder", "flat_plate", "box", "cone"]
)
@pytest.mark.level1
def test_shape_enum_accepts_every_catalog_entry(shape_name: str) -> None:
    """Every §3 catalog entry is accepted by the schema enum."""
    params = _fresh_params()
    params.set("source.target.shape", shape_name)
    params.resolve()

    assert params.get("source.target.shape") == shape_name


# ---------------------------------------------------------------------------
# Reject: unknown shape name
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_shape_rejects_unknown_name() -> None:
    """``shape="pyramid"`` raises at resolve time (not in enum)."""
    params = _fresh_params()
    params.set("source.target.shape", "pyramid")

    with pytest.raises(ValueError, match="must be one of"):
        params.resolve()


# ---------------------------------------------------------------------------
# Reject: dimensional scalar given a dict (Rule-16 surface check)
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_shape_radius_rejects_dict_input() -> None:
    """A dict passed to a float dimensional scalar raises at resolve.

    This is the scalar-schema analogue of "reject shape_params when not a
    dict": the flattened schema accepts only numeric input on the
    ``shape_*_m`` parameters and refuses opaque containers per Rule 16.
    """
    params = _fresh_params()
    params.set("source.target.shape_radius_m", {"radius_m": 1.0})

    with pytest.raises(ValueError, match="expects float"):
        params.resolve()


# ---------------------------------------------------------------------------
# Reject: negative dimensional scalar (bounds enforcement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "param_name",
    [
        "source.target.shape_radius_m",
        "source.target.shape_length_m",
        "source.target.shape_width_m",
        "source.target.shape_height_m",
        "source.target.shape_base_radius_m",
    ],
)
@pytest.mark.level1
def test_shape_dim_rejects_negative(param_name: str) -> None:
    """Negative dimensional scalars fail the schema bounds check."""
    params = _fresh_params()
    params.set(param_name, -1.0)

    with pytest.raises(ValueError, match="out of bounds"):
        params.resolve()


# ---------------------------------------------------------------------------
# Orientation scalars (yaw / pitch / roll in rad, ZYX Euler per Rule 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "param_name",
    [
        "source.target.shape_yaw_rad",
        "source.target.shape_pitch_rad",
        "source.target.shape_roll_rad",
    ],
)
@pytest.mark.level1
def test_shape_orientation_accepts_in_range(param_name: str) -> None:
    """Orientation scalars accept full-rotation input in [-2π, 2π]."""
    import math

    params = _fresh_params()
    params.set(param_name, math.pi / 4.0)
    params.resolve()

    assert params.get(param_name) == pytest.approx(math.pi / 4.0, abs=0.0)


@pytest.mark.parametrize(
    "param_name",
    [
        "source.target.shape_yaw_rad",
        "source.target.shape_pitch_rad",
        "source.target.shape_roll_rad",
    ],
)
@pytest.mark.level1
def test_shape_orientation_rejects_out_of_range(param_name: str) -> None:
    """Orientation scalars reject values outside [-2π, 2π]."""
    params = _fresh_params()
    params.set(param_name, 10.0)  # > 2π ≈ 6.28

    with pytest.raises(ValueError, match="out of bounds"):
        params.resolve()


# ---------------------------------------------------------------------------
# Step 3.1 — reflectance / albedo (S4 / S5 / S6)
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_reflectance_scalar_accepted() -> None:
    """ρ = 0.3 resolves cleanly on the source schema."""
    params = _fresh_params()
    params.set("source.target.reflectance", 0.3)
    params.resolve()

    assert params.get("source.target.reflectance") == pytest.approx(
        0.3, abs=0.0
    )


@pytest.mark.level1
def test_albedo_scalar_accepted() -> None:
    """albedo = 0.25 resolves cleanly on the source schema."""
    params = _fresh_params()
    params.set("source.target.albedo", 0.25)
    params.resolve()

    assert params.get("source.target.albedo") == pytest.approx(
        0.25, abs=0.0
    )


@pytest.mark.level1
@pytest.mark.parametrize("bad_value", [-0.1, 1.5, 10.0])
def test_reflectance_rejects_out_of_bounds(bad_value: float) -> None:
    """ρ outside [0, 1] fails the schema bounds check."""
    params = _fresh_params()
    params.set("source.target.reflectance", bad_value)

    with pytest.raises(ValueError, match="out of bounds"):
        params.resolve()


@pytest.mark.level1
@pytest.mark.parametrize("bad_value", [-0.5, 2.0])
def test_albedo_rejects_out_of_bounds(bad_value: float) -> None:
    """albedo outside [0, 1] fails the schema bounds check."""
    params = _fresh_params()
    params.set("source.target.albedo", bad_value)

    with pytest.raises(ValueError, match="out of bounds"):
        params.resolve()


@pytest.mark.level1
def test_reflectance_path_accepted() -> None:
    """reflectance_path resolves as a plain string (CSV loader is Step 3.2)."""
    params = _fresh_params()
    params.set("source.target.reflectance_path", "scenes/reflectance.csv")
    params.resolve()

    assert (
        params.get("source.target.reflectance_path")
        == "scenes/reflectance.csv"
    )


@pytest.mark.level1
def test_reflectance_plus_albedo_raises() -> None:
    """Setting both surfaces over-specifies ρ; the validator must reject."""
    params = _fresh_params()
    params.set("source.target.reflectance", 0.3)
    params.set("source.target.albedo", 0.3)
    params.resolve()

    with pytest.raises(ParameterBoundsError, match="over-specified"):
        validate_reflectance_albedo_exclusive(params)


@pytest.mark.level1
def test_reflectance_scalar_plus_path_raises() -> None:
    """Scalar reflectance + reflectance_path together is ambiguous."""
    params = _fresh_params()
    params.set("source.target.reflectance", 0.3)
    params.set("source.target.reflectance_path", "rho.csv")
    params.resolve()

    with pytest.raises(ParameterBoundsError, match="over-specified"):
        validate_reflectance_albedo_exclusive(params)


@pytest.mark.level1
def test_single_reflectance_surface_passes_validator() -> None:
    """A single reflective surface (reflectance only) survives the check."""
    params = _fresh_params()
    params.set("source.target.reflectance", 0.25)
    params.resolve()

    # No exception.
    validate_reflectance_albedo_exclusive(params)


@pytest.mark.level1
def test_defaults_pass_validator() -> None:
    """With nothing set, the validator is a no-op."""
    params = _fresh_params()
    params.resolve()

    validate_reflectance_albedo_exclusive(params)
