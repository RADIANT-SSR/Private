"""Tests for point source intensity variants.

Truth anchors:
1. BlackbodyIntensitySource: I = A·ε·B(λ,T)
2. 1/R² → doubling area doubles intensity
3. DirectIntensitySource interpolation matches input

See RADIANT_Source_Target_System.md §3.6.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.source.point_source_blackbody import BlackbodyIntensitySource
from radiant.source.point_source_direct import DirectIntensitySource

WAV = np.linspace(3.0, 5.0, 200)


class TestBlackbodyIntensitySource:
    def test_basic_formula(self) -> None:
        """I(λ) = A · ε · B(λ, T)."""
        T = 500.0
        A = 0.01  # 100 cm²
        eps = 0.9
        src = BlackbodyIntensitySource(
            temperature_K=T, projected_area_m2=A, emissivity=eps,
        )
        I = src.spectral_intensity(WAV)
        expected = A * eps * planck_spectral_radiance(WAV, T)
        np.testing.assert_allclose(I, expected, rtol=1e-12)

    def test_area_scaling(self) -> None:
        """Doubling area doubles intensity."""
        T = 500.0
        src_1 = BlackbodyIntensitySource(temperature_K=T, projected_area_m2=0.01)
        src_2 = BlackbodyIntensitySource(temperature_K=T, projected_area_m2=0.02)
        I_1 = src_1.spectral_intensity(WAV)
        I_2 = src_2.spectral_intensity(WAV)
        np.testing.assert_allclose(I_2, 2.0 * I_1, rtol=1e-12)

    def test_radiance_equals_eps_B(self) -> None:
        """Equivalent radiance = ε · B (area cancels)."""
        T = 500.0
        eps = 0.8
        src = BlackbodyIntensitySource(
            temperature_K=T, projected_area_m2=0.5, emissivity=eps,
        )
        L = src.spectral_radiance(WAV)
        expected = eps * planck_spectral_radiance(WAV, T)
        np.testing.assert_allclose(L, expected, rtol=1e-12)

    def test_unity_emissivity_default(self) -> None:
        src = BlackbodyIntensitySource(temperature_K=500, projected_area_m2=0.01)
        I = src.spectral_intensity(WAV)
        expected = 0.01 * planck_spectral_radiance(WAV, 500)
        np.testing.assert_allclose(I, expected, rtol=1e-12)

    def test_zero_temp_raises(self) -> None:
        with pytest.raises(ValueError, match="temperature_K"):
            BlackbodyIntensitySource(temperature_K=0, projected_area_m2=0.01)

    def test_zero_area_raises(self) -> None:
        with pytest.raises(ValueError, match="projected_area_m2"):
            BlackbodyIntensitySource(temperature_K=500, projected_area_m2=0.0)

    def test_emissivity_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="emissivity"):
            BlackbodyIntensitySource(
                temperature_K=500, projected_area_m2=0.01, emissivity=1.5,
            )

    def test_frozen(self) -> None:
        src = BlackbodyIntensitySource(temperature_K=500, projected_area_m2=0.01)
        with pytest.raises(AttributeError):
            src.temperature_K = 600  # type: ignore[misc]


class TestDirectIntensitySource:
    @pytest.fixture()
    def intensity_data(self) -> SpectralData:
        return SpectralData(
            name="test_intensity",
            wavelength_um=np.linspace(2.0, 6.0, 50),
            values=np.ones(50) * 100.0,
            unit="W/sr/um",
            source="test",
        )

    def test_constant_intensity(self, intensity_data: SpectralData) -> None:
        src = DirectIntensitySource(intensity_data=intensity_data)
        I = src.spectral_intensity(WAV)
        np.testing.assert_allclose(I, 100.0, rtol=1e-6)

    def test_interpolation(self) -> None:
        """Linear interpolation on non-uniform data."""
        wl = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
        vals = np.array([10.0, 20.0, 30.0, 20.0, 10.0])
        sd = SpectralData(
            name="test", wavelength_um=wl, values=vals,
            unit="W/sr/um", source="test",
        )
        src = DirectIntensitySource(intensity_data=sd)
        result = src.spectral_intensity(np.array([3.5]))
        assert result[0] == pytest.approx(25.0, rel=1e-10)

    def test_radiance_conversion(self, intensity_data: SpectralData) -> None:
        """L = I / reference_area."""
        src = DirectIntensitySource(intensity_data=intensity_data)
        ref_area = 1e-6
        L = src.spectral_radiance(WAV, reference_area_m2=ref_area)
        I = src.spectral_intensity(WAV)
        np.testing.assert_allclose(L, I / ref_area, rtol=1e-12)

    def test_out_of_range_raises(self) -> None:
        sd = SpectralData(
            name="narrow", wavelength_um=np.linspace(4.0, 4.5, 10),
            values=np.ones(10), unit="W/sr/um", source="test",
        )
        src = DirectIntensitySource(intensity_data=sd)
        with pytest.raises(ValueError, match="outside table"):
            src.spectral_intensity(WAV)

    def test_negative_values_raises(self) -> None:
        sd = SpectralData(
            name="bad", wavelength_um=np.linspace(2.0, 6.0, 10),
            values=np.full(10, -1.0), unit="W/sr/um", source="test",
        )
        with pytest.raises(ValueError, match="non-negative"):
            DirectIntensitySource(intensity_data=sd)

    def test_zero_ref_area_raises(self) -> None:
        sd = SpectralData(
            name="test", wavelength_um=np.linspace(2.0, 6.0, 10),
            values=np.ones(10), unit="W/sr/um", source="test",
        )
        src = DirectIntensitySource(intensity_data=sd)
        with pytest.raises(ValueError, match="reference_area_m2"):
            src.spectral_radiance(np.array([3.0]), reference_area_m2=0.0)

    def test_frozen(self, intensity_data: SpectralData) -> None:
        src = DirectIntensitySource(intensity_data=intensity_data)
        with pytest.raises(AttributeError):
            src.name = "changed"  # type: ignore[misc]
