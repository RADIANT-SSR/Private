"""Shared two-column CSV reader for boundary-converter path surfaces.

Several S* spec-form paths share the same two-column
``(wavelength_um, value)`` CSV format:

- ``source.target.user_radiance_path``        (S8, W/m²/sr/µm)
- ``source.target.user_intensity_path``       (S10, W/sr/µm)
- ``source.target.reflectance_path``          (S5 spectral, dimensionless)
- ``source.target.albedo_path``               (S6 spectral, dimensionless)
- ``source.target.brightness_temperature_path`` (S11 spectral, K)

This module owns the transport layer only: CSV → :class:`SpectralData`.
It does no physics, no unit conversion, no resampling — every caller
owns those responsibilities.

Rule 2 (units at boundaries): the loader records the caller-supplied
``value_unit`` verbatim on the returned :class:`SpectralData`.  It does
not scale or interpret the values.

Rule 15 (actionable errors): every failure raises
:class:`ParameterBoundsError` with ``what / why / action / context``.
Error messages include the path and (where applicable) the offending
line number.

Rule 17 (no silent failures): malformed rows, empty files, single-row
files, missing files, and non-float tokens all raise — the loader
never skips or defaults.

Rule 19 (one computation, one module): this file owns the CSV-to-
SpectralData transport exclusively.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData


def load_two_column_csv(
    path: Path | str,
    *,
    value_unit: str,
    column_label: str,
    sd_name: str,
    sd_source_prefix: str,
) -> SpectralData:
    """Load a two-column ``(wavelength_um, value)`` CSV into a SpectralData.

    Auto-detects and skips a header row if the first field of line 1
    cannot be parsed as a float.  Returns values on the CSV's native
    wavelength grid — the caller is responsible for resampling onto the
    chain grid.

    Parameters
    ----------
    path:
        Filesystem path to the CSV file.  String paths are coerced to
        :class:`pathlib.Path`.
    value_unit:
        Canonical unit string for the value column (e.g. ``"W/m^2/sr/um"``
        for S8 radiance, ``"K"`` for S11 brightness temperature,
        ``"dimensionless"`` for S5/S6 reflectance).  Recorded verbatim on
        the returned :class:`SpectralData.unit`; the loader does not
        convert units.
    column_label:
        Human-readable label for the value column used in error messages
        (e.g. ``"L_t_source"``, ``"I_t_source"``, ``"reflectance"``,
        ``"brightness_temperature"``).
    sd_name:
        ``SpectralData.name`` on the returned object (e.g.
        ``"source.target.user_radiance"``).
    sd_source_prefix:
        Prefix for ``SpectralData.source`` provenance string.  The
        loader appends ``" (CSV: {path})"``.

    Returns
    -------
    SpectralData
        Values tabulated on the CSV's native wavelength grid, with
        ``unit=value_unit`` and provenance pointing back to the source
        file.

    Raises
    ------
    ParameterBoundsError
        * File does not exist.
        * File is empty (zero usable lines after strip).
        * File has fewer than 2 data rows.
        * Any row has fewer than 2 comma-separated columns.
        * Any row's wavelength or value cannot be parsed as a float.
    """
    path = Path(path)
    prefix = column_label

    if not path.exists():
        raise ParameterBoundsError(
            what=f"{prefix}: CSV file not found at {path!s}",
            why=(
                f"The path loader resolves a two-column CSV of "
                f"(wavelength_um, {column_label}) into a SpectralData."
            ),
            action=(
                "Check the YAML path parameter and ensure the file exists "
                "at the supplied absolute or working-directory-relative "
                "location."
            ),
            context={"path": str(path), "column_label": column_label},
        )

    lines = path.read_text().strip().splitlines()
    if not lines:
        raise ParameterBoundsError(
            what=f"{prefix}: CSV file is empty at {path!s}",
            why=(
                f"The loader needs at least two rows of (wavelength_um, "
                f"{column_label}) to construct a SpectralData object."
            ),
            action=(
                "Populate the CSV with at least two data rows; a header "
                "row is auto-detected and optional."
            ),
            context={"path": str(path), "column_label": column_label},
        )

    start = 0
    try:
        float(lines[0].split(",")[0].strip())
    except ValueError:
        start = 1

    rows: list[tuple[float, float]] = []
    for i, line in enumerate(lines[start:], start=start):
        parts = line.split(",")
        if len(parts) < 2:
            raise ParameterBoundsError(
                what=(
                    f"{prefix}: CSV line {i + 1} in {path!s} has fewer "
                    f"than 2 columns: {line!r}"
                ),
                why=(
                    f"Each data row must carry (wavelength_um, "
                    f"{column_label})."
                ),
                action="Fix the malformed row or remove stray delimiters.",
                context={
                    "path": str(path),
                    "line_number": i + 1,
                    "column_label": column_label,
                },
            )
        try:
            wl = float(parts[0].strip())
            val = float(parts[1].strip())
        except ValueError as err:
            raise ParameterBoundsError(
                what=(
                    f"{prefix}: CSV line {i + 1} in {path!s} cannot be "
                    f"parsed as floats: {line!r}"
                ),
                why=(
                    f"Columns must be parseable as plain floats "
                    f"(wavelength_um, {column_label})."
                ),
                action=(
                    "Remove non-numeric tokens or re-export the CSV as "
                    "two float columns."
                ),
                context={
                    "path": str(path),
                    "line_number": i + 1,
                    "column_label": column_label,
                },
            ) from err
        rows.append((wl, val))

    if len(rows) < 2:
        raise ParameterBoundsError(
            what=(
                f"{prefix}: CSV file {path!s} has fewer than 2 data rows"
            ),
            why=(
                "SpectralData requires at least 2 wavelength samples to "
                "interpolate onto the chain grid."
            ),
            action=(
                f"Provide at least two (wavelength_um, {column_label}) "
                "rows."
            ),
            context={
                "path": str(path),
                "row_count": len(rows),
                "column_label": column_label,
            },
        )

    wl_arr = np.asarray([r[0] for r in rows], dtype=np.float64)
    val_arr = np.asarray([r[1] for r in rows], dtype=np.float64)

    # Rule 15 / 17: reject non-strictly-ascending wavelengths with an
    # actionable message before SpectralData raises a bare ValueError.
    # SpectralData's __post_init__ enforces the same invariant; this
    # check only upgrades the error class at the boundary.
    diffs = np.diff(wl_arr)
    if np.any(diffs <= 0):
        if np.any(diffs == 0):
            raise ParameterBoundsError(
                what=(
                    f"{prefix}: CSV {path!s} has duplicate wavelength "
                    "entries"
                ),
                why=(
                    "Linear interpolation onto the chain grid is "
                    "ambiguous when the same wavelength appears twice."
                ),
                action=(
                    "Deduplicate the wavelength_um column so each "
                    "wavelength appears exactly once."
                ),
                context={
                    "path": str(path),
                    "column_label": column_label,
                },
            )
        raise ParameterBoundsError(
            what=(
                f"{prefix}: CSV {path!s} wavelengths are not strictly "
                "ascending"
            ),
            why=(
                "The loader preserves file row order; downstream "
                "interpolation requires a strictly monotonic grid."
            ),
            action=(
                "Sort the CSV by the wavelength_um column (strictly "
                "ascending) before loading."
            ),
            context={
                "path": str(path),
                "column_label": column_label,
            },
        )

    return SpectralData(
        name=sd_name,
        wavelength_um=wl_arr,
        values=val_arr,
        unit=value_unit,
        source=f"{sd_source_prefix} (CSV: {path!s})",
    )


__all__ = ["load_two_column_csv"]
