"""Vendor dark-current import — load J_dark(T) from a detector-vendor CSV.

Provides :func:`load_dark_current_csv` to read a two-column
temperature-vs-current-density vendor export (columns like
``T_K, Jdark_A_cm2``) into an immutable :class:`DarkCurrentCurve`, and
convert to RADIANT's canonical dark rate [e⁻/s/pixel] for a given pixel
pitch. Found needed by scenario 2.1 (detector datasheet import).

Conversion (once, at this file-reader boundary — Rule 2)::

    rate [e⁻/s] = J [A/cm²] · (pitch · 100)² [cm²] / q

Interpolation is Arrhenius-faithful: ``ln(J)`` is interpolated linearly
in ``1/T``, which is exact for ``J ∝ exp(−E_a / k_B T)`` between nodes
and a far better model of diode dark current than linear-in-T
interpolation. Queries outside the measured temperature range raise —
extrapolating an exponential silently is how dark-current budgets go
wrong (Rule 17).

CSV mechanics are delegated to
:func:`radiant.io.measurement.load_measured_curve`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.constants import q
from radiant.core.exceptions import RadiantError
from radiant.io.measurement import load_measured_curve

__all__ = [
    "DarkCurrentCsvParseError",
    "DarkCurrentCurve",
    "load_dark_current_csv",
]


class DarkCurrentCsvParseError(RadiantError):
    """Raised when a vendor J_dark(T) CSV cannot be parsed or queried."""

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"DarkCurrentCsvParseError{loc}: {detail}")


@dataclass(frozen=True)
class DarkCurrentCurve:
    """An immutable measured J_dark(T) curve.

    Attributes
    ----------
    temperature_K:
        Detector temperature grid [K], float64, strictly ascending,
        positive.
    j_dark_A_cm2:
        Dark current density [A/cm²], same length, strictly positive
        (required for the log-space Arrhenius interpolation).
    source_file:
        Path the curve was loaded from.
    n_points:
        Number of samples.
    """

    temperature_K: npt.NDArray[np.float64]
    j_dark_A_cm2: npt.NDArray[np.float64]
    source_file: str
    n_points: int

    def __post_init__(self) -> None:
        t = np.asarray(self.temperature_K, dtype=np.float64)
        j = np.asarray(self.j_dark_A_cm2, dtype=np.float64)
        object.__setattr__(self, "temperature_K", t)
        object.__setattr__(self, "j_dark_A_cm2", j)
        if t.shape != j.shape or t.ndim != 1:
            raise DarkCurrentCsvParseError(
                f"temperature and J_dark must be equal-length 1-D arrays; "
                f"got shapes {t.shape} and {j.shape}.",
                path=self.source_file,
            )
        if t.shape[0] < 2:
            raise DarkCurrentCsvParseError(
                "curve needs at least two (T, J) samples for interpolation.",
                path=self.source_file,
            )
        if np.any(t <= 0.0):
            raise DarkCurrentCsvParseError(
                f"temperatures must be positive Kelvin; min = {t.min()} K.",
                path=self.source_file,
            )
        if np.any(j <= 0.0):
            raise DarkCurrentCsvParseError(
                f"J_dark values must be positive (min = {j.min()} A/cm²) — "
                "zero or negative current density cannot be interpolated in "
                "log space. Remove or repair the offending rows.",
                path=self.source_file,
            )

    # -- Queries ------------------------------------------------------------

    def j_dark_at(self, temperature_K: float) -> float:
        """Interpolate J_dark [A/cm²] at *temperature_K* (Arrhenius log-space)."""
        lo = float(self.temperature_K[0])
        hi = float(self.temperature_K[-1])
        if not lo <= temperature_K <= hi:
            raise DarkCurrentCsvParseError(
                f"T = {temperature_K} K is outside the measured range "
                f"[{lo}, {hi}] K. Extrapolating an exponential dark-current "
                "curve is unsafe — request vendor data covering the "
                "operating temperature.",
                path=self.source_file,
            )
        # ln(J) linear in 1/T; np.interp needs ascending x, and 1/T
        # descends as T ascends, so flip both arrays.
        inv_t = 1.0 / self.temperature_K[::-1]
        ln_j = np.log(self.j_dark_A_cm2[::-1])
        return float(np.exp(np.interp(1.0 / temperature_K, inv_t, ln_j)))

    def dark_rate_e_per_s(self, temperature_K: float, *, pixel_pitch_m: float) -> float:
        """Dark rate [e⁻/s/pixel] at *temperature_K* for a square pixel.

        ``rate = J(T) [A/cm²] · (pitch·100)² [cm²] / q``.
        """
        if pixel_pitch_m <= 0.0:
            raise DarkCurrentCsvParseError(
                f"pixel_pitch_m must be positive, got {pixel_pitch_m}.",
                path=self.source_file,
            )
        area_cm2 = (pixel_pitch_m * 100.0) ** 2
        return self.j_dark_at(temperature_K) * area_cm2 / q

    def temperature_at_rate(self, rate_e_per_s: float, *, pixel_pitch_m: float) -> float:
        """Inverse query: temperature [K] where the dark rate equals *rate_e_per_s*.

        Exact inverse of :meth:`dark_rate_e_per_s` under the same
        Arrhenius log-space model. Raises when the requested rate lies
        outside the measured curve.
        """
        if pixel_pitch_m <= 0.0:
            raise DarkCurrentCsvParseError(
                f"pixel_pitch_m must be positive, got {pixel_pitch_m}.",
                path=self.source_file,
            )
        area_cm2 = (pixel_pitch_m * 100.0) ** 2
        j_target = rate_e_per_s * q / area_cm2
        j_lo = float(self.j_dark_A_cm2.min())
        j_hi = float(self.j_dark_A_cm2.max())
        if not j_lo <= j_target <= j_hi:
            raise DarkCurrentCsvParseError(
                f"rate {rate_e_per_s:.4g} e⁻/s (J = {j_target:.4g} A/cm²) is "
                f"outside the measured J_dark range [{j_lo:.4g}, {j_hi:.4g}] "
                "A/cm² — no temperature on the curve produces it.",
                path=self.source_file,
            )
        # ln(J) is monotonically increasing in T for diode dark current;
        # interpolate 1/T against ln(J).
        ln_j = np.log(self.j_dark_A_cm2)
        inv_t = 1.0 / self.temperature_K
        if not np.all(np.diff(ln_j) > 0.0):
            raise DarkCurrentCsvParseError(
                "J_dark(T) is not strictly increasing with temperature — "
                "the inverse temperature query is ambiguous. Check the "
                "vendor data for out-of-order or duplicated rows.",
                path=self.source_file,
            )
        inv = np.interp(np.log(j_target), ln_j, inv_t)
        return float(1.0 / inv)

    # -- Serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain types (round-trips via :meth:`from_dict`)."""
        return {
            "temperature_K": self.temperature_K.tolist(),
            "j_dark_A_cm2": self.j_dark_A_cm2.tolist(),
            "source_file": self.source_file,
            "n_points": self.n_points,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DarkCurrentCurve:
        """Rebuild from :meth:`to_dict` output."""
        return cls(
            temperature_K=np.asarray(d["temperature_K"], dtype=np.float64),
            j_dark_A_cm2=np.asarray(d["j_dark_A_cm2"], dtype=np.float64),
            source_file=str(d["source_file"]),
            n_points=int(d["n_points"]),
        )


def load_dark_current_csv(
    path: str | Path,
    *,
    temperature_column: int = 0,
    jdark_column: int = 1,
    delimiter: str = ",",
) -> DarkCurrentCurve:
    """Load a vendor J_dark(T) CSV (``T_K, Jdark_A_cm2`` columns).

    Parameters
    ----------
    path:
        CSV file: temperature [K] and dark current density [A/cm²]
        columns, optional header and ``#`` comments.
    temperature_column, jdark_column:
        Zero-based column indices.
    delimiter:
        Field delimiter (default ``","``).

    Returns
    -------
    DarkCurrentCurve
        Validated curve, strictly ascending in temperature.

    Raises
    ------
    DarkCurrentCsvParseError
        Missing/invalid file or unphysical (non-positive) values.
    """
    p = Path(path)
    if not p.is_file():
        raise DarkCurrentCsvParseError(
            f"file {p} does not exist or is not a file. Check the path; "
            "vendor dark-current data is the CSV export of the J_dark(T) "
            "datasheet plot.",
            path=p,
        )
    try:
        raw = load_measured_curve(
            p,
            x_column=temperature_column,
            y_column=jdark_column,
            delimiter=delimiter,
            x_unit="K",
        )
    except RadiantError as exc:
        raise DarkCurrentCsvParseError(
            f"could not parse the underlying CSV: {exc}",
            path=p,
        ) from exc

    return DarkCurrentCurve(
        temperature_K=raw.x.copy(),
        j_dark_A_cm2=raw.y.copy(),
        source_file=str(p),
        n_points=int(raw.n_points),
    )
