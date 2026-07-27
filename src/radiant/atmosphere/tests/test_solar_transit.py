"""Level-0 tests for the twilight two-arm direct-solar transmittance (GF-9).

The value is PROVISIONAL (no MODTRAN twilight deck in batch 1 — see the module
docstring), so what is pinned here is the *structure*: the tangent
decomposition, the continuity limits, the monotonicity in depression angle,
and the Rule-15/17 refusals.  Absolute radiometric accuracy is deliberately
not asserted, because there is nothing trustworthy to assert it against yet.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere.grazing_column import grazing_slant_column_km
from radiant.atmosphere.segment_grazing import grazing_segment_optical_depth
from radiant.atmosphere.simple import H_MOL_M, SimpleAtmosphere
from radiant.atmosphere.solar_shadow import shadow_height_m
from radiant.atmosphere.solar_transit import twilight_solar_transmittance
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

H_ATM_TOP_M = 1.0e5


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(0.4, 1.0, 31)


@pytest.fixture
def atm() -> SimpleAtmosphere:
    return SimpleAtmosphere(standard_atmosphere="midlat_summer")


def _quiet(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return fn(*args, **kwargs)


class TestTwoArmDecomposition:
    @pytest.mark.level0
    def test_equals_the_product_of_its_two_arms(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """τ_sun = exp(−[od(tangent→target) + od(tangent→TOA)]) — the identity
        the module claims, recomputed from the segment primitive."""
        h_tgt = 60_000.0
        theta_s = math.pi / 2.0 + math.radians(5.0)
        r_0 = (R_EARTH_M + h_tgt) * math.sin(theta_s)
        h_tan = r_0 - R_EARTH_M
        od_out, _ = grazing_segment_optical_depth(atm, wl, r_0, h_tan, h_tgt)
        od_in, _ = grazing_segment_optical_depth(atm, wl, r_0, h_tan, H_ATM_TOP_M)
        expected = np.exp(-(od_out + od_in))
        np.testing.assert_array_equal(
            twilight_solar_transmittance(atm, wl, h_tgt, theta_s, h_atm_top_m=H_ATM_TOP_M),
            expected,
        )

    @pytest.mark.level0
    def test_tangent_altitude_matches_the_shadow_height(self, atm: SimpleAtmosphere) -> None:
        """The tangent altitude of a *just*-sunlit target is 0 by definition —
        a target exactly at the shadow height grazes the surface."""
        theta_s = math.pi / 2.0 + math.radians(4.0)
        h_tgt = shadow_height_m(theta_s)
        r_0 = (R_EARTH_M + h_tgt) * math.sin(theta_s)
        assert r_0 - R_EARTH_M == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.level0
    def test_horizontal_sun_degenerates_to_one_arm(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """As θ_s → π/2⁺ the outgoing arm vanishes and the transit becomes the
        single tangent column h_tgt → h_atm_top [continuity]."""
        h_tgt = 5_000.0
        theta_s = math.pi / 2.0 + 1e-12
        tau = twilight_solar_transmittance(atm, wl, h_tgt, theta_s, h_atm_top_m=H_ATM_TOP_M)
        r_0 = R_EARTH_M + h_tgt
        od_single, _ = grazing_segment_optical_depth(atm, wl, r_0, h_tgt, H_ATM_TOP_M)
        np.testing.assert_allclose(tau, np.exp(-od_single), rtol=1e-9)


class TestPhysicalBehaviour:
    @pytest.mark.level0
    def test_bounded_in_zero_one(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        for depression_deg in (0.5, 2.0, 5.0, 10.0):
            theta_s = math.pi / 2.0 + math.radians(depression_deg)
            h_tgt = max(shadow_height_m(theta_s) * 1.2, 1_000.0)
            if h_tgt >= H_ATM_TOP_M:
                continue
            tau = twilight_solar_transmittance(atm, wl, h_tgt, theta_s, h_atm_top_m=H_ATM_TOP_M)
            assert np.all(np.isfinite(tau))
            assert float(tau.min()) >= 0.0
            assert float(tau.max()) <= 1.0

    @pytest.mark.level0
    def test_higher_target_at_fixed_depression_transmits_more(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """A target further above the terminator has a higher tangent point,
        so its beam misses more of the dense lower atmosphere."""
        theta_s = math.pi / 2.0 + math.radians(2.0)
        low = twilight_solar_transmittance(atm, wl, 10_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)
        high = twilight_solar_transmittance(atm, wl, 60_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)
        assert np.all(high > low)

    @pytest.mark.level0
    def test_transit_column_is_far_longer_than_the_vertical_one(
        self, atm: SimpleAtmosphere
    ) -> None:
        """Order-of-magnitude sanity: a tangent transit at 10 km carries tens
        of vertical columns of air — the fragility statement, quantified."""
        r_0 = R_EARTH_M + 10_000.0
        slant = 2.0 * grazing_slant_column_km(r_0, 10_000.0, H_ATM_TOP_M, H_MOL_M)
        vertical = atm._column_length_km(10_000.0, H_ATM_TOP_M, H_MOL_M)
        assert 30.0 < slant / vertical < 80.0

    @pytest.mark.level0
    def test_deterministic(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        theta_s = math.pi / 2.0 + math.radians(3.0)
        a = twilight_solar_transmittance(atm, wl, 40_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)
        b = twilight_solar_transmittance(atm, wl, 40_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)
        np.testing.assert_array_equal(a, b)


class TestFailureModes:
    @pytest.mark.level0
    @pytest.mark.parametrize("theta_s", [0.0, 1.0, math.pi / 2.0, float("nan")])
    def test_sun_above_horizontal_raises(
        self, atm: SimpleAtmosphere, wl: np.ndarray, theta_s: float
    ) -> None:
        """Rule 15/zero drift: the daylight column belongs to the backend."""
        with pytest.raises(ParameterBoundsError, match="not greater than"):
            twilight_solar_transmittance(atm, wl, 40_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)

    @pytest.mark.level0
    def test_shadowed_target_raises(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        theta_s = math.pi / 2.0 + math.radians(10.0)
        with pytest.raises(ParameterBoundsError, match="shadow"):
            twilight_solar_transmittance(atm, wl, 1_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)

    @pytest.mark.level0
    def test_exo_target_raises_pointing_at_the_vacuum_identity(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        theta_s = math.pi / 2.0 + math.radians(1.0)
        with pytest.raises(ParameterBoundsError) as exc:
            twilight_solar_transmittance(atm, wl, 150_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M)
        assert "tau_sun ≡ 1" in str(exc.value)

    @pytest.mark.level0
    def test_bad_grid_raises(self, atm: SimpleAtmosphere) -> None:
        theta_s = math.pi / 2.0 + math.radians(1.0)
        with pytest.raises(ParameterBoundsError):
            twilight_solar_transmittance(
                atm, np.array([1.0]), 40_000.0, theta_s, h_atm_top_m=H_ATM_TOP_M
            )
