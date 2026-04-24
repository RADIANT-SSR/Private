"""Tests for SurfaceMaterial.

Truth anchors:
1. Kirchhoff: ε + ρ = 1 at every wavelength
2. Graybody: scalar ε → ρ = 1 − ε
3. Material → ThermalSource when no solar geometry

See RADIANT_Source_Target_System.md §4.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.source.combined import CombinedSource
from radiant.source.emitted import ThermalSource
from radiant.source.material import SurfaceMaterial

WAV = np.linspace(3.0, 5.0, 200)


class TestSurfaceMaterial:
    def test_kirchhoff_scalar(self) -> None:
        """ε + ρ = 1 for scalar emissivity."""
        mat = SurfaceMaterial(name="test", temperature_K=300.0, emissivity=0.9)
        assert mat.reflectance == pytest.approx(0.1, rel=1e-15)
        assert mat.verify_kirchhoff()

    def test_kirchhoff_spectral(self) -> None:
        """ε(λ) + ρ(λ) = 1 for array emissivity."""
        eps = np.linspace(0.8, 0.95, 50)
        mat = SurfaceMaterial(name="spectral", temperature_K=350.0, emissivity=eps)
        rho = mat.reflectance
        np.testing.assert_allclose(eps + rho, 1.0, atol=1e-15)
        assert mat.verify_kirchhoff()

    def test_graybody_convenience(self) -> None:
        mat = SurfaceMaterial.graybody("aluminum", 400.0, 0.1)
        assert mat.temperature_K == 400.0
        assert mat.emissivity == 0.1
        assert mat.reflectance == pytest.approx(0.9, rel=1e-15)

    def test_create_source_thermal(self) -> None:
        """No solar → ThermalSource."""
        mat = SurfaceMaterial(name="test", temperature_K=500.0, emissivity=0.9)
        src = mat.create_source()
        assert isinstance(src, ThermalSource)
        L = src.spectral_radiance(WAV)
        expected = 0.9 * planck_spectral_radiance(WAV, 500.0)
        np.testing.assert_allclose(L, expected, rtol=1e-10)

    def test_create_source_combined(self) -> None:
        """With solar → CombinedSource."""
        mat = SurfaceMaterial(name="test", temperature_K=300.0, emissivity=0.9)
        src = mat.create_source(solar_zenith_rad=0.3)
        assert isinstance(src, CombinedSource)
        L = src.spectral_radiance(WAV)
        assert np.all(L > 0)

    def test_negative_temp_raises(self) -> None:
        with pytest.raises(ValueError, match="temperature_K"):
            SurfaceMaterial(name="bad", temperature_K=-10, emissivity=0.9)

    def test_emissivity_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="emissivity"):
            SurfaceMaterial(name="bad", temperature_K=300, emissivity=1.1)

    def test_emissivity_lt_0_raises(self) -> None:
        with pytest.raises(ValueError, match="emissivity"):
            SurfaceMaterial(name="bad", temperature_K=300, emissivity=-0.1)

    def test_invalid_brdf_model_raises(self) -> None:
        with pytest.raises(ValueError, match="brdf_model"):
            SurfaceMaterial(
                name="bad", temperature_K=300, emissivity=0.9,
                brdf_model="cook-torrance",
            )

    def test_invalid_specular_fraction_raises(self) -> None:
        with pytest.raises(ValueError, match="specular_fraction"):
            SurfaceMaterial(
                name="bad", temperature_K=300, emissivity=0.9,
                specular_fraction=1.5,
            )

    def test_frozen(self) -> None:
        mat = SurfaceMaterial(name="test", temperature_K=300, emissivity=0.9)
        with pytest.raises(AttributeError):
            mat.temperature_K = 400  # type: ignore[misc]

    def test_phong_material(self) -> None:
        mat = SurfaceMaterial(
            name="glossy", temperature_K=300, emissivity=0.9,
            brdf_model="phong", phong_exponent=20.0, specular_fraction=0.3,
        )
        src = mat.create_source(solar_zenith_rad=0.3, observer_zenith_rad=0.3)
        assert isinstance(src, CombinedSource)
        L = src.spectral_radiance(WAV)
        assert np.all(L > 0)

    def test_zero_emissivity_reflectance_one(self) -> None:
        mat = SurfaceMaterial(name="mirror", temperature_K=300, emissivity=0.0)
        assert mat.reflectance == pytest.approx(1.0, rel=1e-15)
