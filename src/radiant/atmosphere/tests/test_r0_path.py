r"""Level-0 tests for the path-weighted Fried parameter (Gap 110).

The five task truth anchors live here:

1. HV-5/7 vertical r₀ at 0.5 µm = 4.8–5.2 cm (literature 5 cm);
2. ``r0 ∝ λ^(6/5)`` exactly;
3. ``r0 ∝ sec(ζ)^(-3/5)`` exactly for a fixed profile;
4. the vacuum / space-observer limit — a finite huge r₀, never an error;
5. a tabulated profile fed HV samples reproduces the HV preset (round-trip).

plus the level-arm closed form, the wave-type weighting direction, and the
failure modes.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.cn2_hufnagel_valley import HufnagelValleyCn2
from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile
from radiant.atmosphere.protocol import ZENITH_CEILING_RAD
from radiant.atmosphere.r0_path import (
    R0_NEGLIGIBLE_M,
    SPHERICAL_LEVEL_WEIGHT,
    fried_parameter_from_integral_m,
    path_fried_parameter_from_los,
)
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.viewing_triangle import solve_from_lower_zenith

VIS_M = 0.5e-6
HV = HufnagelValleyCn2()

#: HV-5/7 vertical, ground sensor, plane wave, 0.5 µm — recomputed here at
#: full precision so the scaling tests have an exact reference.
_HV_ZENITH_R0_M = 0.04960567060977687


def _uplooking(zeta_low_rad: float, h_sensor: float = 0.0, h_tgt: float = 800.0e3):
    """Up-looking LOS with the requested SENSOR-side (lower-endpoint) zenith."""
    if zeta_low_rad == 0.0:
        return LineOfSightGeometry(h_tgt=h_tgt, h_sensor=h_sensor, theta_o=math.pi)
    sol = solve_from_lower_zenith(zeta_low_rad, h_sensor, h_tgt)
    return LineOfSightGeometry(h_tgt=h_tgt, h_sensor=h_sensor, theta_o=sol.theta_o_rad)


def _level(altitude_m: float, arm_m: float) -> LineOfSightGeometry:
    phi = arm_m / (R_EARTH_M + altitude_m)
    return LineOfSightGeometry(
        h_tgt=altitude_m, h_sensor=altitude_m, theta_o=math.pi / 2.0 + phi / 2.0
    )


# ---------------------------------------------------------------------------
# Truth anchors
# ---------------------------------------------------------------------------


class TestTruthAnchors:
    @pytest.mark.level0
    def test_anchor1_hv57_zenith_r0_is_5cm(self) -> None:
        """HV-5/7, vertical, 0.5 µm → r₀ ≈ 5 cm (Andrews & Phillips 2005 §12.2.2)."""
        r = path_fried_parameter_from_los(_uplooking(0.0), HV, VIS_M)
        assert 0.048 <= r.r0_m <= 0.052, f"r0 = {r.r0_m * 100:.4f} cm"
        assert r.negligible is False
        assert r.zeta_low_rad == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.level0
    def test_anchor2_r0_scales_as_lambda_to_the_6_5(self) -> None:
        """r₀ ∝ λ^(6/5) is exact — the same integral, a different k."""
        los = _uplooking(0.0)
        base = path_fried_parameter_from_los(los, HV, VIS_M).r0_m
        for lam_m in (1.064e-6, 1.55e-6, 4.0e-6, 10.0e-6):
            r = path_fried_parameter_from_los(los, HV, lam_m).r0_m
            assert r / base == pytest.approx((lam_m / VIS_M) ** 1.2, rel=1e-12)

    @pytest.mark.level0
    def test_anchor2_integral_is_wavelength_independent(self) -> None:
        """All the wavelength dependence sits in k, none in the path integral."""
        los = _uplooking(0.0)
        a = path_fried_parameter_from_los(los, HV, VIS_M)
        b = path_fried_parameter_from_los(los, HV, 4.0e-6)
        assert a.cn2_path_integral_m13 == pytest.approx(b.cn2_path_integral_m13, rel=1e-15)

    @pytest.mark.level0
    @pytest.mark.parametrize("zeta_deg", [0.0, 15.0, 30.0, 45.0, 60.0, 80.0, 89.0])
    def test_anchor3_r0_scales_as_sec_zeta_to_the_minus_3_5(self, zeta_deg: float) -> None:
        """Fixed profile → r₀(ζ) = r₀(0)·sec(ζ)^(-3/5), exactly."""
        zeta = math.radians(zeta_deg)
        r = path_fried_parameter_from_los(_uplooking(zeta), HV, VIS_M)
        expected = _HV_ZENITH_R0_M * (1.0 / math.cos(zeta)) ** (-3.0 / 5.0)
        assert r.r0_m == pytest.approx(expected, rel=1e-9)

    @pytest.mark.level0
    def test_anchor4_space_observer_gives_a_finite_huge_r0_not_an_error(self) -> None:
        """LEO sensor → GEO target: the whole path is vacuum.

        This is the case ``RADIANT_Atmosphere.md`` used to reject outright
        ("the parameter resolver rejects turbulence for a space observer with
        a ScopeError"). ADR-0011 guardrail G4: the generalization retires the
        carve-out — the answer is a number, not a refusal.
        """
        los = LineOfSightGeometry(h_tgt=35_786.0e3, h_sensor=500.0e3, theta_o=math.pi)
        r = path_fried_parameter_from_los(los, HV, VIS_M)
        assert math.isfinite(r.r0_m)
        assert r.r0_m == R0_NEGLIGIBLE_M
        assert r.negligible is True
        assert r.cn2_path_integral_m13 == 0.0

    @pytest.mark.level0
    def test_anchor4_residual_column_above_20km_is_metres_of_r0(self) -> None:
        """A 20 km sensor sees only the residual column: r₀ of order metres.

        Independent check: ∫₂₀ᵏᵐ^¹⁰⁰ᵏᵐ Cn²_HV dh = 1.4104e-15 m^(1/3), giving
        r₀ = 4.126 m at 0.5 µm.  (The Phase-3 task text quoted "> 5 m"; the
        HV-5/7 jet-stream tail is slightly stronger than that, and 4.1 m is
        the value the published profile actually produces — see the task
        report.)  At 4.1 m the Kolmogorov MTF at the cutoff of a 0.3 m
        aperture is 0.96, i.e. turbulence is a sub-5 % effect.
        """
        los = _uplooking(0.0, h_sensor=20.0e3)
        r = path_fried_parameter_from_los(los, HV, VIS_M)
        assert r.r0_m == pytest.approx(4.126, rel=1e-3)
        assert r.negligible is False
        assert r.r0_m > 3.0

    @pytest.mark.level0
    def test_anchor5_tabulated_profile_round_trips_the_hv_preset(self) -> None:
        """Sampling HV and re-integrating the table reproduces r₀ to < 0.1 %."""
        h = np.concatenate([np.linspace(0.0, 2000.0, 200), np.linspace(2000.0, 100_000.0, 200)[1:]])
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HV.cn2(h), label="hv-samples")
        los = _uplooking(0.0)
        analytic = path_fried_parameter_from_los(los, HV, VIS_M).r0_m
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # the table spans the whole path: no warning
            tabulated = path_fried_parameter_from_los(los, table, VIS_M).r0_m
        assert tabulated == pytest.approx(analytic, rel=1e-3)


# ---------------------------------------------------------------------------
# Direction awareness and weighting
# ---------------------------------------------------------------------------


class TestDirectionAndWeighting:
    @pytest.mark.level0
    def test_ground_sensor_integrates_the_full_column(self) -> None:
        ground = path_fried_parameter_from_los(_uplooking(0.0, h_sensor=0.0), HV, VIS_M)
        assert ground.h_low_m == 0.0
        assert ground.h_high_m == 1.0e5

    @pytest.mark.level0
    def test_airborne_sensor_integrates_a_partial_column_and_sees_better(self) -> None:
        """Climbing above the surface layer must increase r₀ monotonically."""
        previous = 0.0
        for h_sensor in (0.0, 500.0, 3000.0, 10_000.0, 20_000.0):
            r = path_fried_parameter_from_los(_uplooking(0.0, h_sensor=h_sensor), HV, VIS_M)
            assert r.r0_m > previous
            previous = r.r0_m

    @pytest.mark.level0
    def test_downlooking_plane_wave_matches_the_uplooking_column(self) -> None:
        """Plane-wave weighting is endpoint-symmetric: same slab, same integral."""
        up = path_fried_parameter_from_los(_uplooking(0.0), HV, VIS_M)
        down = LineOfSightGeometry(h_tgt=0.0, h_sensor=500.0e3, theta_o=0.0)
        assert path_fried_parameter_from_los(down, HV, VIS_M).r0_m == pytest.approx(
            up.r0_m, rel=1e-12
        )

    @pytest.mark.level0
    def test_spherical_weighting_favours_the_aperture_end(self) -> None:
        """Turbulence near the sensor dominates — the documented convention.

        Ground sensor / space target: the atmosphere sits at the *aperture*
        end, so the spherical weight is ≈ 1 there and the answer is close to
        the plane-wave one.  Space sensor / ground target: the same slab now
        sits at the *source* end, the weight collapses, and r₀ becomes far
        larger.
        """
        up = _uplooking(0.0)
        down = LineOfSightGeometry(h_tgt=0.0, h_sensor=500.0e3, theta_o=0.0)
        up_plane = path_fried_parameter_from_los(up, HV, VIS_M).r0_m
        up_sph = path_fried_parameter_from_los(up, HV, VIS_M, "spherical").r0_m
        down_sph = path_fried_parameter_from_los(down, HV, VIS_M, "spherical").r0_m
        assert up_sph == pytest.approx(up_plane, rel=0.02)
        assert down_sph > 100.0 * up_sph

    @pytest.mark.level0
    def test_spherical_weight_never_exceeds_the_plane_wave_integral(self) -> None:
        """W = u^(5/3) ∈ [0, 1] ⇒ the weighted integral can only shrink."""
        for los in (_uplooking(0.0), LineOfSightGeometry(h_tgt=0.0, h_sensor=8.0e3, theta_o=0.0)):
            plane = path_fried_parameter_from_los(los, HV, VIS_M)
            sph = path_fried_parameter_from_los(los, HV, VIS_M, "spherical")
            assert sph.cn2_path_integral_m13 <= plane.cn2_path_integral_m13
            assert sph.r0_m >= plane.r0_m


class TestLevelArm:
    @pytest.mark.level0
    def test_level_arm_uses_the_closed_form_not_an_airmass(self) -> None:
        """∫ = Cn²(h)·L for a plane wave — no sec(π/2) anywhere."""
        arm_m = 20_000.0
        altitude = 3000.0
        los = _level(altitude, arm_m)
        r = path_fried_parameter_from_los(los, HV, 4.0e-6)
        cn2_here = float(HV.cn2(np.array([altitude]))[0])
        chord = 2.0 * (R_EARTH_M + altitude) * math.sin(arm_m / (R_EARTH_M + altitude) / 2.0)
        assert r.cn2_path_integral_m13 == pytest.approx(cn2_here * chord, rel=1e-9)
        assert r.zeta_low_rad == pytest.approx(math.pi / 2.0, abs=1e-15)
        assert r.h_low_m == r.h_high_m == altitude

    @pytest.mark.level0
    def test_level_arm_spherical_weight_is_three_eighths(self) -> None:
        """∫₀¹ u^(5/3) du = 3/8 exactly."""
        los = _level(3000.0, 20_000.0)
        plane = path_fried_parameter_from_los(los, HV, 4.0e-6)
        sph = path_fried_parameter_from_los(los, HV, 4.0e-6, "spherical")
        assert sph.cn2_path_integral_m13 == pytest.approx(
            SPHERICAL_LEVEL_WEIGHT * plane.cn2_path_integral_m13, rel=1e-12
        )

    @pytest.mark.level0
    def test_level_arm_r0_scales_with_length_to_the_minus_3_5(self) -> None:
        short = path_fried_parameter_from_los(_level(3000.0, 10_000.0), HV, 4.0e-6).r0_m
        long = path_fried_parameter_from_los(_level(3000.0, 40_000.0), HV, 4.0e-6).r0_m
        assert long / short == pytest.approx(4.0 ** (-3.0 / 5.0), rel=1e-6)

    @pytest.mark.level0
    def test_level_arm_above_the_atmosphere_is_negligible(self) -> None:
        r = path_fried_parameter_from_los(_level(2.0e5, 50_000.0), HV, VIS_M)
        assert r.negligible is True
        assert r.r0_m == R0_NEGLIGIBLE_M


# ---------------------------------------------------------------------------
# Reduction, coverage and failure modes
# ---------------------------------------------------------------------------


class TestReduction:
    @pytest.mark.level0
    def test_reduction_matches_the_closed_form(self) -> None:
        k = 2.0 * math.pi / VIS_M
        integral = 2.0e-12
        expected = (0.423 * k * k * integral) ** (-3.0 / 5.0)
        assert fried_parameter_from_integral_m(integral, VIS_M) == pytest.approx(
            expected, rel=1e-14
        )

    @pytest.mark.level0
    def test_cross_model_against_the_coherence_radius_formulation(self) -> None:
        """Independent literature route to the same number, to 0.2 %.

        Andrews & Phillips write the plane-wave **spatial coherence radius**
        as ρ₀ = [1.46 k² ∫ Cn² dz]^(-3/5) and relate it to the Fried parameter
        by r₀ = 2.1 ρ₀.  That is a different constant pair from the 0.423 this
        module uses, and the two must agree:
        ``2.1 · 1.46^(-3/5) = 1.6739`` vs ``0.423^(-3/5) = 1.6714``.
        """
        k = 2.0 * math.pi / VIS_M
        integral = 2.2354e-12  # the HV-5/7 vertical column
        ours = fried_parameter_from_integral_m(integral, VIS_M)
        theirs = 2.1 * (1.46 * k * k * integral) ** (-3.0 / 5.0)
        assert ours == pytest.approx(theirs, rel=2e-3)

    @pytest.mark.level0
    def test_zero_integral_saturates_rather_than_returning_inf(self) -> None:
        value = fried_parameter_from_integral_m(0.0, VIS_M)
        assert math.isfinite(value)
        assert value == R0_NEGLIGIBLE_M

    @pytest.mark.level0
    def test_negative_integral_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="negative or non-finite"):
            fried_parameter_from_integral_m(-1.0e-12, VIS_M)

    @pytest.mark.level0
    def test_non_positive_wavelength_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="wavelength_m"):
            fried_parameter_from_integral_m(1.0e-12, 0.0)


class TestCoverageWarning:
    @pytest.mark.level0
    def test_short_table_warns_and_reports_an_upper_bound(self) -> None:
        h = np.linspace(0.0, 5000.0, 51)
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HV.cn2(h), label="short")
        with pytest.warns(UserWarning, match="outside the table"):
            r = path_fried_parameter_from_los(_uplooking(0.0), table, VIS_M)
        full = path_fried_parameter_from_los(_uplooking(0.0), HV, VIS_M)
        assert r.r0_m > full.r0_m  # the missing slabs can only help seeing

    @pytest.mark.level0
    def test_full_coverage_does_not_warn(self) -> None:
        h = np.linspace(0.0, 100_000.0, 501)
        table = TabulatedCn2Profile(altitude_m=h, cn2_m23=HV.cn2(h), label="full")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            path_fried_parameter_from_los(_uplooking(0.0), table, VIS_M)


class TestFailureModes:
    @pytest.mark.level0
    def test_missing_sensor_endpoint_rejected(self) -> None:
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.3)
        with pytest.raises(ParameterBoundsError, match="h_sensor is None"):
            path_fried_parameter_from_los(los, HV, VIS_M)

    @pytest.mark.level0
    def test_unknown_wave_type_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="wave_type"):
            path_fried_parameter_from_los(_uplooking(0.0), HV, VIS_M, "gaussian")

    @pytest.mark.level0
    def test_non_positive_wavelength_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="wavelength_m"):
            path_fried_parameter_from_los(_uplooking(0.0), HV, -1.0)

    @pytest.mark.level0
    def test_horizon_guard_fires_before_the_airmass_ceiling_is_reached(self) -> None:
        """No LOS can present ζ_low past 89.5°: the Phase-1 guard raises first.

        The ±0.5° hard horizon guard on ``LineOfSightGeometry`` /
        ``solve_from_lower_zenith`` coincides with the atmosphere's
        ``ZENITH_CEILING_RAD`` (89.5°), so the ``sec(ζ)`` divergence is
        unreachable through a validated scene.  The ceiling check inside
        ``path_fried_parameter_from_los`` is therefore defence-in-depth for
        hand-built callers and for any future relaxation of the guard; the
        *observable* behaviour a user gets is this one.
        """
        assert pytest.approx(math.radians(89.5), rel=1e-12) == ZENITH_CEILING_RAD
        with pytest.raises(ParameterBoundsError, match="horizon guard"):
            _uplooking(ZENITH_CEILING_RAD + math.radians(0.2), h_sensor=0.0, h_tgt=20_000.0)

    @pytest.mark.level0
    def test_at_the_ceiling_the_integral_still_computes(self) -> None:
        """ζ_low = 89.5° exactly is inside the warn shoulder and must compute."""
        with pytest.warns(UserWarning, match="near-horizontal"):
            los = _uplooking(ZENITH_CEILING_RAD, h_sensor=0.0, h_tgt=20_000.0)
        r = path_fried_parameter_from_los(los, HV, VIS_M)
        assert math.isfinite(r.r0_m)
        assert r.r0_m > 0.0

    @pytest.mark.level0
    def test_reproducible(self) -> None:
        los = _uplooking(math.radians(45.0))
        a = path_fried_parameter_from_los(los, HV, VIS_M)
        b = path_fried_parameter_from_los(los, HV, VIS_M)
        assert a.r0_m == b.r0_m
        assert a.cn2_path_integral_m13 == b.cn2_path_integral_m13
