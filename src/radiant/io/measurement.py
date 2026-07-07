"""Measured-curve import — load lab / field measurement data from CSV.

Provides :func:`load_measured_curve` to read a two-column (x, y) curve
from a delimited text file into an immutable :class:`MeasuredCurve`,
for comparison against RADIANT predictions (Gap 30). Typical inputs:
measured MTF vs spatial frequency, measured spectral transmission vs
wavelength.

Parsing rules:

- Lines starting with ``#`` are comments and skipped.
- Blank lines are skipped.
- ``skip_header="auto"`` (default): if the first non-comment,
  non-blank row does not parse as numeric in the requested columns it
  is treated as a column-header row and skipped. An integer skips
  exactly that many data rows unconditionally.
- Any non-numeric value after the header is a hard
  :class:`MeasurementParseError` (no silent row dropping — Rule 17).
- ``x`` must be strictly ascending. Out-of-order rows are sorted with
  a ``UserWarning``; duplicated x values raise, since the intended
  ordering is then ambiguous.

Excel workbooks are out of scope — export the sheet to CSV first.
"""

from __future__ import annotations

import csv
import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError

logger = logging.getLogger(__name__)

__all__ = ["MeasuredCurve", "MeasurementParseError", "load_measured_curve"]


class MeasurementParseError(RadiantError):
    """Raised when a measurement file cannot be parsed into a valid curve.

    Attributes
    ----------
    path:
        File path that triggered the error (``None`` when the error
        comes from direct :class:`MeasuredCurve` construction).
    detail:
        Human-readable description of the problem, including what to do
        about it.
    """

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"MeasurementParseError{loc}: {detail}")


@dataclass(frozen=True)
class MeasuredCurve:
    """An immutable measured (x, y) curve loaded from a file.

    Attributes
    ----------
    x:
        Independent variable, float64, strictly ascending. Units are
        whatever the file uses — record them in ``x_unit``.
    y:
        Dependent variable, float64, same length as ``x``.
    source_file:
        Path the curve was loaded from (or a caller-supplied label for
        synthetic curves).
    x_unit:
        Unit string for ``x`` (e.g. ``"cy/mm"``, ``"um"``); ``None``
        when unknown.
    n_points:
        Number of (x, y) samples; must equal ``len(x)``.
    """

    x: npt.NDArray[np.float64]
    y: npt.NDArray[np.float64]
    source_file: str
    x_unit: str | None
    n_points: int

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=np.float64)
        y = np.asarray(self.y, dtype=np.float64)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        if x.ndim != 1 or y.ndim != 1:
            raise MeasurementParseError(
                f"MeasuredCurve arrays must be 1-D; got x.ndim={x.ndim}, "
                f"y.ndim={y.ndim}. Pass flat (x, y) column vectors.",
                path=self.source_file,
            )
        if x.shape[0] != y.shape[0]:
            raise MeasurementParseError(
                f"x and y have different lengths ({x.shape[0]} vs {y.shape[0]}). "
                "Each x sample needs exactly one y sample.",
                path=self.source_file,
            )
        if self.n_points != x.shape[0]:
            raise MeasurementParseError(
                f"n_points={self.n_points} does not match len(x)={x.shape[0]}. "
                "Construct MeasuredCurve with n_points=len(x).",
                path=self.source_file,
            )
        if x.shape[0] == 0:
            raise MeasurementParseError(
                "curve has zero points. Provide at least one (x, y) sample.",
                path=self.source_file,
            )
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise MeasurementParseError(
                "curve contains NaN or Inf values. Remove or repair the "
                "non-finite rows in the source data before loading.",
                path=self.source_file,
            )
        if x.shape[0] > 1 and not np.all(np.diff(x) > 0.0):
            raise MeasurementParseError(
                "x values are not strictly ascending after load. Sort the "
                "data and remove duplicate x values.",
                path=self.source_file,
            )


def _parse_row(
    row: list[str],
    x_column: int,
    y_column: int,
    line_no: int,
    path: Path,
) -> tuple[float, float]:
    """Parse one CSV row into (x, y) floats with actionable errors."""
    needed = max(x_column, y_column)
    if len(row) <= needed:
        raise MeasurementParseError(
            f"line {line_no}: row has {len(row)} column(s) but "
            f"x_column={x_column}, y_column={y_column} require at least "
            f"{needed + 1}. Check the delimiter (currently splitting into "
            f"{row!r}) and the column indices.",
            path=path,
        )
    try:
        x_val = float(row[x_column])
        y_val = float(row[y_column])
    except ValueError as exc:
        raise MeasurementParseError(
            f"line {line_no}: could not parse "
            f"x={row[x_column]!r}, y={row[y_column]!r} as numbers ({exc}). "
            "Fix the offending row, or if it is a units/header row, use "
            "skip_header to skip it.",
            path=path,
        ) from exc
    return x_val, y_val


