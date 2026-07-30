"""Level-0 tests for the Hufnagel-Valley Cn²(h) profile (Gap 110).

Truth anchors are the published HV-5/7 parameters and the hand-evaluated
three-term formula (Andrews & Phillips 2005 §12.2.2 Eq. 12.30; Beland 1993
§2.3).  The two integral anchors — r₀ = 5 cm and θ₀ = 7 µrad at 0.5 µm for a
vertical path — live here as *profile* validation, computed with an
independent quadrature written in the test rather than with RADIANT's
integrator (Rule 18).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.cn2_hufnagel_valley import (
    HV_5_7_GROUND_STRENGTH_M23,
    HV_5_7_WIND_RMS_M_S,
    HufnagelValleyCn2,
)
from radiant.core.parameters import ParameterBoundsError


def _independent_moment(power: float, h_max: float = 1.0e5, n: int = 2_000_001) -> float:
    """∫₀^h_max Cn²_HV(h) · h^power dh, computed without RADIANT's quadrature."""
    h = np.linspace(0.0, h_max, n)
    w, a = HV_5_7_WIND_RMS_M_S, HV_5_7_GROUND_STRENGTH_M23
    cn2 = (
        0.00594 * (w / 27.0) ** 2 * (1.0e-5 * h) ** 10 * np.exp(-h / 1000.0)
        + 2.7e-16 * np.exp(-h / 1500.0)
        + a * np.exp(-h / 100.0)
    )
    return float(np.trapezoid(cn2 * h**power, h))


class TestHVFormula:
    @pytest.mark.level0
    def test_ground_value_is_hand_computed_sum(self) -> None:
        """Cn²(0) = 0 (tropo) + 2.7e-16 (middle) + A (surface)."""
        hv = HufnagelValleyCn2()
        value = float(hv.cn2(np.array([0.0]))[0])
        expected = 2.7e-16 + HV_5_7_GROUND_STRENGTH_M23  # 1.727e-14
        assert value == pytest.approx(expected, rel=1e-14)

    @pytest.mark.level0
    def test_value_at_1km_hand_computed(self) -> None:
        """Hand evaluation of the three terms at h = 1000 m."""
        hv = HufnagelValleyCn2()
        tropo = 0.00594 * (21.0 / 27.0) ** 2 * (1.0e-2) ** 10 * math.exp(-1.0)
        middle = 2.7e-16 * math.exp(-1000.0 / 1500.0)
        surface = 1.7e-14 * math.exp(-10.0)
        expected = tropo + middle + surface
        assert float(hv.cn2(np.array([1000.0]))[0]) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_jet_stream_term_peaks_at_10km(self) -> None:
        """d/dh[10 ln h − h/1000] = 0 at h = 10 km — the tropopause bump."""
        hv = HufnagelValleyCn2(ground_strength_m23=0.0)
        h = np.linspace(5.0e3, 20.0e3, 15001)
        # Subtract the analytic middle term so the bump is isolated: it is a
        # monotone exponential and would otherwise pull the argmax down.
        tropo = hv.cn2(h) - 2.7e-16 * np.exp(-h / 1500.0)
        assert h[int(np.argmax(tropo))] == pytest.approx(10.0e3, abs=10.0)

    @pytest.mark.level0
    def test_wind_scales_jet_stream_quadratically(self) -> None:
        """The (w/27)² factor: doubling w quadruples the tropopause term."""
        a = HufnagelValleyCn2(wind_rms_m_s=21.0, ground_strength_m23=0.0)
        b = HufnagelValleyCn2(wind_rms_m_s=42.0, ground_strength_m23=0.0)
        h = np.array([10.0e3])
        middle = 2.7e-16 * math.exp(-10.0e3 / 1500.0)
        assert (float(b.cn2(h)[0]) - middle) == pytest.approx(
            4.0 * (float(a.cn2(h)[0]) - middle), rel=1e-12
        )

    @pytest.mark.level0
    def test_ground_strength_scales_surface_layer(self) -> None:
        hv = HufnagelValleyCn2(wind_rms_m_s=0.0, ground_strength_m23=3.4e-14)
        h = np.array([0.0])
        assert float(hv.cn2(h)[0]) == pytest.approx(3.4e-14 + 2.7e-16, rel=1e-14)

    @pytest.mark.level0
    def test_monotone_decay_above_the_bump(self) -> None:
        hv = HufnagelValleyCn2()
        h = np.linspace(12.0e3, 100.0e3, 5001)
        assert np.all(np.diff(hv.cn2(h)) < 0.0)

    @pytest.mark.level0
    def test_no_overflow_at_absurd_altitude(self) -> None:
        """The log-space jet-stream term must not produce inf·0 = NaN."""
        hv = HufnagelValleyCn2()
        values = hv.cn2(np.array([1.0e6, 1.0e9, 1.0e12, 1.0e30]))
        assert np.all(np.isfinite(values))
        assert np.all(values >= 0.0)
        # All three terms have underflowed; nothing survives above ~1 Mm.
        assert np.all(values < 1.0e-100)


