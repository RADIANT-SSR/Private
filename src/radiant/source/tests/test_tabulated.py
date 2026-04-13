"""Tests for TabulatedRadianceSource.

See RADIANT_Source_Target_System.md §3.5.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.source.tabulated import TabulatedRadianceSource


WAV = np.linspace(3.0, 5.0, 200)


class TestTabulatedRadianceSource:
    @pytest.fixture()
    def radiance_data(self) -> SpectralData:
        return SpectralData(
            name="test_radiance",
            wavelength_um=np.linspace(2.0, 6.0, 50),
            values=np.ones(50) * 5.0,
            unit="W/m2/sr/um",
            source="test",
        )

    def test_constant_value(self, radiance_data: SpectralData) -> None:
        src = TabulatedRadianceSource(radiance_data=radiance_data)
        L = src.spectral_radiance(WAV)
        np.testing.assert_allclose(L, 5.0, rtol=1e-6)

    def test_interpolation(self) -> None:
        wl = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sd = SpectralData(
            name="linear", wavelength_um=wl, values=vals,
            unit="W/m2/sr/um", source="test",
        )
        src = TabulatedRadianceSource(radiance_data=sd)
        result = src.spectral_radiance(np.array([3.5]))
        assert result[0] == pytest.approx(2.5, rel=1e-10)

    def test_out_of_range_raises(self) -> None:
        sd = SpectralData(
            name="narrow", wavelength_um=np.linspace(4.0, 4.5, 10),
            values=np.ones(10), unit="W/m2/sr/um", source="test",
        )
        src = TabulatedRadianceSource(radiance_data=sd)
        with pytest.raises(ValueError, match="outside table"):
            src.spectral_radiance(WAV)

    def test_negative_values_raises(self) -> None:
        sd = SpectralData(
            name="bad", wavelength_um=np.linspace(2.0, 6.0, 10),
            values=np.full(10, -1.0), unit="W/m2/sr/um", source="test",
        )
        with pytest.raises(ValueError, match="non-negative"):
            TabulatedRadianceSource(radiance_data=sd)

    def test_serialization_roundtrip(self, radiance_data: SpectralData) -> None:
        src = TabulatedRadianceSource(radiance_data=radiance_data, name="my_tab")
        d = src.to_dict()
        src2 = TabulatedRadianceSource.from_dict(d)
        L1 = src.spectral_radiance(WAV)
        L2 = src2.spectral_radiance(WAV)
        np.testing.assert_allclose(L1, L2, rtol=1e-12)

    def test_frozen(self, radiance_data: SpectralData) -> None:
        src = TabulatedRadianceSource(radiance_data=radiance_data)
        with pytest.raises(AttributeError):
            src.name = "changed"  # type: ignore[misc]

    def test_deterministic(self, radiance_data: SpectralData) -> None:
        src = TabulatedRadianceSource(radiance_data=radiance_data)
        L1 = src.spectral_radiance(WAV)
        L2 = src.spectral_radiance(WAV)
        np.testing.assert_array_equal(L1, L2)
