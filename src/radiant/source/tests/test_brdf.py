"""Tests for BRDF models (Lambertian and Phong).

Truth anchors:
1. Lambertian: BRDF = ρ/π → ∫BRDF·cosθ·dΩ = ρ (energy conservation)
2. Phong at specular: cos^n(0) = 1 → peak BRDF = ρ_d/π + ρ_s·(n+2)/(2π)
3. Phong with specular_fraction=0 → Lambertian

See RADIANT_Source_Target_System.md §3.3.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.brdf_phong import PhongBRDF


WAV = np.linspace(3.0, 5.0, 100)


class TestLambertianBRDF:
    def test_basic_value(self) -> None:
        """BRDF = ρ/π for scalar reflectance."""
        brdf = LambertianBRDF(reflectance=0.5)
        vals = brdf.evaluate(WAV)
        assert vals[0] == pytest.approx(0.5 / math.pi, rel=1e-12)

    def test_angle_independent(self) -> None:
        """Lambertian is angle-independent."""
        brdf = LambertianBRDF(reflectance=0.3)
        v1 = brdf.evaluate(WAV, theta_sun_rad=0.0, theta_obs_rad=0.0)
        v2 = brdf.evaluate(WAV, theta_sun_rad=0.5, theta_obs_rad=1.0)
        np.testing.assert_allclose(v1, v2, rtol=1e-12)

    def test_energy_conservation(self) -> None:
        """∫BRDF·cosθ·dΩ = ρ over hemisphere.

        For Lambertian: ∫(ρ/π)·cosθ·sinθ·dθ·dφ
        = (ρ/π)·2π·∫₀^{π/2} cosθ·sinθ·dθ
        = (ρ/π)·2π·(1/2) = ρ
        """
        rho = 0.7
        brdf = LambertianBRDF(reflectance=rho)
        vals = brdf.evaluate(WAV)  # ρ/π
        # Numerical hemisphere integral
        n_theta = 1000
        theta = np.linspace(0, math.pi / 2, n_theta)
        integrand = float(vals[0]) * np.cos(theta) * np.sin(theta)
        integral = 2 * math.pi * float(np.trapezoid(integrand, theta))
        assert integral == pytest.approx(rho, rel=1e-4)

    def test_spectral_reflectance(self) -> None:
        """Array reflectance produces wavelength-dependent BRDF."""
        rho = np.linspace(0.2, 0.8, len(WAV))
        brdf = LambertianBRDF(reflectance=rho)
        vals = brdf.evaluate(WAV)
        expected = rho / math.pi
        np.testing.assert_allclose(vals, expected, rtol=1e-12)

    def test_zero_reflectance(self) -> None:
        brdf = LambertianBRDF(reflectance=0.0)
        vals = brdf.evaluate(WAV)
        np.testing.assert_allclose(vals, 0.0, atol=1e-30)

    def test_negative_reflectance_raises(self) -> None:
        with pytest.raises(ValueError, match="reflectance"):
            LambertianBRDF(reflectance=-0.1)

    def test_reflectance_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="reflectance"):
            LambertianBRDF(reflectance=1.1)

    def test_array_length_mismatch_raises(self) -> None:
        brdf = LambertianBRDF(reflectance=np.array([0.5, 0.6]))
        with pytest.raises(ValueError, match="does not match"):
            brdf.evaluate(WAV)

    def test_frozen(self) -> None:
        brdf = LambertianBRDF(reflectance=0.5)
        with pytest.raises(AttributeError):
            brdf.reflectance = 0.3  # type: ignore[misc]


class TestPhongBRDF:
    def test_specular_peak(self) -> None:
        """At specular geometry (α=0), cos^n(0)=1 → peak BRDF known."""
        rho = 0.6
        sf = 0.3
        n = 20
        brdf = PhongBRDF(reflectance=rho, specular_fraction=sf, phong_exponent=n)
        # At specular: θ_obs = θ_sun → α = 0
        vals = brdf.evaluate(WAV, theta_sun_rad=0.3, theta_obs_rad=0.3)
        rho_d = rho * (1 - sf)
        rho_s = rho * sf
        expected = rho_d / math.pi + rho_s * (n + 2) / (2 * math.pi)
        assert vals[0] == pytest.approx(expected, rel=1e-10)

    def test_zero_specular_equals_lambertian(self) -> None:
        """Phong with specular_fraction=0 is Lambertian."""
        rho = 0.5
        phong = PhongBRDF(reflectance=rho, specular_fraction=0.0)
        lamb = LambertianBRDF(reflectance=rho)
        p_vals = phong.evaluate(WAV, theta_sun_rad=0.3, theta_obs_rad=0.5)
        l_vals = lamb.evaluate(WAV, theta_sun_rad=0.3, theta_obs_rad=0.5)
        np.testing.assert_allclose(p_vals, l_vals, rtol=1e-12)

    def test_specular_off_axis_lower(self) -> None:
        """BRDF drops when observer moves away from specular angle."""
        brdf = PhongBRDF(reflectance=0.5, specular_fraction=0.5, phong_exponent=20)
        v_spec = brdf.evaluate(WAV, theta_sun_rad=0.3, theta_obs_rad=0.3)
        v_off = brdf.evaluate(WAV, theta_sun_rad=0.3, theta_obs_rad=0.8)
        assert v_spec[0] > v_off[0]

    def test_negative_reflectance_raises(self) -> None:
        with pytest.raises(ValueError, match="reflectance"):
            PhongBRDF(reflectance=-0.1)

    def test_invalid_specular_fraction_raises(self) -> None:
        with pytest.raises(ValueError, match="specular_fraction"):
            PhongBRDF(reflectance=0.5, specular_fraction=1.5)

    def test_negative_exponent_raises(self) -> None:
        with pytest.raises(ValueError, match="phong_exponent"):
            PhongBRDF(reflectance=0.5, phong_exponent=-1)

    def test_frozen(self) -> None:
        brdf = PhongBRDF(reflectance=0.5)
        with pytest.raises(AttributeError):
            brdf.reflectance = 0.3  # type: ignore[misc]
