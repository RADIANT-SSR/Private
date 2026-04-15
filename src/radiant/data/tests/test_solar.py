"""Tests for SpectralLibrary — solar irradiance loading and validation."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.data.library import SpectralLibrary


@pytest.fixture
def lib() -> SpectralLibrary:
    return SpectralLibrary()


class TestSolarLoading:
    """Test loading and validating solar irradiance spectrum."""

    def test_solar_loads(self, lib: SpectralLibrary) -> None:
        sd = lib.solar()
        assert sd.name == "solar_irradiance_am0"
        assert sd.unit == "W/m²/µm"
        assert len(sd.wavelength_um) >= 50

    def test_wavelength_ascending(self, lib: SpectralLibrary) -> None:
        sd = lib.solar()
        assert np.all(np.diff(sd.wavelength_um) > 0)

    def test_values_positive(self, lib: SpectralLibrary) -> None:
        sd = lib.solar()
        assert np.all(sd.values >= 0.0)

    def test_integrated_solar_constant(self, lib: SpectralLibrary) -> None:
        """Integrated solar irradiance should be near 1361 W/m² (±5%)."""
        sd = lib.solar()
        total = float(np.trapezoid(sd.values, sd.wavelength_um))
        assert abs(total - 1361.0) / 1361.0 < 0.05, (
            f"Integrated solar irradiance {total:.1f} W/m² "
            f"differs from TSI=1361 W/m² by more than 5%"
        )

    def test_peak_near_visible(self, lib: SpectralLibrary) -> None:
        """Peak spectral irradiance should be near 0.5 µm (visible)."""
        sd = lib.solar()
        peak_idx = int(np.argmax(sd.values))
        peak_wl = float(sd.wavelength_um[peak_idx])
        assert 0.4 <= peak_wl <= 0.7, (
            f"Solar peak at {peak_wl:.2f} µm, expected near 0.5 µm"
        )

    def test_uv_lower_than_visible(self, lib: SpectralLibrary) -> None:
        """UV irradiance (< 0.35 µm) should be lower than visible peak."""
        sd = lib.solar()
        uv_mask = sd.wavelength_um < 0.35
        vis_mask = (sd.wavelength_um >= 0.45) & (sd.wavelength_um <= 0.55)
        if np.any(uv_mask) and np.any(vis_mask):
            uv_max = float(np.max(sd.values[uv_mask]))
            vis_mean = float(np.mean(sd.values[vis_mask]))
            assert uv_max < vis_mean

    def test_ir_decreases(self, lib: SpectralLibrary) -> None:
        """Irradiance should decrease in the IR (> 2 µm)."""
        sd = lib.solar()
        mask_2um = np.abs(sd.wavelength_um - 2.0).argmin()
        mask_5um = np.abs(sd.wavelength_um - 5.0).argmin()
        if mask_5um > mask_2um:
            assert sd.values[mask_5um] < sd.values[mask_2um]
