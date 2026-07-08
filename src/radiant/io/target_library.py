"""Target-library import — load a target set from a mission Excel workbook.

Provides :func:`load_target_library` to read the program-office target
list (columns ``target_name, length_m, width_m, height_m,
temperature_K, emissivity, material``) into a tuple of validated
:class:`TargetEntry` objects, computing ``projected_area_m2 =
length_m × width_m`` for the sub-pixel/point-source area term. Found
needed by scenario 4.1 (detection matrix briefings).

openpyxl is imported lazily: it lives in the ``[scenarios]`` optional
dependency group, not the core install, so this module raises an
actionable :class:`TargetLibraryError` naming the extra when the
package is absent instead of breaking ``import radiant.io`` (same
optional-dependency pattern as the MODTRAN backend).

Emissivity here is a scene-target material property — a legitimate
independent input (Rule 5 applies to optical elements, not targets).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from radiant.core.exceptions import RadiantError

__all__ = ["TargetEntry", "TargetLibraryError", "load_target_library"]

_REQUIRED_COLUMNS = (
    "target_name",
    "length_m",
    "width_m",
    "height_m",
    "temperature_K",
    "emissivity",
    "material",
)


class TargetLibraryError(RadiantError):
    """Raised when a target-library workbook cannot be parsed or validated."""

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"TargetLibraryError{loc}: {detail}")


@dataclass(frozen=True)
class TargetEntry:
    """One validated target-library row (canonical units).

    ``projected_area_m2`` is derived (length × width — the overhead-look
    footprint); it is not an input column.
    """

    target_name: str
    length_m: float
    width_m: float
    height_m: float
    temperature_K: float
    emissivity: float
    material: str

    def __post_init__(self) -> None:
        for field_name in ("length_m", "width_m", "height_m", "temperature_K"):
            value = getattr(self, field_name)
            if not value > 0.0:
                raise TargetLibraryError(
                    f"target {self.target_name!r}: {field_name} must be positive, got {value}."
                )
        if not 0.0 < self.emissivity <= 1.0:
            raise TargetLibraryError(
                f"target {self.target_name!r}: emissivity must be in (0, 1], got {self.emissivity}."
            )

    @property
    def projected_area_m2(self) -> float:
        """Overhead-look projected area [m²]: length × width."""
        return self.length_m * self.width_m

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain types (projected area is derived, not stored)."""
        return asdict(self)


def _require_openpyxl() -> Any:
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise TargetLibraryError(
            "openpyxl is required to read target-library workbooks. "
            'Install the scenarios extra: pip install -e ".[scenarios]".'
        ) from exc
    return openpyxl


def load_target_library(
    path: str | Path,
    *,
    sheet: str | None = None,
) -> tuple[TargetEntry, ...]:
    """Load a target library from an Excel workbook.

    Parameters
    ----------
    path:
        ``.xlsx`` workbook whose first row is the header
        (``target_name, length_m, width_m, height_m, temperature_K,
        emissivity, material`` in any column order).
    sheet:
        Worksheet name; default is the active sheet.

    Returns
    -------
    tuple[TargetEntry, ...]
        Validated entries in row order.

    Raises
    ------
    TargetLibraryError
        Missing file/columns, non-numeric or unphysical values,
        duplicate target names, or an empty library.
    """
    p = Path(path)
    if not p.is_file():
        raise TargetLibraryError(
            f"file {p} does not exist or is not a file. Check the path to "
            "the target-library workbook.",
            path=p,
        )
    openpyxl = _require_openpyxl()
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb[sheet] if sheet is not None else wb.active

    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        raise TargetLibraryError("workbook sheet is empty.", path=p) from None

    col_index: dict[str, int] = {}
    for idx, cell in enumerate(header):
        if cell is not None:
            col_index[str(cell).strip()] = idx
    missing = [c for c in _REQUIRED_COLUMNS if c not in col_index]
    if missing:
        raise TargetLibraryError(
            f"header is missing required column(s) {missing}. Found "
            f"{sorted(col_index)}; expected {list(_REQUIRED_COLUMNS)} "
            "(any column order).",
            path=p,
        )

    def cell_in(row: tuple[Any, ...], col: str) -> Any:
        idx = col_index[col]
        return row[idx] if idx < len(row) else None

    entries: list[TargetEntry] = []
    seen_names: set[str] = set()
    for row_no, row in enumerate(rows, start=2):
        if row is None or all(cell is None for cell in row):
            continue  # blank spacer row

        name = cell_in(row, "target_name")
        if name is None:
            raise TargetLibraryError(
                f"row {row_no}: target_name is empty in a non-blank row.",
                path=p,
            )
        name = str(name).strip()
        if name in seen_names:
            raise TargetLibraryError(
                f"row {row_no}: duplicate target name {name!r} — names key "
                "the detection matrix and must be unique.",
                path=p,
            )
        seen_names.add(name)

        numeric: dict[str, float] = {}
        for col in ("length_m", "width_m", "height_m", "temperature_K", "emissivity"):
            raw = cell_in(row, col)
            try:
                numeric[col] = float(raw)
            except (TypeError, ValueError):
                raise TargetLibraryError(
                    f"row {row_no}: {col} = {raw!r} is not numeric.",
                    path=p,
                ) from None

        try:
            entries.append(
                TargetEntry(
                    target_name=name,
                    material=str(cell_in(row, "material") or "").strip(),
                    **numeric,
                )
            )
        except TargetLibraryError as exc:
            raise TargetLibraryError(f"row {row_no}: {exc.detail}", path=p) from None

    if not entries:
        raise TargetLibraryError("workbook contains no target rows below the header.", path=p)
    return tuple(entries)