def _row_is_numeric(row: list[str], x_column: int, y_column: int) -> bool:
    """True if the requested columns of *row* both parse as floats."""
    if len(row) <= max(x_column, y_column):
        return False
    try:
        float(row[x_column])
        float(row[y_column])
    except ValueError:
        return False
    return True


def load_measured_curve(
    path: str | Path,
    *,
    x_column: int = 0,
    y_column: int = 1,
    delimiter: str = ",",
    skip_header: int | Literal["auto"] = "auto",
    x_unit: str | None = None,
) -> MeasuredCurve:
    """Load a two-column measured curve from a delimited text file.

    Parameters
    ----------
    path:
        CSV (or other delimited text) file to read.
    x_column, y_column:
        Zero-based column indices for the independent and dependent
        variables.
    delimiter:
        Field delimiter (default ``","``).
    skip_header:
        ``"auto"`` (default) skips the first non-comment row if it is
        non-numeric in the requested columns; an integer skips exactly
        that many rows unconditionally.
    x_unit:
        Unit string to attach to the x axis (e.g. ``"cy/mm"``). RADIANT
        does not convert here — conversion happens where the curve is
        consumed (e.g. :func:`radiant.api.compare.compare_mtf`).

    Returns
    -------
    MeasuredCurve
        Immutable curve with strictly ascending float64 x.

    Raises
    ------
    MeasurementParseError
        If the file is missing, empty, has no data rows, contains
        non-numeric data after the header, has too few columns, or has
        duplicated x values.

    Warns
    -----
    UserWarning
        When x values are out of order and are sorted on load.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise MeasurementParseError(
            f"file not found: {file_path}. Check the path (cwd-relative "
            "paths depend on where RADIANT is invoked; prefer absolute paths).",
            path=file_path,
        )
    if isinstance(skip_header, int) and skip_header < 0:
        raise MeasurementParseError(
            f"skip_header={skip_header} is negative. Use 'auto' or a non-negative row count.",
            path=file_path,
        )

    xs: list[float] = []
    ys: list[float] = []
    rows_skipped = 0
    first_data_row_seen = False

    with file_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for line_no, raw_row in enumerate(reader, start=1):
            row = [cell.strip() for cell in raw_row]
            # Blank line: every cell empty (csv yields [] for truly empty lines).
            if not row or all(cell == "" for cell in row):
                continue
            if row[0].startswith("#"):
                continue
            if isinstance(skip_header, int) and rows_skipped < skip_header:
                rows_skipped += 1
                continue
            if (
                skip_header == "auto"
                and not first_data_row_seen
                and not _row_is_numeric(row, x_column, y_column)
            ):
                logger.debug(
                    "load_measured_curve: auto-skipping header row %d of %s: %r",
                    line_no,
                    file_path,
                    row,
                )
                first_data_row_seen = True
                continue
            first_data_row_seen = True
            x_val, y_val = _parse_row(row, x_column, y_column, line_no, file_path)
            xs.append(x_val)
            ys.append(y_val)

    if not xs:
        raise MeasurementParseError(
            "no data rows found (file is empty, all comments/blank, or the "
            "header consumed every row). Check the file contents and the "
            "skip_header setting.",
            path=file_path,
        )

    x_arr = np.asarray(xs, dtype=np.float64)
    y_arr = np.asarray(ys, dtype=np.float64)

    if not np.all(np.isfinite(x_arr)) or not np.all(np.isfinite(y_arr)):
        raise MeasurementParseError(
            "file contains NaN or Inf values (e.g. a literal 'nan' cell). "
            "Remove or repair the non-finite rows before loading.",
            path=file_path,
        )

    if x_arr.size > 1:
        sorted_x = np.sort(x_arr)
        dup_mask = np.diff(sorted_x) == 0.0
        if np.any(dup_mask):
            first_dup = float(sorted_x[:-1][dup_mask][0])
            raise MeasurementParseError(
                f"duplicated x values found (e.g. x={first_dup:g} appears "
                "more than once); the curve ordering is ambiguous. De-duplicate "
                "the source data (average repeated readings first if needed).",
                path=file_path,
            )
        if not np.all(np.diff(x_arr) > 0.0):
            warnings.warn(
                f"load_measured_curve: x values in {file_path} are not "
                "ascending; sorting by x on load.",
                UserWarning,
                stacklevel=2,
            )
            order = np.argsort(x_arr)
            x_arr = x_arr[order]
            y_arr = y_arr[order]

    return MeasuredCurve(
        x=x_arr,
        y=y_arr,
        source_file=str(file_path),
        x_unit=x_unit,
        n_points=int(x_arr.size),
    )
