"""Level 0 tests for radiant.io.measurement — measured-curve CSV import.

Fixture files are written inline via tmp_path (the io-test convention;
see test_config.py). Expected values are hand-written, not computed by
RADIANT code (Rule 18).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.io.measurement import (
    MeasuredCurve,
    MeasurementParseError,
    load_measured_curve,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestBasicParsing:
    def test_plain_two_column_csv(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "plain.csv", "10.0,0.90\n20.0,0.80\n30.0,0.70\n")
        curve = load_measured_curve(path)
        np.testing.assert_allclose(curve.x, [10.0, 20.0, 30.0], rtol=1e-12)
        np.testing.assert_allclose(curve.y, [0.90, 0.80, 0.70], rtol=1e-12)
        assert curve.n_points == 3
        assert curve.source_file == str(path)
        assert curve.x_unit is None
        assert curve.x.dtype == np.float64
        assert curve.y.dtype == np.float64

    def test_auto_header_skipped(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "hdr.csv", "freq_cy_mm,mtf\n5.0,0.95\n10.0,0.85\n")
        curve = load_measured_curve(path)
        np.testing.assert_allclose(curve.x, [5.0, 10.0], rtol=1e-12)
        np.testing.assert_allclose(curve.y, [0.95, 0.85], rtol=1e-12)

    def test_auto_with_numeric_first_row_keeps_it(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "nohdr.csv", "1.0,0.99\n2.0,0.98\n")
        curve = load_measured_curve(path)
        assert curve.n_points == 2
        assert curve.x[0] == pytest.approx(1.0, abs=1e-15)

    def test_comment_and_blank_lines_skipped(self, tmp_path: Path) -> None:
        text = "# instrument: bench MTF rig\n\n1.0,0.9\n# mid-file comment\n\n2.0,0.8\n"
        path = _write(tmp_path, "comments.csv", text)
        curve = load_measured_curve(path)
        np.testing.assert_allclose(curve.x, [1.0, 2.0], rtol=1e-12)
        np.testing.assert_allclose(curve.y, [0.9, 0.8], rtol=1e-12)

    def test_integer_skip_header(self, tmp_path: Path) -> None:
        # Two junk rows that would NOT auto-detect (they are numeric).
        path = _write(tmp_path, "skip2.csv", "0.0,0.0\n0.0,0.0\n1.0,0.9\n2.0,0.8\n")
        curve = load_measured_curve(path, skip_header=2)
        np.testing.assert_allclose(curve.x, [1.0, 2.0], rtol=1e-12)

    def test_column_selection_and_delimiter(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "cols.txt", "run1\t1.0\t0.91\nrun2\t2.0\t0.82\n")
        curve = load_measured_curve(path, x_column=1, y_column=2, delimiter="\t")
        np.testing.assert_allclose(curve.x, [1.0, 2.0], rtol=1e-12)
        np.testing.assert_allclose(curve.y, [0.91, 0.82], rtol=1e-12)

    def test_x_unit_recorded(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "unit.csv", "1.0,0.9\n2.0,0.8\n")
        curve = load_measured_curve(path, x_unit="cy/mm")
        assert curve.x_unit == "cy/mm"

    def test_single_point_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "one.csv", "5.0,0.5\n")
        curve = load_measured_curve(path)
        assert curve.n_points == 1


class TestOrderingRules:
    def test_unsorted_x_sorted_with_warning(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "unsorted.csv", "3.0,0.7\n1.0,0.9\n2.0,0.8\n")
        with pytest.warns(UserWarning, match="not\\s+ascending"):
            curve = load_measured_curve(path)
        np.testing.assert_allclose(curve.x, [1.0, 2.0, 3.0], rtol=1e-12)
        np.testing.assert_allclose(curve.y, [0.9, 0.8, 0.7], rtol=1e-12)

    def test_duplicate_x_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "dup.csv", "1.0,0.9\n2.0,0.8\n2.0,0.7\n")
        with pytest.raises(MeasurementParseError, match="duplicated x"):
            load_measured_curve(path)


class TestErrorCases:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(MeasurementParseError, match="file not found"):
            load_measured_curve(tmp_path / "nope.csv")

    def test_empty_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "empty.csv", "")
        with pytest.raises(MeasurementParseError, match="no data rows"):
            load_measured_curve(path)

    def test_comments_only_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "allcomments.csv", "# a\n# b\n\n")
        with pytest.raises(MeasurementParseError, match="no data rows"):
            load_measured_curve(path)

    def test_header_only_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "hdronly.csv", "freq,mtf\n")
        with pytest.raises(MeasurementParseError, match="no data rows"):
            load_measured_curve(path)

    def test_non_numeric_after_header_raises_with_line(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "bad.csv", "freq,mtf\n1.0,0.9\n2.0,oops\n")
        with pytest.raises(MeasurementParseError, match="line 3"):
            load_measured_curve(path)

    def test_too_few_columns(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "narrow.csv", "1.0\n2.0\n")
        with pytest.raises(MeasurementParseError, match="column"):
            load_measured_curve(path)

    def test_nan_cell_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "nan.csv", "1.0,0.9\n2.0,nan\n")
        with pytest.raises(MeasurementParseError, match="NaN or Inf"):
            load_measured_curve(path)

    def test_negative_skip_header_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "ok.csv", "1.0,0.9\n")
        with pytest.raises(MeasurementParseError, match="negative"):
            load_measured_curve(path, skip_header=-1)

    def test_error_is_radiant_error(self, tmp_path: Path) -> None:
        from radiant.core.exceptions import RadiantError

        path = _write(tmp_path, "empty2.csv", "")
        with pytest.raises(RadiantError):
            load_measured_curve(path)


class TestMeasuredCurveDataclass:
    def test_frozen(self) -> None:
        curve = MeasuredCurve(
            x=np.array([1.0, 2.0]),
            y=np.array([0.9, 0.8]),
            source_file="synthetic",
            x_unit=None,
            n_points=2,
        )
        with pytest.raises(AttributeError):
            curve.n_points = 5  # type: ignore[misc]

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(MeasurementParseError, match="different lengths"):
            MeasuredCurve(
                x=np.array([1.0, 2.0]),
                y=np.array([0.9]),
                source_file="synthetic",
                x_unit=None,
                n_points=2,
            )

    def test_n_points_mismatch_raises(self) -> None:
        with pytest.raises(MeasurementParseError, match="n_points"):
            MeasuredCurve(
                x=np.array([1.0, 2.0]),
                y=np.array([0.9, 0.8]),
                source_file="synthetic",
                x_unit=None,
                n_points=3,
            )

    def test_descending_x_raises(self) -> None:
        with pytest.raises(MeasurementParseError, match="ascending"):
            MeasuredCurve(
                x=np.array([2.0, 1.0]),
                y=np.array([0.8, 0.9]),
                source_file="synthetic",
                x_unit=None,
                n_points=2,
            )
