"""Level 0 tests for radiant.io.aster_library (scenario 1.3).

Anchors are hand values (Rule 18): reflectance 2.5% → emissivity 0.975
(opaque Kirchhoff); band averages on constructed ramps.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.io.aster_library import (
    AsterLibraryError,
    load_aster_spectrum,
)

HEADER = """\
Name: Conifer forest canopy
Type: vegetation
Class: tree
Subclass: needle
Particle Size: n/a
Sample No.: veg.needle.conifer
Owner: JPL
Wavelength Range: ALL
Origin: synthetic test fixture
Description: Test spectrum in ASTER library text format.
Measurement: Directional Hemispherical Reflectance
First Column: X
Second Column: Y
X Units: Wavelength (micrometers)
Y Units: Reflectance (percent)
First X Value: 12.0
Last X Value: 3.0
Number of X Values: 4
Additional Information: none
"""


def _write(tmp_path: Path, body: str, header: str = HEADER) -> Path:
    p = tmp_path / "spectrum.txt"
    p.write_text(header + body, encoding="utf-8")
    return p


class TestLoad:
    def test_descending_wavelength_file_is_sorted_ascending(self, tmp_path: Path) -> None:
        """Real ASTER files list wavelength descending; loader sorts."""
        p = _write(tmp_path, "12.0 3.0\n10.0 2.5\n5.0 4.0\n3.0 6.0\n")
        spec = load_aster_spectrum(p)
        assert spec.wavelength_um == pytest.approx([3.0, 5.0, 10.0, 12.0], rel=1e-12)
        assert spec.reflectance == pytest.approx([0.06, 0.04, 0.025, 0.03], rel=1e-12)
        assert spec.name == "Conifer forest canopy"
        assert spec.y_units_percent is True

    def test_fraction_units_header(self, tmp_path: Path) -> None:
        header = HEADER.replace("Reflectance (percent)", "Reflectance (fraction)")
        p = _write(tmp_path, "12.0 0.03\n3.0 0.06\n", header=header)
        spec = load_aster_spectrum(p)
        assert spec.reflectance == pytest.approx([0.06, 0.03], rel=1e-12)
        assert spec.y_units_percent is False

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AsterLibraryError, match="does not exist"):
            load_aster_spectrum(tmp_path / "nope.txt")

    def test_no_data_rows_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "")
        with pytest.raises(AsterLibraryError, match="no data rows"):
            load_aster_spectrum(p)

    def test_malformed_data_row_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "12.0 3.0\nbroken row here\n")
        with pytest.raises(AsterLibraryError, match="could not parse"):
            load_aster_spectrum(p)

    def test_reflectance_above_100pct_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "12.0 150.0\n3.0 6.0\n")
        with pytest.raises(AsterLibraryError, match="reflectance"):
            load_aster_spectrum(p)


class TestEmissivity:
    def test_kirchhoff_opaque_hand_anchor(self, tmp_path: Path) -> None:
        """ε = 1 − ρ: reflectance 2.5% → emissivity 0.975."""
        p = _write(tmp_path, "12.0 3.0\n10.0 2.5\n3.0 6.0\n")
        spec = load_aster_spectrum(p)
        eps = spec.emissivity()
        assert eps[1] == pytest.approx(0.975, rel=1e-12)  # at 10 µm

    def test_band_averaged_emissivity_ramp(self, tmp_path: Path) -> None:
        """Linear ρ ramp 2%→4% over 8–12 µm: mean ε over the band = 0.97."""
        p = _write(tmp_path, "12.0 4.0\n8.0 2.0\n")
        spec = load_aster_spectrum(p)
        eps_band = spec.band_averaged_emissivity(8.0, 12.0)
        assert eps_band == pytest.approx(0.97, rel=1e-9)

    def test_band_outside_data_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "12.0 3.0\n8.0 2.0\n")
        with pytest.raises(AsterLibraryError, match="outside"):
            spec = load_aster_spectrum(p)
            spec.band_averaged_emissivity(3.0, 5.0)