class TestHVTruthAnchors:
    """Published HV-5/7 integral values, via an independent quadrature."""

    @pytest.mark.level0
    def test_anchor_r0_5cm_at_500nm(self) -> None:
        """HV-5/7 vertical r₀ at 0.5 µm = 5 cm (Andrews & Phillips 2005 §12.2.2)."""
        k = 2.0 * math.pi / 0.5e-6
        r0 = (0.423 * k * k * _independent_moment(0.0)) ** (-3.0 / 5.0)
        assert 0.048 <= r0 <= 0.052, f"HV-5/7 r0 = {r0 * 100:.3f} cm, expected 4.8-5.2 cm"

    @pytest.mark.level0
    def test_anchor_isoplanatic_angle_7urad(self) -> None:
        """HV-5/7 vertical θ₀ at 0.5 µm = 7 µrad (the '/7' in the name).

        θ₀ = [2.914 k² ∫ Cn²(h) h^(5/3) dh]^(-3/5) at zenith (Andrews &
        Phillips 2005 Eq. 12.16 / Fried 1982).  Order-of-magnitude sanity for
        the profile *shape*: the r₀ anchor above constrains the zeroth moment,
        this one the 5/3-th, so together they pin both the surface layer and
        the jet-stream bump.
        """
        k = 2.0 * math.pi / 0.5e-6
        theta0 = (2.914 * k * k * _independent_moment(5.0 / 3.0)) ** (-3.0 / 5.0)
        assert 6.0e-6 <= theta0 <= 8.0e-6, f"HV-5/7 theta0 = {theta0 * 1e6:.3f} urad"


