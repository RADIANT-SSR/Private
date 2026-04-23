"""Tests for the Q3 shape-wiring path through ``_inferrer``.

Step 1.2 of the Target Definition Matrix Implementation Plan: the
inferrer now builds a concrete ``TargetShape`` from the flattened
``source.target.shape*`` scalars (registered in Step 1.1) and attaches
it to the assembled ``TargetDescriptor``.  When a user supplies both a
``shape`` and ``projected_area_m2`` > 0, the shape wins and a
``UserWarning`` fires (Rule 17).

Truth anchors
-------------
Three analytic anchors validate the shape-factory + inferrer wiring
against closed-form projected-area identities from the §3 catalog:

1. **Sphere** — ``A_proj = π r²`` regardless of view direction
   (orientation-invariant).
2. **Cylinder side view** — ``A_proj = 2 r L`` when the cylinder axis
   lies perpendicular to the view direction.
3. **Flat plate** — ``A_proj = W·H`` when the plate normal is parallel
   to the view direction; ``A_proj = 0`` when edge-on.

See the shape catalog in
[docs/RADIANT_Target_Definition_Matrix.md §3](../../../../docs/RADIANT_Target_Definition_Matrix.md)
for the identities the scalars mirror.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

# Full parameter schema (pull the full schema so ``_infer_los`` can
# read ``geometry.target_altitude_m`` without KeyError fallbacks).
from radiant.api._param_registry import build_parameter_set
from radiant.core.parameters import ParameterBoundsError
from radiant.io.config import load_config
from radiant.source._inferrer import infer_descriptors
from radiant.source._schema import ALL_PARAMETERS as SRC_PARAMS
from radiant.source.resolvers.shape_factory import build_shape
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere

REPO_ROOT = Path(__file__).resolve().parents[4]
_LWIR_TEMPLATE = REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_WL_LWIR = np.linspace(8.0, 13.0, 11)


def _base_params():  # type: ignore[no-untyped-def]
    """Return a ParameterSet seeded from the LWIR aerial template.

    The template supplies the optics consistency-group inputs
    (aperture_diameter_m, focal_length_m) so ``resolve()`` does not trip
    the optics cycle check.  Matches the pattern used by
    [test_inferrer.py](test_inferrer.py).
    """
    params = build_parameter_set()
    load_config(_LWIR_TEMPLATE, params)
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "simple")
    return params


# ---------------------------------------------------------------------------
# Truth Anchor 1: Sphere — A_proj = π r²
# ---------------------------------------------------------------------------


class TestTruthAnchorSphere:
    """Sphere projected area is π r² regardless of view (closed form)."""

    def test_sphere_descriptor_is_sphere_and_area_is_pi_rsq(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "sphere")
        params.set("source.target.shape_radius_m", 1.0)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, Sphere)
        assert target.A_t == pytest.approx(math.pi, rel=1e-12, abs=0.0)


# ---------------------------------------------------------------------------
# Truth Anchor 2: Cylinder side view — A_proj = 2 r L
# ---------------------------------------------------------------------------


class TestTruthAnchorCylinderSide:
    """Cylinder viewed with axis perpendicular to view: A = 2 r L."""

    def test_cylinder_side_view_is_two_r_l(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "cylinder")
        params.set("source.target.shape_radius_m", 1.0)
        params.set("source.target.shape_length_m", 10.0)
        # Rotate body +Z (cylinder axis) to scene +X so the nadir view
        # (scene +Z) sees the cylinder broadside.  ZYX Euler with
        # pitch = π/2 takes body +Z → scene +X.
        params.set("source.target.shape_pitch_rad", math.pi / 2.0)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, Cylinder)
        assert target.A_t == pytest.approx(20.0, rel=1e-12, abs=1e-12)


# ---------------------------------------------------------------------------
# Truth Anchor 3: Flat plate — normal view W·H, edge view 0
# ---------------------------------------------------------------------------


class TestTruthAnchorFlatPlate:
    """Flat plate: A = W·H at normal incidence, 0 edge-on."""

    def test_flat_plate_normal_view_is_wh(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "flat_plate")
        params.set("source.target.shape_length_m", 2.0)
        params.set("source.target.shape_width_m", 3.0)
        # Default orientation (0,0,0): body +Z = scene +Z; nadir view
        # aligns with plate normal so A = L·W.
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, FlatPlate)
        assert target.A_t == pytest.approx(6.0, rel=1e-12, abs=0.0)

    def test_flat_plate_edge_view_is_zero(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "flat_plate")
        params.set("source.target.shape_length_m", 2.0)
        params.set("source.target.shape_width_m", 3.0)
        # Rotate plate normal (body +Z) to scene +X via pitch=π/2.
        # Nadir view (scene +Z) now hits the edge: A = 0.
        params.set("source.target.shape_pitch_rad", math.pi / 2.0)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, FlatPlate)
        # Edge-on: A collapses to 0 up to float noise from sin(π/2)·cos(π/2).
        assert target.A_t is None or target.A_t == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Q3 precedence: shape wins over projected_area_m2 with a UserWarning
# ---------------------------------------------------------------------------


class TestQ3Precedence:
    def test_shape_and_area_conflict_emits_single_warning(self) -> None:
        """Both shape + projected_area_m2 → exactly one ``shape.*wins`` warning."""
        params = _base_params()
        params.set("source.target.shape", "sphere")
        params.set("source.target.shape_radius_m", 1.0)
        params.set("source.target.projected_area_m2", 5.0)
        params.resolve()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        shape_wins = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "shape" in str(w.message).lower()
            and "wins" in str(w.message).lower()
        ]
        assert len(shape_wins) == 1, (
            f"Expected exactly one shape-wins UserWarning, got "
            f"{len(shape_wins)}: {[str(w.message) for w in shape_wins]}"
        )
        # Shape instance landed on the descriptor, and A_t reflects
        # shape.projected_area (π), not the user-supplied 5.0.
        assert isinstance(target.shape, Sphere)
        assert target.A_t == pytest.approx(math.pi, rel=1e-12, abs=0.0)

    def test_no_shape_uses_projected_area_no_warning(self) -> None:
        """Back-compat: shape='none' keeps projected_area_m2 and emits no warning."""
        params = _base_params()
        params.set("source.target.projected_area_m2", 5.0)
        params.resolve()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        shape_wins = [
            w
            for w in caught
            if issubclass(w.category, UserWarning)
            and "shape" in str(w.message).lower()
            and "wins" in str(w.message).lower()
        ]
        assert shape_wins == []
        assert target.shape is None
        assert target.A_t == pytest.approx(5.0, rel=1e-12, abs=0.0)


# ---------------------------------------------------------------------------
# Shape-factory validation — Rule 15 ParameterBoundsError
# ---------------------------------------------------------------------------


class TestShapeFactoryValidation:
    def test_sphere_zero_radius_raises_parameter_bounds_error(self) -> None:
        """shape='sphere' with radius sentinel (0.0) → ParameterBoundsError."""
        params = _base_params()
        params.set("source.target.shape", "sphere")
        # shape_radius_m left at the default sentinel 0.0.
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="shape_radius_m"):
            build_shape(params)

    def test_sphere_negative_radius_rejected_at_schema(self) -> None:
        """Negative radius fails earlier, at schema bounds (Step 1.1 contract)."""
        params = _base_params()
        params.set("source.target.shape_radius_m", -1.0)

        with pytest.raises(ValueError, match="out of bounds"):
            params.resolve()


# ---------------------------------------------------------------------------
# Cone and Box — factory produces the right concrete type
# ---------------------------------------------------------------------------


class TestAdditionalShapes:
    def test_cone_descriptor_is_cone(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "cone")
        params.set("source.target.shape_base_radius_m", 1.0)
        params.set("source.target.shape_height_m", 2.0)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, Cone)
        # Smoke: cone projected area is positive under nadir view.
        assert target.A_t is not None and target.A_t > 0.0

    def test_box_descriptor_is_box(self) -> None:
        params = _base_params()
        params.set("source.target.shape", "box")
        params.set("source.target.shape_length_m", 1.0)
        params.set("source.target.shape_width_m", 2.0)
        params.set("source.target.shape_height_m", 3.0)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _, _ = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target.shape, Box)
        # Nadir view sees the top face (L·W = 2 m²) plus the 0-cosine
        # side faces; the box projected-area formula in body frame is
        # L·W at pitch=0 when v_body = (0,0,1).
        assert target.A_t == pytest.approx(2.0, rel=1e-12, abs=0.0)


# ---------------------------------------------------------------------------
# Factory unit test: pure dispatch without the inferrer
# ---------------------------------------------------------------------------


class TestShapeFactoryDispatch:
    @pytest.mark.parametrize(
        "shape_name, dims, expected_type",
        [
            ("sphere", {"shape_radius_m": 1.0}, Sphere),
            (
                "cylinder",
                {"shape_radius_m": 1.0, "shape_length_m": 2.0},
                Cylinder,
            ),
            (
                "flat_plate",
                {"shape_length_m": 1.0, "shape_width_m": 2.0},
                FlatPlate,
            ),
            (
                "box",
                {
                    "shape_length_m": 1.0,
                    "shape_width_m": 2.0,
                    "shape_height_m": 3.0,
                },
                Box,
            ),
            (
                "cone",
                {"shape_base_radius_m": 1.0, "shape_height_m": 2.0},
                Cone,
            ),
        ],
    )
    def test_factory_dispatches_every_catalog_shape(
        self,
        shape_name: str,
        dims: dict[str, float],
        expected_type: type,
    ) -> None:
        """build_shape produces the matching concrete class for every enum."""
        # Source-only ParameterSet is sufficient — the factory only
        # touches source.target.shape* scalars.
        from radiant.core.parameters import ParameterSet

        params = ParameterSet(list(SRC_PARAMS))
        params.set("source.target.shape", shape_name)
        for key, value in dims.items():
            params.set(f"source.target.{key}", value)
        params.resolve()

        result = build_shape(params)
        assert isinstance(result, expected_type)

    def test_factory_none_on_shape_sentinel(self) -> None:
        """build_shape returns None when shape='none' (back-compat)."""
        from radiant.core.parameters import ParameterSet

        params = ParameterSet(list(SRC_PARAMS))
        params.resolve()

        assert build_shape(params) is None
