"""Level 0 tests for radiant.io.target_library (scenario 4.1).

Anchors are hand values (Rule 18): projected_area = length × width.
openpyxl is required for these tests (declared in the [scenarios]
extra); they are skipped when it is absent, matching the loader's
lazy-import behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from radiant.io.target_library import (  # noqa: E402
    TargetEntry,
    TargetLibraryError,
    load_target_library,
)

HEADERS = [
    "target_name",
    "length_m",
    "width_m",
    "height_m",
    "temperature_K",
    "emissivity",
    "material",
]


def _write_xlsx(path: Path, rows: list[list[object]], headers: list[str] = HEADERS) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Targets"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


class TestLoad:
    def test_basic_load_and_projected_area(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "lib.xlsx",
            [
                ["MBT tank", 7.9, 3.6, 2.4, 310.0, 0.90, "painted steel"],
                ["Cargo truck", 8.0, 2.5, 3.2, 300.0, 0.92, "painted steel"],
            ],
        )
        lib = load_target_library(p)
        assert len(lib) == 2
        tank = lib[0]
        assert tank.target_name == "MBT tank"
        assert tank.projected_area_m2 == pytest.approx(7.9 * 3.6, rel=1e-12)
        assert tank.temperature_K == pytest.approx(310.0, rel=1e-12)

    def test_entries_are_immutable(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "lib.xlsx",
            [
                ["A", 1.0, 1.0, 1.0, 300.0, 0.9, "m"],
            ],
        )
        entry = load_target_library(p)[0]
        with pytest.raises(AttributeError):
            entry.length_m = 2.0  # type: ignore[misc]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TargetLibraryError, match="does not exist"):
            load_target_library(tmp_path / "nope.xlsx")

    def test_missing_column_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "bad.xlsx", [["A", 1.0, 1.0]], headers=["target_name", "length_m", "width_m"]
        )
        with pytest.raises(TargetLibraryError, match="temperature_K"):
            load_target_library(p)

    def test_blank_rows_skipped(self, tmp_path: Path) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(HEADERS)
        ws.append(["A", 1.0, 1.0, 1.0, 300.0, 0.9, "m"])
        ws.append([None] * 7)
        ws.append(["B", 2.0, 2.0, 2.0, 305.0, 0.8, "m"])
        p = tmp_path / "gaps.xlsx"
        wb.save(p)
        lib = load_target_library(p)
        assert [e.target_name for e in lib] == ["A", "B"]


class TestValidation:
    def test_nonpositive_dimension_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "bad.xlsx",
            [
                ["A", 0.0, 1.0, 1.0, 300.0, 0.9, "m"],
            ],
        )
        with pytest.raises(TargetLibraryError, match="positive"):
            load_target_library(p)

    def test_emissivity_out_of_range_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "bad.xlsx",
            [
                ["A", 1.0, 1.0, 1.0, 300.0, 1.5, "m"],
            ],
        )
        with pytest.raises(TargetLibraryError, match="emissivity"):
            load_target_library(p)

    def test_nonnumeric_value_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "bad.xlsx",
            [
                ["A", "big", 1.0, 1.0, 300.0, 0.9, "m"],
            ],
        )
        with pytest.raises(TargetLibraryError, match="numeric"):
            load_target_library(p)

    def test_duplicate_target_name_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "bad.xlsx",
            [
                ["A", 1.0, 1.0, 1.0, 300.0, 0.9, "m"],
                ["A", 2.0, 2.0, 2.0, 305.0, 0.8, "m"],
            ],
        )
        with pytest.raises(TargetLibraryError, match="duplicate"):
            load_target_library(p)

    def test_empty_library_raises(self, tmp_path: Path) -> None:
        p = _write_xlsx(tmp_path / "empty.xlsx", [])
        with pytest.raises(TargetLibraryError, match="no target rows"):
            load_target_library(p)


class TestRoundTrip:
    def test_to_dict(self, tmp_path: Path) -> None:
        p = _write_xlsx(
            tmp_path / "lib.xlsx",
            [
                ["A", 2.0, 3.0, 1.0, 300.0, 0.9, "steel"],
            ],
        )
        d = load_target_library(p)[0].to_dict()
        clone = TargetEntry(**d)
        assert clone.projected_area_m2 == pytest.approx(6.0, rel=1e-12)
