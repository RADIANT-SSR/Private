"""Level-0 tests for the grazing (near-tangent) path-segment evaluator.

The optical path is validated in ``test_grazing_column.py``; what is tested
here is the *segment* contract — that this evaluator produces the same shape
of product as its two siblings, that it agrees with ``segment_simple`` where
both are valid (cross-model consistency), and that its directional radiance
split behaves.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.segment_grazing import (
    evaluate_grazing_segment,
    grazing_segment_optical_depth,
)
from radiant.atmosphere.segment_simple import (
    column_segment_optical_depth,
    evaluate_column_segment,
)
from radiant.atmosphere.segments import ColumnSegmentSpec, SegmentQuantities
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

H_ATM_TOP_M = 1.0e5


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(8.0, 13.0, 51)


@pytest.fixture
def atm() -> SimpleAtmosphere:
    return SimpleAtmosphere(standard_atmosphere="midlat_summer")


def _quiet(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return fn(*args, **kwargs)


class TestContract:
    @pytest.mark.level0
    def test_returns_a_valid_segment_product(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        """τ ∈ [0,1], both radiances ≥ 0, all three on the input grid."""
        q = evaluate_grazing_segment(
            atm,
            wl,
            r_tangent_m=R_EARTH_M + 5_000.0,
            h_low_m=5_000.0,
            h_high_m=H_ATM_TOP_M,
            zeta_low_rad=math.pi / 2.0,
        )
        assert isinstance(q, SegmentQuantities)
        assert q.tau.shape == wl.shape
        assert float(q.tau.min()) >= 0.0 and float(q.tau.max()) <= 1.0
        assert float(q.L_toward_upper.min()) >= 0.0
        assert float(q.L_toward_lower.min()) >= 0.0

    @pytest.mark.level0
    def test_thermal_only_split_is_symmetric(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        """With no sun the two directions are identical element-for-element:
        a segment has one temperature and one τ."""
        q = evaluate_grazing_segment(
            atm,
            wl,
            r_tangent_m=R_EARTH_M + 1_000.0,
            h_low_m=1_000.0,
            h_high_m=H_ATM_TOP_M,
            zeta_low_rad=math.pi / 2.0,
        )
        np.testing.assert_array_equal(q.L_toward_upper, q.L_toward_lower)

    @pytest.mark.level0
    def test_scattering_splits_the_two_directions(self, atm: SimpleAtmosphere) -> None:
        """A lit VIS arc scatters differently up and down (phase-angle flip)."""
        wl_vis = np.linspace(0.45, 0.75, 31)
        q = _quiet(
            evaluate_grazing_segment,
            atm,
            wl_vis,
            r_tangent_m=R_EARTH_M + 2_000.0,
            h_low_m=2_000.0,
            h_high_m=H_ATM_TOP_M,
            zeta_low_rad=math.pi / 2.0,
            theta_s_rad=0.6,
            delta_phi_rad=0.0,
        )
        assert not np.array_equal(q.L_toward_upper, q.L_toward_lower)

    @pytest.mark.level0
    def test_vacuum_above_the_column(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        q = evaluate_grazing_segment(
            atm,
            wl,
            r_tangent_m=R_EARTH_M + H_ATM_TOP_M,
            h_low_m=H_ATM_TOP_M,
            h_high_m=2.0 * H_ATM_TOP_M,
            zeta_low_rad=math.pi / 2.0,
        )
        np.testing.assert_array_equal(q.tau, np.ones_like(wl))
        np.testing.assert_array_equal(q.L_toward_upper, np.zeros_like(wl))


class TestCrossModelConsistency:
    @pytest.mark.level0
    @pytest.mark.parametrize("zenith_deg", [0.0, 30.0, 60.0])
    def test_agrees_with_the_column_model_where_both_are_valid(
        self, atm: SimpleAtmosphere, wl: np.ndarray, zenith_deg: float
    ) -> None:
        """Model A: exact spherical slant integral (this module).
        Model B: vertical column × plane-parallel-with-spherical-correction
        air mass (``segment_simple``).  Tolerance: 1 % on optical depth well
        inside the air-mass validity window.
        """
        h_low, h_high = 0.0, H_ATM_TOP_M
        z = math.radians(zenith_deg)
        r_tan = (R_EARTH_M + h_low) * math.sin(z)
        od_grazing, _ = grazing_segment_optical_depth(atm, wl, r_tan, h_low, h_high)
        od_column, _, _ = column_segment_optical_depth(
            atm, wl, ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=z)
        )
        np.testing.assert_allclose(od_grazing, od_column, rtol=0.01)

    @pytest.mark.level0
    def test_diverges_past_the_ceiling_and_the_grazing_form_is_larger(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """At 89° the air-mass form understates the true slant column by ~3×.

        This is the quantitative statement of *why* ``ColumnSegmentSpec``
        refuses past 89.5° and this module exists.  The factor is larger than
        the molecular-only ratio (≈ 2.4) because water vapour's 2 km scale
        height hugs the tangent point far more tightly than the 8 km molecular
        one — the per-species air mass is exactly what captures that.
        """
        z = math.radians(89.0)
        r_tan = R_EARTH_M * math.sin(z)
        od_grazing, _ = grazing_segment_optical_depth(atm, wl, r_tan, 0.0, H_ATM_TOP_M)
        od_column, _, _ = column_segment_optical_depth(
            atm, wl, ColumnSegmentSpec(h_low_m=0.0, h_high_m=H_ATM_TOP_M, zeta_low_rad=z)
        )
        ratio = float(np.median(od_grazing / od_column))
        assert 2.5 < ratio < 3.2

    @pytest.mark.level0
    def test_radiance_agrees_with_the_column_evaluator_at_moderate_zenith(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """The whole product (not just τ) agrees at 60°: same thermal model,
        same single-scatter model, only the path geometry differs."""
        z = math.radians(60.0)
        r_tan = R_EARTH_M * math.sin(z)
        grazing = evaluate_grazing_segment(
            atm, wl, r_tangent_m=r_tan, h_low_m=0.0, h_high_m=H_ATM_TOP_M, zeta_low_rad=z
        )
        column = evaluate_column_segment(
            atm, wl, ColumnSegmentSpec(h_low_m=0.0, h_high_m=H_ATM_TOP_M, zeta_low_rad=z)
        )
        np.testing.assert_allclose(grazing.tau, column.tau, rtol=0.01)
        np.testing.assert_allclose(
            grazing.L_toward_lower, column.L_toward_lower, rtol=0.02, atol=1e-6
        )


class TestFailureModes:
    @pytest.mark.level0
    @pytest.mark.parametrize("zeta_low_rad", [-0.1, math.pi / 2.0 + 1e-3, math.pi, float("nan")])
    def test_descending_or_invalid_zenith_raises(
        self, atm: SimpleAtmosphere, wl: np.ndarray, zeta_low_rad: float
    ) -> None:
        """Only ascending arcs — a descending one is a limb transit (declined)."""
        with pytest.raises(ParameterBoundsError):
            evaluate_grazing_segment(
                atm,
                wl,
                r_tangent_m=R_EARTH_M,
                h_low_m=0.0,
                h_high_m=H_ATM_TOP_M,
                zeta_low_rad=zeta_low_rad,
            )

    @pytest.mark.level0
    def test_bad_h_atm_top_raises(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        with pytest.raises(ParameterBoundsError, match="positive-finite"):
            evaluate_grazing_segment(
                atm,
                wl,
                r_tangent_m=R_EARTH_M,
                h_low_m=0.0,
                h_high_m=H_ATM_TOP_M,
                zeta_low_rad=0.0,
                h_atm_top_m=0.0,
            )

    @pytest.mark.level0
    def test_bad_wavelength_grid_raises(self, atm: SimpleAtmosphere) -> None:
        with pytest.raises(ParameterBoundsError):
            evaluate_grazing_segment(
                atm,
                np.array([2.0, 1.0, 3.0]),
                r_tangent_m=R_EARTH_M,
                h_low_m=0.0,
                h_high_m=H_ATM_TOP_M,
                zeta_low_rad=0.0,
            )
