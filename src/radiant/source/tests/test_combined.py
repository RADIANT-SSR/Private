"""Tests for CombinedSource (Kirchhoff-consistent thermal + reflected).

Truth anchors:
1. ε=1, solar off → equals ThermalSource
2. ε=0, thermal off → equals ReflectedSolarSource
3. Kirchhoff: L_total = ε·B + (1-ε)·(ρ/π)·E_sun·cosθ

Cross-model consistency:
- CombinedSource with ε=1 = ThermalSource (to 1e-10)
- CombinedSource with ε=0 = ReflectedSolarSource (to 1e-10)

See RADIANT_Source_Target_System.md §3.4.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.source.brdf import LambertianBRDF
from radiant.source.combined import CombinedSource
from radiant.source.emitted import ThermalSource
from radiant.source.reflected import ReflectedSolarSource


WAV = np.linspace(3.0, 5.0, 200)


class TestCombinedSource:
    def test_eps_1_equals_thermal(self) -> None:
        """ε=1 → L = B(λ,T), no reflected component."""
        T = 300.0
        combined = CombinedSource(
            temperature_K=T, emissivity=1.0,
            solar_zenith_rad=0.0,
        )
        thermal = ThermalSource(temperature_K=T, emissivity=1.0)
        L_combined = combined.spectral_radiance(WAV)
        L_thermal = thermal.spectral_radiance(WAV)
        np.testing.assert_allclose(L_combined, L_thermal, rtol=1e-10)

    def test_eps_0_equals_reflected(self) -> None:
        """ε=0 → L = (1/π)·E_sun·cosθ (pure reflected Lambertian)."""
        theta = 0.3
        combined = CombinedSource(
            temperature_K=300.0, emissivity=0.0,
            solar_zenith_rad=theta,
        )
        reflected = ReflectedSolarSource(
            brdf=LambertianBRDF(reflectance=1.0),
            solar_zenith_rad=theta,
        )
        L_combined = combined.spectral_radiance(WAV)
        L_reflected = reflected.spectral_radiance(WAV)
        np.testing.assert_allclose(L_combined, L_reflected, rtol=1e-10)

    def test_kirchhoff_hand_calc(self) -> None:
        """L = ε·B + (1-ε)·(ρ/π)·E_sun·cosθ with ρ = 1-ε."""
        T = 350.0
        eps = 0.6
        theta = math.radians(30)
        combined = CombinedSource(
            temperature_K=T, emissivity=eps,
            solar_zenith_rad=theta,
        )
        L = combined.spectral_radiance(WAV)

        B = planck_spectral_radiance(WAV, T)
        E_sun = toa_solar_spectral_irradiance(WAV)
        rho = 1.0 - eps
        expected = eps * B + (rho / math.pi) * E_sun * math.cos(theta)
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_sun_at_horizon(self) -> None:
        """θ_sun = π/2 → reflected term = 0, only thermal."""
        T = 300.0
        eps = 0.5
        combined = CombinedSource(
            temperature_K=T, emissivity=eps,
            solar_zenith_rad=math.pi / 2,
        )
        L = combined.spectral_radiance(WAV)
        expected = eps * planck_spectral_radiance(WAV, T)
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_mwir_crossover(self) -> None:
        """In MWIR, both terms contribute — result > either alone."""
        T = 400.0
        eps = 0.8
        combined = CombinedSource(
            temperature_K=T, emissivity=eps,
            solar_zenith_rad=0.0,
        )
        L_combined = combined.spectral_radiance(WAV)
        L_thermal = eps * planck_spectral_radiance(WAV, T)
        # Combined should be >= thermal at every wavelength
        assert np.all(L_combined >= L_thermal - 1e-20)

    def test_phong_brdf_model(self) -> None:
        """Phong model produces different result than Lambertian."""
        T = 300.0
        eps = 0.5
        lamb = CombinedSource(
            temperature_K=T, emissivity=eps,
            solar_zenith_rad=0.3, observer_zenith_rad=0.3,
            brdf_model="lambertian",
        )
        phong = CombinedSource(
            temperature_K=T, emissivity=eps,
            solar_zenith_rad=0.3, observer_zenith_rad=0.3,
            brdf_model="phong", specular_fraction=0.5, phong_exponent=20,
        )
        L_lamb = lamb.spectral_radiance(WAV)
        L_phong = phong.spectral_radiance(WAV)
        # Phong at specular should be higher than Lambertian
        assert np.all(L_phong > L_lamb)

    def test_spectral_emissivity(self) -> None:
        """Array emissivity works correctly."""
        eps = np.linspace(0.3, 0.9, len(WAV))
        combined = CombinedSource(
            temperature_K=300.0, emissivity=eps,
            solar_zenith_rad=0.0,
        )
        L = combined.spectral_radiance(WAV)
        assert len(L) == len(WAV)
        assert np.all(np.isfinite(L))
        assert np.all(L > 0)

    def test_negative_temp_raises(self) -> None:
        with pytest.raises(ValueError, match="temperature_K"):
            CombinedSource(
                temperature_K=-10, emissivity=0.5,
                solar_zenith_rad=0.0,
            )

    def test_emissivity_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="emissivity"):
            CombinedSource(
                temperature_K=300, emissivity=1.1,
                solar_zenith_rad=0.0,
            )

    def test_invalid_brdf_model_raises(self) -> None:
        with pytest.raises(ValueError, match="brdf_model"):
            CombinedSource(
                temperature_K=300, emissivity=0.5,
                solar_zenith_rad=0.0,
                brdf_model="invalid",
            )

    def test_invalid_zenith_raises(self) -> None:
        with pytest.raises(ValueError, match="solar_zenith_rad"):
            CombinedSource(
                temperature_K=300, emissivity=0.5,
                solar_zenith_rad=2.0,
            )

    def test_frozen(self) -> None:
        src = CombinedSource(
            temperature_K=300, emissivity=0.5,
            solar_zenith_rad=0.0,
        )
        with pytest.raises(AttributeError):
            src.temperature_K = 400  # type: ignore[misc]

    def test_deterministic(self) -> None:
        src = CombinedSource(
            temperature_K=300, emissivity=0.5,
            solar_zenith_rad=0.3,
        )
        L1 = src.spectral_radiance(WAV)
        L2 = src.spectral_radiance(WAV)
        np.testing.assert_array_equal(L1, L2)
