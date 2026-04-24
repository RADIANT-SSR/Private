"""Tests for ReflectedSolarSource.

Truth anchors:
1. Lambertian with ρ=0.5 at noon: L = (ρ/π)·E_sun·cos(0) = ρ·E_sun/π
2. Sun at horizon (θ=π/2): L = 0
3. 1/R² scaling with distance

See RADIANT_Source_Target_System.md §3.3.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF
from radiant.source.reflected import ReflectedSolarSource

WAV = np.linspace(0.4, 2.5, 200)


class TestReflectedSolarSource:
    def test_lambertian_noon_hand_calc(self) -> None:
        """ρ=0.5, noon (θ_sun=0): L = (ρ/π)·E_sun·1 = 0.5·E_sun/π."""
        rho = 0.5
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=rho),
            solar_zenith_rad=0.0,
        )
        L = src.spectral_radiance(WAV)
        E_sun = toa_solar_spectral_irradiance(WAV)
        expected = (rho / math.pi) * E_sun
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_sun_at_horizon_zero(self) -> None:
        """θ_sun = π/2 → cos(π/2) ≈ 0 → L ≈ 0 (within floating-point)."""
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=0.5),
            solar_zenith_rad=math.pi / 2,
        )
        L = src.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 0.0, atol=1e-12)

    def test_oblique_sun(self) -> None:
        """θ_sun = 60°: L = (ρ/π)·E_sun·cos(60°)."""
        rho = 0.3
        theta = math.radians(60)
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=rho),
            solar_zenith_rad=theta,
        )
        L = src.spectral_radiance(WAV)
        E_sun = toa_solar_spectral_irradiance(WAV)
        expected = (rho / math.pi) * E_sun * math.cos(theta)
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_distance_scaling(self) -> None:
        """At 2 AU, reflected radiance is 1/4 of 1 AU."""
        brdf = LambertianBRDF(reflectance=0.5)
        src_1au = ReflectedSolarSource(brdf=brdf, solar_zenith_rad=0.0, distance_au=1.0)
        src_2au = ReflectedSolarSource(brdf=brdf, solar_zenith_rad=0.0, distance_au=2.0)
        L_1au = src_1au.spectral_radiance(WAV)
        L_2au = src_2au.spectral_radiance(WAV)
        np.testing.assert_allclose(L_2au, L_1au / 4.0, rtol=1e-10)

    def test_phong_specular_peak(self) -> None:
        """Phong at specular geometry should be higher than off-axis."""
        brdf = PhongBRDF(reflectance=0.5, specular_fraction=0.5, phong_exponent=20)
        src_spec = ReflectedSolarSource(
            brdf=brdf, solar_zenith_rad=0.3, observer_zenith_rad=0.3,
        )
        src_off = ReflectedSolarSource(
            brdf=brdf, solar_zenith_rad=0.3, observer_zenith_rad=0.8,
        )
        L_spec = src_spec.spectral_radiance(WAV)
        L_off = src_off.spectral_radiance(WAV)
        assert np.all(L_spec > L_off)

    def test_positive_radiance(self) -> None:
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=0.5),
            solar_zenith_rad=0.3,
        )
        L = src.spectral_radiance(WAV)
        assert np.all(L > 0)

    def test_zero_reflectance_zero_radiance(self) -> None:
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=0.0),
            solar_zenith_rad=0.0,
        )
        L = src.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 0.0, atol=1e-30)

    def test_invalid_zenith_raises(self) -> None:
        with pytest.raises(ValueError, match="solar_zenith_rad"):
            ReflectedSolarSource(
                brdf=LambertianBRDF(reflectance=0.5),
                solar_zenith_rad=2.0,
            )

    def test_negative_distance_raises(self) -> None:
        with pytest.raises(ValueError, match="distance_au"):
            ReflectedSolarSource(
                brdf=LambertianBRDF(reflectance=0.5),
                solar_zenith_rad=0.0,
                distance_au=-1.0,
            )

    def test_frozen(self) -> None:
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=0.5),
            solar_zenith_rad=0.0,
        )
        with pytest.raises(AttributeError):
            src.solar_zenith_rad = 0.5  # type: ignore[misc]

    def test_deterministic(self) -> None:
        src = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=0.5),
            solar_zenith_rad=0.3,
        )
        L1 = src.spectral_radiance(WAV)
        L2 = src.spectral_radiance(WAV)
        np.testing.assert_array_equal(L1, L2)
