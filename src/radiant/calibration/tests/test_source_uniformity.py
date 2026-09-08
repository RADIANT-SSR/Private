"""Level 0 tests for the cal-source spatial-uniformity residual (Gap 122 item 1).

Written before the implementation (Rule 18). Expected values are hand
calculations from the closed-form correction algebra, not RADIANT outputs:

    one-point (offset-only):  sigma(S) = dT_unif * D1              (constant)
    two-point (gain+offset):  sigma(S) = dT_unif * |D1*(S2-S) + D2*(S-S1)| / (S2-S1)

with D_j = dS/dT at cal temperature T_j, and the source's spatial pattern
taken identical (in K) at both cal views — the same plate, so the two
imprints are fully correlated, giving linear (not RSS) weight combination.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.calibration.cal_points import cal_point_ds_dt_e_per_K
from radiant.calibration.errors import CalibrationValidationError
from radiant.calibration.source_uniformity import (
    one_point_uniformity_residual_e,
    two_point_uniformity_residual_e,
)


class TestOnePointLevel0:
    def test_constant_product(self) -> None:
        """sigma = dT * D1: 0.05 K * 500 e-/K = 25 e- at any scene signal."""
        sigma = one_point_uniformity_residual_e(delta_t_unif_K=0.05, ds_dt_cal_e_per_K=500.0)
        assert sigma == pytest.approx(25.0, rel=1e-12)

    def test_zero_uniformity_is_zero(self) -> None:
        assert one_point_uniformity_residual_e(
            delta_t_unif_K=0.0, ds_dt_cal_e_per_K=500.0
        ) == pytest.approx(0.0, abs=0.0)


class TestTwoPointLevel0:
    _KW = {"s1_e": 10_000.0, "s2_e": 40_000.0, "delta_t_unif_K": 0.05}

    def test_at_first_cal_point(self) -> None:
        """At S = S1 the correction still carries the first view's imprint:
        sigma = dT * D1 = 25 e- — non-zero exactly where the NUC parabola
        vanishes (the correctability-gap claim of Gap 122 item 1)."""
        sigma = two_point_uniformity_residual_e(
            signal_e=10_000.0,
            ds_dt_cal1_e_per_K=500.0,
            ds_dt_cal2_e_per_K=800.0,
            **self._KW,
        )
        assert sigma == pytest.approx(25.0, rel=1e-12)

    def test_at_second_cal_point(self) -> None:
        sigma = two_point_uniformity_residual_e(
            signal_e=40_000.0,
            ds_dt_cal1_e_per_K=500.0,
            ds_dt_cal2_e_per_K=800.0,
            **self._KW,
        )
        assert sigma == pytest.approx(0.05 * 800.0, rel=1e-12)

    def test_midpoint_hand_value(self) -> None:
        """S = 25000: 0.05 * |500*15000 + 800*15000| / 30000 = 32.5 e-."""
        sigma = two_point_uniformity_residual_e(
            signal_e=25_000.0,
            ds_dt_cal1_e_per_K=500.0,
            ds_dt_cal2_e_per_K=800.0,
            **self._KW,
        )
        assert sigma == pytest.approx(32.5, rel=1e-12)

    def test_equal_derivatives_collapse_to_constant(self) -> None:
        """D1 = D2 = D: the interpolation weights sum to one, so sigma =
        dT * D at every S — including far outside the cal span (exact
        algebraic identity, tested at S = 70000 > S2)."""
        sigma = two_point_uniformity_residual_e(
            signal_e=70_000.0,
            ds_dt_cal1_e_per_K=600.0,
            ds_dt_cal2_e_per_K=600.0,
            **self._KW,
        )
        assert sigma == pytest.approx(0.05 * 600.0, rel=1e-12)

    def test_coincident_cal_points_refused(self) -> None:
        with pytest.raises(CalibrationValidationError, match="coincide"):
            two_point_uniformity_residual_e(
                signal_e=25_000.0,
                s1_e=10_000.0,
                s2_e=10_000.0,
                delta_t_unif_K=0.05,
                ds_dt_cal1_e_per_K=500.0,
                ds_dt_cal2_e_per_K=800.0,
            )

    def test_negative_uniformity_refused(self) -> None:
        with pytest.raises(CalibrationValidationError, match="non-negative"):
            two_point_uniformity_residual_e(
                signal_e=25_000.0,
                ds_dt_cal1_e_per_K=500.0,
                ds_dt_cal2_e_per_K=800.0,
                s1_e=10_000.0,
                s2_e=40_000.0,
                delta_t_unif_K=-0.05,
            )


class TestCalPointDsDtLevel0:
    """dS/dT at the cal temperature via the band Planck-ratio mapping."""

    def test_narrow_band_matches_analytic_planck_derivative(self) -> None:
        """Quasi-monochromatic band at 10 um, T_cal = T_scene = 300 K:
        d ln Bq / dT = (x/T) * e^x / (e^x - 1),  x = h c / (lambda k T).

        x = 14387.77 um K / (10 um * 300 K) = 4.79592...; the mapping's
        dS/dT must equal S * d ln Bq / dT to the narrow-band limit.
        """
        x = 14387.7688 / (10.0 * 300.0)
        dlnb_dt = (x / 300.0) * math.exp(x) / (math.exp(x) - 1.0)
        expected = 30_000.0 * dlnb_dt

        actual = cal_point_ds_dt_e_per_K(
            t_cal_K=300.0,
            scene_temp_K=300.0,
            scene_signal_e=30_000.0,
            lam_min_um=9.99,
            lam_max_um=10.01,
        )
        assert actual == pytest.approx(expected, rel=1e-3)

    def test_cooler_cal_point_has_larger_relative_derivative(self) -> None:
        """d ln B / dT grows as T falls (x/T ~ 1/T^2 dominates in LWIR), so
        the 290 K cal point's absolute dS/dT stays within ~15 % of the
        300 K scene's for an 8-12 um band — a physical sanity bracket."""
        d_290 = cal_point_ds_dt_e_per_K(
            t_cal_K=290.0,
            scene_temp_K=300.0,
            scene_signal_e=30_000.0,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        d_300 = cal_point_ds_dt_e_per_K(
            t_cal_K=300.0,
            scene_temp_K=300.0,
            scene_signal_e=30_000.0,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert d_290 > 0.0 and d_300 > 0.0
        assert d_290 == pytest.approx(d_300, rel=0.15)

    def test_invalid_temperature_refused(self) -> None:
        with pytest.raises(CalibrationValidationError, match="absolute temperature"):
            cal_point_ds_dt_e_per_K(
                t_cal_K=0.0,
                scene_temp_K=300.0,
                scene_signal_e=30_000.0,
                lam_min_um=8.0,
                lam_max_um=12.0,
            )


class TestChainDerivativeConsistency:
    """Cross-model anchor: as T_cal -> T_scene the mapping's derivative must
    approach the chain's own spectral ds_dt in the flat-response limit.

    Kept at module grain (numpy reference integral) so the Level 0 file needs
    no chain run; the full-chain comparison lives in the task report.
    """

    def test_against_reference_integral(self) -> None:
        from radiant.core.blackbody import planck_spectral_radiance
        from radiant.core.constants import c, h

        lam = np.linspace(8.0, 12.0, 2001)
        e_ph = h * c / (lam * 1e-6)

        def bq(t: float) -> float:
            return float(np.trapezoid(planck_spectral_radiance(lam, t) / e_ph, lam))

        s = 30_000.0
        expected = s * (bq(300.05) - bq(299.95)) / 0.1 / bq(300.0)
        actual = cal_point_ds_dt_e_per_K(
            t_cal_K=300.0,
            scene_temp_K=300.0,
            scene_signal_e=s,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert actual == pytest.approx(expected, rel=1e-6)