class TestSiteElevation:
    """CU-262 — the surface term is anchored to the terrain, not to MSL."""

    @pytest.mark.level0
    def test_default_site_is_sea_level_and_bit_identical(self) -> None:
        """``site_elevation_m = 0`` reproduces the pre-CU-262 profile exactly."""
        h = np.linspace(0.0, 1.0e5, 4001)
        np.testing.assert_array_equal(
            HufnagelValleyCn2().cn2(h), HufnagelValleyCn2(site_elevation_m=0.0).cn2(h)
        )

    @pytest.mark.level0
    def test_surface_term_full_strength_at_the_site(self) -> None:
        """At h = h_site the surface term is A, exactly as it is at MSL for a
        sea-level site.  The free-atmosphere terms stay on MSL, so only the
        surface term is shifted."""
        h_site = 900.0
        hv = HufnagelValleyCn2(site_elevation_m=h_site)
        value = float(hv.cn2(np.array([h_site]))[0])
        tropo = 0.00594 * (21.0 / 27.0) ** 2 * (1.0e-5 * h_site) ** 10 * math.exp(-h_site / 1000.0)
        middle = 2.7e-16 * math.exp(-h_site / 1500.0)
        expected = tropo + middle + HV_5_7_GROUND_STRENGTH_M23  # surface at full A
        assert value == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    def test_free_atmosphere_terms_are_not_shifted(self) -> None:
        """The 10 km jet stream stays at 10 km MSL for a 2 km site (a mountain
        does not lift the tropopause)."""
        hv = HufnagelValleyCn2(site_elevation_m=2000.0, ground_strength_m23=0.0)
        h = np.linspace(5.0e3, 20.0e3, 15001)
        tropo = hv.cn2(h) - 2.7e-16 * np.exp(-h / 1500.0)
        assert h[int(np.argmax(tropo))] == pytest.approx(10.0e3, abs=10.0)

    @pytest.mark.level0
    def test_surface_term_decays_from_the_site_not_from_msl(self) -> None:
        """100 m above a 900 m site the surface term is A/e — the CU-262 defect
        gave A·exp(-10) there instead."""
        h_site = 900.0
        hv = HufnagelValleyCn2(
            site_elevation_m=h_site, wind_rms_m_s=0.0, ground_strength_m23=1.7e-14
        )
        surface = float(hv.cn2(np.array([h_site + 100.0]))[0]) - 2.7e-16 * math.exp(
            -(h_site + 100.0) / 1500.0
        )
        assert surface == pytest.approx(1.7e-14 / math.e, rel=1e-11)

    @pytest.mark.level0
    def test_surface_layer_column_is_site_invariant(self) -> None:
        r"""Analytic anchor: $\int_{h_{site}}^{\infty} A e^{-(h-h_{site})/100}\,dh
        = 100 A$ regardless of the site elevation.  This is the whole content of
        the CU-262 fix — an elevated site keeps its boundary layer."""
        for h_site in (0.0, 900.0, 2635.0, 4200.0):
            hv = HufnagelValleyCn2(
                site_elevation_m=h_site, wind_rms_m_s=0.0, ground_strength_m23=0.0
            )
            hv_with_surface = HufnagelValleyCn2(
                site_elevation_m=h_site, wind_rms_m_s=0.0, ground_strength_m23=1.7e-14
            )
            h = np.linspace(h_site, h_site + 5000.0, 500_001)
            surface_only = hv_with_surface.cn2(h) - hv.cn2(h)
            column = float(np.trapezoid(surface_only, h))
            assert column == pytest.approx(100.0 * 1.7e-14, rel=1e-6), (
                f"site {h_site} m MSL: surface column {column:.6e} m^(1/3)"
            )

    @pytest.mark.level0
    def test_level_air_to_air_path_has_no_surface_term(self) -> None:
        """A level leg 10 km above a 900 m site: the surface term is suppressed
        by exp(-91), i.e. gone, without any topology special case."""
        h_site, h_arm = 900.0, 10.0e3
        hv = HufnagelValleyCn2(site_elevation_m=h_site)
        free = HufnagelValleyCn2(site_elevation_m=h_site, ground_strength_m23=0.0)
        total = float(hv.cn2(np.array([h_arm]))[0])
        assert total == pytest.approx(float(free.cn2(np.array([h_arm]))[0]), rel=1e-12)

    @pytest.mark.level0
    def test_negative_site_elevation_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="site_elevation_m"):
            HufnagelValleyCn2(site_elevation_m=-1.0)

    @pytest.mark.level0
    def test_nonfinite_site_elevation_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="not finite"):
            HufnagelValleyCn2(site_elevation_m=float("nan"))

    @pytest.mark.level0
    def test_altitude_below_the_site_is_refused(self) -> None:
        """h < h_site is inside the terrain — an input error, not a clamp."""
        hv = HufnagelValleyCn2(site_elevation_m=900.0)
        with pytest.raises(ParameterBoundsError, match="below the ground"):
            hv.cn2(np.array([899.0]))

    @pytest.mark.level0
    def test_describe_names_the_site_only_when_non_zero(self) -> None:
        assert "site" not in HufnagelValleyCn2().describe()
        assert "900 m MSL" in HufnagelValleyCn2(site_elevation_m=900.0).describe()


class TestHVFailureModes:
    @pytest.mark.level0
    def test_negative_wind_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="wind_rms_m_s"):
            HufnagelValleyCn2(wind_rms_m_s=-1.0)

    @pytest.mark.level0
    def test_negative_ground_strength_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="ground_strength_m23"):
            HufnagelValleyCn2(ground_strength_m23=-1e-15)

    @pytest.mark.level0
    def test_nan_coefficient_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="not finite"):
            HufnagelValleyCn2(wind_rms_m_s=float("nan"))

    @pytest.mark.level0
    def test_negative_altitude_rejected(self) -> None:
        """At the default site elevation of 0 the floor is mean sea level."""
        with pytest.raises(ParameterBoundsError, match="below the ground"):
            HufnagelValleyCn2().cn2(np.array([-1.0]))

    @pytest.mark.level0
    def test_nonfinite_altitude_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError, match="non-finite"):
            HufnagelValleyCn2().cn2(np.array([0.0, float("inf")]))

    @pytest.mark.level0
    def test_zero_wind_and_ground_leaves_only_middle_term(self) -> None:
        hv = HufnagelValleyCn2(wind_rms_m_s=0.0, ground_strength_m23=0.0)
        h = np.array([0.0, 1500.0])
        np.testing.assert_allclose(
            hv.cn2(h), np.array([2.7e-16, 2.7e-16 * math.exp(-1.0)]), rtol=1e-13
        )

    @pytest.mark.level0
    def test_contract_metadata(self) -> None:
        hv = HufnagelValleyCn2()
        assert hv.coverage_m is None
        assert 10.0e3 in hv.breakpoints_m
        assert "HV-5/7" in hv.describe()
