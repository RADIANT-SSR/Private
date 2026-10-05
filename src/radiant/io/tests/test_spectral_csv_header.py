"""A spectral CSV may carry a column-header row, and a corrupt one is refused (CU-397).

The reader previously called ``float()`` on the first cell of the first non-comment
line and let a bare ``ValueError`` escape: a file beginning ``wavelength_um,value`` —
what Excel, pandas, and this repo's own substrate tables all write — crashed with
"could not convert string to float: 'wavelength_um'". No file named, no element named,
no remedy, and not a RadiantError, so a caller catching RadiantError did not catch it.
It is reached straight from the GUI's *CSV file…* button.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.io.element_config import ElementConfigError, parse_element_entries

_WL = np.linspace(3.0, 5.0, 9)


def _entry(path: Path) -> dict[str, object]:
    return {
        "name": "M1",
        "transfer_mode": "REFLECTIVE",
        "reflectance": str(path),
        "temperature_K": 290.0,
    }


def _parse(tmp_path: Path, text: str) -> object:
    path = tmp_path / "coating.csv"
    path.write_text(text, encoding="utf-8")
    return parse_element_entries([_entry(path)], _WL, tmp_path)[0]


_ROWS = "3.0,0.97\n4.0,0.96\n5.0,0.95\n"


class TestHeaderRowIsAccepted:
    @pytest.mark.level1
    def test_the_canonical_header_is_skipped(self, tmp_path: Path) -> None:
        element = _parse(tmp_path, "wavelength_um,value\n" + _ROWS)
        assert element.reflectance.values[0] == pytest.approx(0.97, abs=1e-12)

    @pytest.mark.level1
    def test_a_header_with_units_and_spaces_is_skipped(self, tmp_path: Path) -> None:
        element = _parse(tmp_path, "Wavelength [um], Reflectance\n" + _ROWS)
        assert element.reflectance.values[-1] == pytest.approx(0.95, abs=1e-12)

    @pytest.mark.level1
    def test_a_header_gives_the_same_data_as_no_header(self, tmp_path: Path) -> None:
        """The skip must not shift the grid by a row."""
        bare = _parse(tmp_path / "a", _ROWS) if (tmp_path / "a").mkdir() is None else None
        headed = _parse(tmp_path, "wavelength_um,value\n" + _ROWS)
        assert bare is not None
        np.testing.assert_allclose(headed.reflectance.values, bare.reflectance.values, rtol=1e-15)

    @pytest.mark.level1
    def test_an_excel_byte_order_mark_is_tolerated(self, tmp_path: Path) -> None:
        """Excel writes a BOM by default; U+FEFF made the first number unparseable."""
        path = tmp_path / "bom.csv"
        path.write_text("﻿wavelength_um,value\n" + _ROWS, encoding="utf-8")
        element = parse_element_entries([_entry(path)], _WL, tmp_path)[0]
        assert element.reflectance.values[0] == pytest.approx(0.97, abs=1e-12)

    @pytest.mark.level1
    def test_a_comment_line_before_the_header_still_works(self, tmp_path: Path) -> None:
        element = _parse(tmp_path, "# mirror coating, vendor lot 42\nwavelength_um,value\n" + _ROWS)
        assert element.reflectance.values[0] == pytest.approx(0.97, abs=1e-12)


class TestCorruptDataIsStillRefused:
    """The skip is for a header, not an amnesty on unparseable rows."""

    @pytest.mark.level1
    def test_a_nan_row_is_refused_not_mistaken_for_a_header(self, tmp_path: Path) -> None:
        """``float("NaN")`` succeeds, so a letters-only test would wave this through."""
        with pytest.raises(ElementConfigError) as excinfo:
            _parse(tmp_path, "NaN,NaN\n" + _ROWS)
        assert "line 1" in str(excinfo.value)

    @pytest.mark.level1
    def test_an_inf_row_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ElementConfigError):
            _parse(tmp_path, "inf,-inf\n" + _ROWS)

    @pytest.mark.level1
    def test_a_nan_in_the_value_column_is_refused(self, tmp_path: Path) -> None:
        """The one nothing caught: a NaN value interpolated across the whole grid.

        Measured before the guard: ``3.0,0.97 / 4.0,NaN / 5.0,0.95`` on a 9-point grid
        produced 7 NaN reflectances and 7 NaN emissivities, with no error anywhere.
        """
        with pytest.raises(ElementConfigError) as excinfo:
            _parse(tmp_path, "3.0,0.97\n4.0,NaN\n5.0,0.95\n")
        assert "line 2" in str(excinfo.value)

    @pytest.mark.level1
    def test_a_nan_in_the_wavelength_column_names_the_file_and_line(self, tmp_path: Path) -> None:
        """Previously reached SpectralData, which refused it naming neither."""
        with pytest.raises(ElementConfigError) as excinfo:
            _parse(tmp_path, "3.0,0.97\nNaN,0.96\n5.0,0.95\n")
        message = str(excinfo.value)
        assert "coating.csv" in message and "line 2" in message

    @pytest.mark.level1
    def test_a_malformed_number_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ElementConfigError, match="expected two finite"):
            _parse(tmp_path, "3..5,0.97\n" + _ROWS)

    @pytest.mark.level1
    def test_garbage_partway_down_is_refused_not_skipped(self, tmp_path: Path) -> None:
        """Only the FIRST data-bearing row may be a header."""
        with pytest.raises(ElementConfigError) as excinfo:
            _parse(tmp_path, _ROWS + "wavelength_um,value\n6.0,0.94\n")
        assert "line 4" in str(excinfo.value)

    @pytest.mark.level1
    def test_the_refusal_is_actionable(self, tmp_path: Path) -> None:
        """Rule 15: name the file, the line, the element property, and the remedy."""
        with pytest.raises(ElementConfigError) as excinfo:
            _parse(tmp_path, "3..5,0.97\n" + _ROWS)
        message = str(excinfo.value)
        assert "coating.csv" in message
        assert "line 1" in message
        assert "'M1.reflectance'" in message
        assert "two numeric columns" in message

    @pytest.mark.level1
    def test_the_refusal_is_a_radiant_error(self, tmp_path: Path) -> None:
        """A bare ValueError escaped before; RadiantError is the catchable contract."""
        from radiant.core.exceptions import RadiantError

        with pytest.raises(RadiantError):
            _parse(tmp_path, "3..5,0.97\n" + _ROWS)
