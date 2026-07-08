"""ASTER spectral-library import — load a material spectrum from the
JPL/NASA ASTER library text format.

Provides :func:`load_aster_spectrum` to read one ASTER library file
(the ``Name:``/``Type:``/… metadata header followed by two whitespace-
separated columns, wavelength [µm] and reflectance, usually listed in
DESCENDING wavelength order) into an :class:`AsterSpectrum` in RADIANT
conventions: ascending wavelength [µm], reflectance as a fraction.
Found needed by scenario 1.3 (forest background emissivity for the
dual-band wildfire trade).

Emissivity for opaque materials follows Kirchhoff's law for scene
targets: ε(λ) = 1 − ρ(λ). This is the legitimate independent-emissivity
case (scene material property); Rule 5's derived-only constraint binds
optical elements, not targets.

The Y-unit is taken from the ``Y Units:`` header line (``percent`` vs
``fraction``); files without a recognizable unit line raise rather than
guess (Rule 17).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError

__all__ = ["AsterLibraryError", "AsterSpectrum", "load_aster_spectrum"]


class AsterLibraryError(RadiantError):
    """Raised when an ASTER library file cannot be parsed or queried."""

    def __init__(self, detail: str, *, path: str | Path | None = None) -> None:
        self.path = path
        self.detail = detail
        loc = f" in {path}" if path else ""
        super().__init__(f"AsterLibraryError{loc}: {detail}")


@dataclass(frozen=True)
class AsterSpectrum:
    """One ASTER library spectrum in RADIANT conventions.

    Attributes
    ----------
    name:
        The header ``Name:`` field (material description).
    wavelength_um:
        Ascending wavelength grid [µm].
    reflectance:
        Directional-hemispherical reflectance [fraction, 0–1].
    y_units_percent:
        True when the source file recorded reflectance in percent
        (provenance of the ÷100 conversion).
    source_file:
        Path the spectrum was loaded from.
    """

    name: str
    wavelength_um: npt.NDArray[np.float64]
    reflectance: npt.NDArray[np.float64]
    y_units_percent: bool
    source_file: str

    def __post_init__(self) -> None:
        wl = np.asarray(self.wavelength_um, dtype=np.float64)
        rho = np.asarray(self.reflectance, dtype=np.float64)
        object.__setattr__(self, "wavelength_um", wl)
        object.__setattr__(self, "reflectance", rho)
        if wl.shape != rho.shape or wl.ndim != 1 or wl.shape[0] == 0:
            raise AsterLibraryError(
                f"wavelength/reflectance must be equal-length non-empty 1-D "
                f"arrays; got shapes {wl.shape} and {rho.shape}.",
                path=self.source_file,
            )
        if np.any(wl <= 0.0):
            raise AsterLibraryError(
                f"wavelengths must be positive µm; min = {wl.min()}.",
                path=self.source_file,
            )
        if np.any((rho < 0.0) | (rho > 1.0)):
            raise AsterLibraryError(
                f"reflectance out of [0, 1] after conversion (range "
                f"{rho.min():.4g}–{rho.max():.4g}). Check the Y Units header "
                "(percent vs fraction) and the data rows.",
                path=self.source_file,
            )

    def emissivity(self) -> npt.NDArray[np.float64]:
        """Spectral emissivity ε(λ) = 1 − ρ(λ) (opaque material)."""
        return np.asarray(1.0 - self.reflectance, dtype=np.float64)

    def band_averaged_emissivity(self, lam_min_um: float, lam_max_um: float) -> float:
        """Mean ε over [lam_min_um, lam_max_um] (trapezoidal)."""
        lo = float(self.wavelength_um[0])
        hi = float(self.wavelength_um[-1])
        if lam_min_um < lo or lam_max_um > hi:
            raise AsterLibraryError(
                f"band [{lam_min_um}, {lam_max_um}] µm lies (partly) outside "
                f"the measured spectrum [{lo}, {hi}] µm — extrapolating a "
                "material spectrum is unsafe.",
                path=self.source_file,
            )
        if not lam_min_um < lam_max_um:
            raise AsterLibraryError(
                f"need lam_min < lam_max, got ({lam_min_um}, {lam_max_um}) µm.",
                path=self.source_file,
            )
        grid = np.linspace(lam_min_um, lam_max_um, 501)
        eps = np.interp(grid, self.wavelength_um, self.emissivity())
        return float(np.trapezoid(eps, grid) / (lam_max_um - lam_min_um))


def load_aster_spectrum(path: str | Path) -> AsterSpectrum:
    """Parse one ASTER spectral-library text file.

    Parameters
    ----------
    path:
        ASTER library file: ``Key: value`` metadata header lines followed
        by two whitespace-separated numeric columns (wavelength [µm],
        reflectance). Descending-wavelength files (the library's native
        order) are sorted ascending on load.

    Returns
    -------
    AsterSpectrum
        Canonical ascending-µm spectrum with fractional reflectance.

    Raises
    ------
    AsterLibraryError
        Missing file, unrecognizable Y units, malformed data rows, no
        data rows, or out-of-range reflectance.
    """
    p = Path(path)
    if not p.is_file():
        raise AsterLibraryError(
            f"file {p} does not exist or is not a file. Check the path to "
            "the ASTER library spectrum (speclib.jpl.nasa.gov text format).",
            path=p,
        )

    name = ""
    y_units: str | None = None
    wl: list[float] = []
    rho: list[float] = []

    for line_no, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        # Numeric two-column data row?
        if len(parts) == 2:
            try:
                wl.append(float(parts[0]))
                rho.append(float(parts[1]))
                continue
            except ValueError:
                pass  # falls through to header handling
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            if key == "name":
                name = value.strip()
            elif key == "y units":
                y_units = value.strip().lower()
            continue
        if wl:
            # A non-parsable line in the middle of the data block.
            raise AsterLibraryError(
                f"line {line_no}: could not parse data row {raw!r} as two numeric columns.",
                path=p,
            )
        # Non-numeric, non-key line before data (free-text header) — skip.

    if not wl:
        raise AsterLibraryError("file contains no data rows (two numeric columns).", path=p)
    if y_units is None or ("percent" not in y_units and "fraction" not in y_units):
        raise AsterLibraryError(
            f"could not determine the reflectance unit from the 'Y Units:' "
            f"header (got {y_units!r}). Expected 'percent' or 'fraction'.",
            path=p,
        )

    percent = "percent" in y_units
    wl_arr = np.asarray(wl, dtype=np.float64)
    rho_arr = np.asarray(rho, dtype=np.float64)
    if percent:
        rho_arr = rho_arr / 100.0
    order = np.argsort(wl_arr)
    return AsterSpectrum(
        name=name,
        wavelength_um=wl_arr[order],
        reflectance=rho_arr[order],
        y_units_percent=percent,
        source_file=str(p),
    )
