"""Vendor QE-curve import — load QE(λ) from a detector-vendor CSV.

Provides :func:`load_qe_csv` to read a two-column wavelength-vs-QE
vendor export into an immutable :class:`QeCurve` in RADIANT canonical
units (wavelength in µm, QE as a fraction). Found needed by scenario
2.1 (detector datasheet import): vendors ship QE curves in mixed
conventions — ``wavelength_nm, QE_pct`` and ``lambda_um,
quantum_efficiency`` are both common — and the conversion must happen
exactly once, at this file-reader boundary (Rule 2).

CSV mechanics (comments, header auto-detection, numeric validation,
ascending-x enforcement) are delegated to
:func:`radiant.io.measurement.load_measured_curve`; this module adds
the unit handling and QE-specific validation.

Unit resolution (``"auto"`` default):

- Wavelength: the header token containing ``nm`` → nanometres;
  ``um`` / ``µm`` / ``micron`` → micrometres. No header hint → a
  :class:`QeCsvParseError` asking for an explicit ``wavelength_unit``
  (no magnitude-based guessing — Rule 17).
- QE: the header token containing ``pct`` / ``percent`` / ``%`` →
  percent; otherwise fraction. A fraction-mode curve with values > 1
  raises with a pointer at ``qe_unit="percent"`` rather than silently
  producing unphysical QE.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError
from radiant.io.measurement import load_measured_curve

__all__ = ["QeCsvParseError", "QeCurve", "load_qe_csv"]

WavelengthUnit = Literal["auto", "nm", "um"]
QeUnit = Literal["auto", "percent", "fraction"]
OutOfRange = Literal["error", "zero", "clamp"]


class QeCsvParseError(RadiantError):
    """Raised when a vendor QE CSV cannot be parsed into a valid curve."""

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"QeCsvParseError{loc}: {detail}")


@dataclass(frozen=True)
class QeCurve:
    """An immutable QE(λ) curve in canonical units.

    Attributes
    ----------
    wavelength_um:
        Wavelength grid [µm], float64, strictly ascending, positive.
    qe:
        Quantum efficiency [fraction, 0–1], same length.
    source_file:
        Path the curve was loaded from.
    n_points:
        Number of samples.
    """

    wavelength_um: npt.NDArray[np.float64]
    qe: npt.NDArray[np.float64]
    source_file: str
    n_points: int

    def __post_init__(self) -> None:
        wl = np.asarray(self.wavelength_um, dtype=np.float64)
        qe = np.asarray(self.qe, dtype=np.float64)
        object.__setattr__(self, "wavelength_um", wl)
        object.__setattr__(self, "qe", qe)
        if wl.shape != qe.shape or wl.ndim != 1:
            raise QeCsvParseError(
                f"wavelength and qe must be equal-length 1-D arrays; got "
                f"shapes {wl.shape} and {qe.shape}.",
                path=self.source_file,
            )
        if wl.shape[0] == 0:
            raise QeCsvParseError("curve has zero points.", path=self.source_file)
        if np.any(wl <= 0.0):
            raise QeCsvParseError(
                f"wavelengths must be positive; min = {wl.min()} µm. Check "
                "the wavelength_unit (nm values mis-read as µm would be "
                "large, zero/negative rows are data errors).",
                path=self.source_file,
            )
        if np.any(qe < 0.0):
            raise QeCsvParseError(
                f"QE contains negative values (min = {qe.min()}). Remove or "
                "repair the offending rows — negative QE is unphysical.",
                path=self.source_file,
            )
        if np.any(qe > 1.0):
            raise QeCsvParseError(
                f"QE > 1 after conversion (max = {qe.max()}). If the file "
                'is in percent, pass qe_unit="percent" (or use a header '
                "containing 'pct'/'percent'/'%').",
                path=self.source_file,
            )

    # -- Evaluation -------------------------------------------------------

    def evaluate(
        self,
        wavelength_um: npt.NDArray[np.float64],
        *,
        out_of_range: OutOfRange = "error",
    ) -> npt.NDArray[np.float64]:
        """Interpolate QE onto *wavelength_um* [µm].

        Parameters
        ----------
        wavelength_um:
            Target wavelength grid [µm].
        out_of_range:
            ``"error"`` (default) raises when any target wavelength lies
            outside the measured range — extrapolating a QE curve past
            its cutoff silently is how detectors grow imaginary response.
            ``"zero"`` returns 0 outside the range (physical for a
            cutoff); ``"clamp"`` holds the edge values.
        """
        wl = np.asarray(wavelength_um, dtype=np.float64)
        lo, hi = float(self.wavelength_um[0]), float(self.wavelength_um[-1])
        outside = (wl < lo) | (wl > hi)
        if out_of_range == "error" and bool(np.any(outside)):
            bad = wl[outside]
            raise QeCsvParseError(
                f"{bad.size} wavelength(s) (e.g. {bad.flat[0]:.4g} µm) lie "
                f"outside the measured QE range [{lo:.4g}, {hi:.4g}] µm. "
                'Pass out_of_range="zero" (past-cutoff response is zero) '
                'or "clamp", or restrict the evaluation band.',
                path=self.source_file,
            )
        out = np.interp(wl, self.wavelength_um, self.qe)
        if out_of_range == "zero":
            out = np.where(outside, 0.0, out)
        return np.asarray(out, dtype=np.float64)

    def band_averaged_qe(self, lam_min_um: float, lam_max_um: float) -> float:
        """Mean QE over [lam_min_um, lam_max_um] via trapezoidal integration."""
        if not lam_min_um < lam_max_um:
            raise QeCsvParseError(
                f"band_averaged_qe: need lam_min < lam_max, got ({lam_min_um}, {lam_max_um}) µm.",
                path=self.source_file,
            )
        grid = np.linspace(lam_min_um, lam_max_um, 501)
        vals = self.evaluate(grid, out_of_range="error")
        return float(np.trapezoid(vals, grid) / (lam_max_um - lam_min_um))

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain types (round-trips via :meth:`from_dict`)."""
        return {
            "wavelength_um": self.wavelength_um.tolist(),
            "qe": self.qe.tolist(),
            "source_file": self.source_file,
            "n_points": self.n_points,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QeCurve:
        """Rebuild from :meth:`to_dict` output."""
        return cls(
            wavelength_um=np.asarray(d["wavelength_um"], dtype=np.float64),
            qe=np.asarray(d["qe"], dtype=np.float64),
            source_file=str(d["source_file"]),
            n_points=int(d["n_points"]),
        )


def _header_tokens(path: Path, delimiter: str) -> list[str]:
    """Return the lower-cased tokens of the first non-comment CSV row."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh, delimiter=delimiter):
            if not row or (row[0].lstrip().startswith("#")):
                continue
            return [cell.strip().lower() for cell in row]
    return []


def _resolve_wavelength_unit(token: str, unit: WavelengthUnit, path: Path) -> str:
    if unit != "auto":
        return unit
    if "nm" in token:
        return "nm"
    if "um" in token or "µm" in token or "micron" in token:
        return "um"
    raise QeCsvParseError(
        f"cannot infer the wavelength unit from header column {token!r}. "
        'Pass wavelength_unit="nm" or "um" explicitly.',
        path=path,
    )


def _resolve_qe_unit(token: str, unit: QeUnit) -> str:
    if unit != "auto":
        return unit
    if "pct" in token or "percent" in token or "%" in token:
        return "percent"
    return "fraction"


def load_qe_csv(
    path: str | Path,
    *,
    wavelength_column: int = 0,
    qe_column: int = 1,
    delimiter: str = ",",
    wavelength_unit: WavelengthUnit = "auto",
    qe_unit: QeUnit = "auto",
) -> QeCurve:
    """Load a vendor QE curve CSV into canonical units (µm, fraction).

    Parameters
    ----------
    path:
        CSV file: one wavelength column, one QE column, optional header
        and ``#`` comments.
    wavelength_column, qe_column:
        Zero-based column indices.
    delimiter:
        Field delimiter (default ``","``).
    wavelength_unit:
        ``"auto"`` (from the header token), ``"nm"``, or ``"um"``.
    qe_unit:
        ``"auto"`` (percent iff the header token says pct/percent/%),
        ``"percent"``, or ``"fraction"``.

    Returns
    -------
    QeCurve
        Canonical-units curve, strictly ascending in wavelength.

    Raises
    ------
    QeCsvParseError
        Missing/invalid file, unresolvable units, or unphysical QE.
    """
    p = Path(path)
    if not p.is_file():
        raise QeCsvParseError(
            f"file {p} does not exist or is not a file. Check the path; "
            "vendor QE curves are the CSV export of the datasheet plot.",
            path=p,
        )

    header = _header_tokens(p, delimiter)
    wl_token = header[wavelength_column] if len(header) > wavelength_column else ""
    qe_token = header[qe_column] if len(header) > qe_column else ""

    wl_unit = _resolve_wavelength_unit(wl_token, wavelength_unit, p)
    q_unit = _resolve_qe_unit(qe_token, qe_unit)

    try:
        raw = load_measured_curve(
            p,
            x_column=wavelength_column,
            y_column=qe_column,
            delimiter=delimiter,
            x_unit=wl_unit,
        )
    except RadiantError as exc:
        raise QeCsvParseError(
            f"could not parse the underlying CSV: {exc}",
            path=p,
        ) from exc

    wl_um = raw.x / 1000.0 if wl_unit == "nm" else raw.x.copy()
    qe = raw.y / 100.0 if q_unit == "percent" else raw.y.copy()

    return QeCurve(
        wavelength_um=wl_um,
        qe=qe,
        source_file=str(p),
        n_points=int(raw.n_points),
    )
