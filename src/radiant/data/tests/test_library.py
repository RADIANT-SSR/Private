"""Tests for SpectralLibrary — material emissivity loading and validation."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.data.library import SpectralLibrary


@pytest.fixture
def lib() -> SpectralLibrary:
    return SpectralLibrary()


class TestMaterialsList:
    """Test listing available materials."""

    def test_materials_returns_list(self, lib: SpectralLibrary) -> None:
        materials = lib.materials()
        assert isinstance(materials, list)
        assert len(materials) >= 19

    def test_materials_sorted(self, lib: SpectralLibrary) -> None:
        materials = lib.materials()
        assert materials == sorted(materials)

    def test_known_materials_present(self, lib: SpectralLibrary) -> None:
        materials = lib.materials()
        for name in ["aluminum", "water_calm", "vegetation_green", "blackbody", "steel"]:
            assert name in materials


class TestMaterialLoading:
    """Test loading individual material emissivity spectra."""

    def test_load_aluminum(self, lib: SpectralLibrary) -> None:
        sd = lib.material("aluminum")
        assert sd.name == "emissivity_aluminum"
        assert sd.unit == "dimensionless"
        assert len(sd.wavelength_um) >= 10

    def test_emissivity_range(self, lib: SpectralLibrary) -> None:
        """All emissivity values must be in [0, 1]."""
        for name in lib.materials():
            sd = lib.material(name)
            assert np.all(sd.values >= 0.0), f"{name}: emissivity < 0"
            assert np.all(sd.values <= 1.0), f"{name}: emissivity > 1"

    def test_wavelength_ascending(self, lib: SpectralLibrary) -> None:
        """Wavelengths must be strictly ascending."""
        for name in lib.materials():
            sd = lib.material(name)
            assert np.all(np.diff(sd.wavelength_um) > 0), f"{name}: not ascending"

    def test_blackbody_unity(self, lib: SpectralLibrary) -> None:
        """Blackbody emissivity must be 1.0 everywhere."""
        sd = lib.material("blackbody")
        np.testing.assert_allclose(sd.values, 1.0, atol=1e-10)

    def test_metals_low_emissivity(self, lib: SpectralLibrary) -> None:
        """Polished metals should have low emissivity (< 0.3 at most wavelengths)."""
        for name in ["aluminum", "gold", "copper"]:
            sd = lib.material(name)
            median_emissivity = float(np.median(sd.values))
            assert median_emissivity < 0.3, (
                f"{name}: median emissivity {median_emissivity:.3f} too high for polished metal"
            )

    def test_paint_black_high_emissivity(self, lib: SpectralLibrary) -> None:
        """Black paint should have high emissivity (> 0.85 on average)."""
        sd = lib.material("paint_black")
        mean_emissivity = float(np.mean(sd.values))
        assert mean_emissivity > 0.85, f"Black paint mean emissivity {mean_emissivity:.3f} too low"

    def test_unknown_material_raises(self, lib: SpectralLibrary) -> None:
        with pytest.raises(KeyError, match="Unknown material"):
            lib.material("unobtanium")

    def test_material_info(self, lib: SpectralLibrary) -> None:
        info = lib.material_info("aluminum")
        assert "description" in info
        assert "default_temperature_K" in info
        assert info["default_temperature_K"] > 0

    def test_material_info_unknown_raises(self, lib: SpectralLibrary) -> None:
        with pytest.raises(KeyError, match="Unknown material"):
            lib.material_info("unobtanium")

    def test_kirchhoff_consistency(self, lib: SpectralLibrary) -> None:
        """For opaque materials, emissivity + reflectance = 1.
        We can only check that emissivity is physically consistent (0 ≤ ε ≤ 1),
        since reflectance data is not included."""
        for name in lib.materials():
            sd = lib.material(name)
            assert np.all(sd.values >= 0.0) and np.all(sd.values <= 1.0)

    def test_temperature_plausible(self, lib: SpectralLibrary) -> None:
        """Default temperatures should be in a plausible range (200–400 K)."""
        for name in lib.materials():
            info = lib.material_info(name)
            t = info["default_temperature_K"]
            assert 200 <= t <= 400, f"{name}: default temp {t} K out of plausible range"

    def test_source_provenance(self, lib: SpectralLibrary) -> None:
        """Every material should have a non-empty source string."""
        for name in lib.materials():
            sd = lib.material(name)
            assert sd.source and len(sd.source) > 5
