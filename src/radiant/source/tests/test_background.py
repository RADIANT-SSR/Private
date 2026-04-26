"""Tests for background source types.

Truth anchors:
1. BlackbodyBackground: L = ε·B(λ,T)
2. ConstantBackground: flat value everywhere
3. CMB default: T=2.7 K, ε=1

See RADIANT_Source_Target_System.md §3.7.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.source.backgrounds.blackbody import CMB_BACKGROUND, BlackbodyBackground
from radiant.source.backgrounds.constant import ConstantBackground
from radiant.source.backgrounds.tabulated import TabulatedBackground

WAV = np.linspace(3.0, 5.0, 200)


class TestBlackbodyBackground:
    @pytest.mark.level0
    def test_basic(self) -> None:
        """L = ε · B(λ, T)."""
        T = 295.0
        eps = 0.95
        bg = BlackbodyBackground(temperature_K=T, emissivity=eps)
        L = bg.spectral_radiance(WAV)
        expected = eps * planck_spectral_radiance(WAV, T)
        np.testing.assert_allclose(L, expected, rtol=1e-12)

    @pytest.mark.level0
    def test_unity_emissivity(self) -> None:
        bg = BlackbodyBackground(temperature_K=300.0)
        L = bg.spectral_radiance(WAV)
        expected = planck_spectral_radiance(WAV, 300.0)
        np.testing.assert_allclose(L, expected, rtol=1e-12)

    @pytest.mark.level0
    def test_zero_temp(self) -> None:
        bg = BlackbodyBackground(temperature_K=0.0)
        L = bg.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 0.0, atol=1e-30)

    @pytest.mark.level0
    def test_negative_temp_raises(self) -> None:
        with pytest.raises(ValueError, match="temperature_K"):
            BlackbodyBackground(temperature_K=-10)

    @pytest.mark.level0
    def test_emissivity_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="emissivity"):
            BlackbodyBackground(temperature_K=300, emissivity=1.1)

    @pytest.mark.level0
    def test_frozen(self) -> None:
        bg = BlackbodyBackground(temperature_K=300)
        with pytest.raises(AttributeError):
            bg.temperature_K = 400  # type: ignore[misc]

    @pytest.mark.level0
    def test_serialization(self) -> None:
        bg = BlackbodyBackground(temperature_K=295, emissivity=0.95)
        d = bg.to_dict()
        assert d["type"] == "blackbody"
        assert d["temperature_K"] == 295


class TestConstantBackground:
    @pytest.mark.level0
    def test_basic(self) -> None:
        bg = ConstantBackground(radiance_W_m2_sr_um=1.5)
        L = bg.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 1.5, rtol=1e-12)

    @pytest.mark.level0
    def test_zero_radiance(self) -> None:
        bg = ConstantBackground(radiance_W_m2_sr_um=0.0)
        L = bg.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 0.0, atol=1e-30)

    @pytest.mark.level0
    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="radiance"):
            ConstantBackground(radiance_W_m2_sr_um=-1.0)


class TestTabulatedBackground:
    @pytest.mark.level0
    def test_basic(self) -> None:
        sd = SpectralData(
            name="bg", wavelength_um=np.linspace(2.0, 6.0, 50),
            values=np.ones(50) * 3.0, unit="W/m2/sr/um", source="test",
        )
        bg = TabulatedBackground(radiance_data=sd)
        L = bg.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 3.0, rtol=1e-6)

    @pytest.mark.level0
    def test_out_of_range_raises(self) -> None:
        sd = SpectralData(
            name="narrow", wavelength_um=np.linspace(4.0, 4.5, 10),
            values=np.ones(10), unit="W/m2/sr/um", source="test",
        )
        bg = TabulatedBackground(radiance_data=sd)
        with pytest.raises(ValueError, match="outside table"):
            bg.spectral_radiance(WAV)

    @pytest.mark.level0
    def test_negative_values_raises(self) -> None:
        sd = SpectralData(
            name="bad", wavelength_um=np.linspace(2.0, 6.0, 10),
            values=np.full(10, -1.0), unit="W/m2/sr/um", source="test",
        )
        with pytest.raises(ValueError, match="non-negative"):
            TabulatedBackground(radiance_data=sd)


class TestCMBBackground:
    @pytest.mark.level0
    def test_cmb_temperature(self) -> None:
        assert CMB_BACKGROUND.temperature_K == 2.7

    @pytest.mark.level0
    def test_cmb_emissivity(self) -> None:
        assert CMB_BACKGROUND.emissivity == 1.0

    @pytest.mark.level0
    def test_cmb_produces_radiance(self) -> None:
        L = CMB_BACKGROUND.spectral_radiance(WAV)
        # CMB at 2.7 K in MWIR is negligible but non-negative
        assert np.all(L >= 0)
