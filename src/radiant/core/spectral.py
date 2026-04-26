"""Spectral data types and store.

Wavelength-dependent quantities (QE, atmospheric transmittance, filter
transmission, emissivity, etc.) live here, on a single common wavelength
grid. Per RADIANT_Conventions.md:
  - Primary spectral variable: wavelength in µm
  - Array ordering: ascending wavelength

Classes
-------
SpectralGrid
    Immutable value object representing a wavelength axis in µm.
SpectralData
    A wavelength-dependent quantity with provenance, arithmetic, and I/O.
SpectralDataStore
    Holds multiple SpectralData objects interpolated to a common grid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import matplotlib.axes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SpectralGrid
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpectralGrid:
    """An immutable wavelength axis in µm, strictly ascending.

    This is the single source of identity for a spectral axis.
    SpectralData objects that share the same SpectralGrid instance
    can perform arithmetic without interpolation.

    Parameters
    ----------
    wavelengths_um:
        1-D array of wavelengths in µm, strictly ascending, at least 2 points,
        all non-negative.
    """

    wavelengths_um: np.ndarray  # shape (N,), dtype float64, ascending

    def __post_init__(self) -> None:
        # frozen=True means we must use object.__setattr__ to coerce
        wl = np.asarray(self.wavelengths_um, dtype=np.float64)
        object.__setattr__(self, "wavelengths_um", wl)

        if wl.ndim != 1:
            raise ValueError("SpectralGrid: wavelengths_um must be 1-D")
        if len(wl) < 2:
            raise ValueError(
                f"SpectralGrid: wavelengths_um must have at least 2 points, got {len(wl)}"
            )
        if np.any(wl < 0.0):
            raise ValueError(
                "SpectralGrid: wavelengths_um must be non-negative (all values ≥ 0 µm)"
            )
        if not np.all(np.diff(wl) > 0):
            raise ValueError("SpectralGrid: wavelengths_um must be strictly ascending")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def n_points(self) -> int:
        """Number of wavelength samples."""
        return int(self.wavelengths_um.shape[0])

    @property
    def lam_min(self) -> float:
        """Minimum wavelength in µm."""
        return float(self.wavelengths_um[0])

    @property
    def lam_max(self) -> float:
        """Maximum wavelength in µm."""
        return float(self.wavelengths_um[-1])

    @property
    def span(self) -> float:
        """Spectral span (lam_max - lam_min) in µm."""
        return float(self.wavelengths_um[-1] - self.wavelengths_um[0])

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def uniform(cls, lam_min: float, lam_max: float, n_points: int) -> SpectralGrid:
        """Construct a uniformly-spaced grid from lam_min to lam_max.

        Parameters
        ----------
        lam_min:
            Start wavelength in µm (inclusive).
        lam_max:
            End wavelength in µm (inclusive).
        n_points:
            Number of grid points (≥ 2).

        Returns
        -------
        SpectralGrid
        """
        if n_points < 2:
            raise ValueError(f"SpectralGrid.uniform: n_points must be ≥ 2, got {n_points}")
        if lam_min >= lam_max:
            raise ValueError(
                f"SpectralGrid.uniform: lam_min ({lam_min}) must be < lam_max ({lam_max})"
            )
        return cls(wavelengths_um=np.linspace(lam_min, lam_max, n_points))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {"wavelengths_um": self.wavelengths_um.tolist()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpectralGrid:
        """Deserialize from a dict produced by to_dict()."""
        return cls(wavelengths_um=np.array(d["wavelengths_um"], dtype=np.float64))

    # ------------------------------------------------------------------
    # Equality / hashing
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Two grids are equal iff their wavelength arrays are element-wise identical."""
        if not isinstance(other, SpectralGrid):
            return NotImplemented
        return bool(np.array_equal(self.wavelengths_um, other.wavelengths_um))

    def __hash__(self) -> int:
        return hash(self.wavelengths_um.tobytes())


# ---------------------------------------------------------------------------
# SpectralData
# ---------------------------------------------------------------------------


@dataclass
class SpectralData:
    """A wavelength-dependent quantity with provenance, arithmetic, and I/O.

    Parameters
    ----------
    name:
        Human-readable identifier.
    wavelength_um:
        1-D array of wavelengths in µm, strictly ascending.
    values:
        1-D array of values at each wavelength sample.
    unit:
        Physical unit of ``values`` (string, e.g. ``"W/m²/sr/µm"``).
    source:
        Provenance string (e.g. ``"Planck function"``).
    source_parameters:
        Optional dict of parameters used to generate this data.

    Notes
    -----
    Arithmetic operators (``+``, ``-``, ``*``, ``/``) require identical
    wavelength grids (element-wise). Use :meth:`resample` first if needed.

    Units flow for :meth:`integrate`:
        - values [W/m²/sr/µm] × wavelength_um [µm] → [W/m²/sr] (spectral radiance
          integrated over bandpass).
    """

    name: str
    wavelength_um: np.ndarray
    values: np.ndarray
    unit: str
    source: str
    source_parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.wavelength_um = np.asarray(self.wavelength_um, dtype=np.float64)
        self.values = np.asarray(self.values, dtype=np.float64)

        if self.wavelength_um.ndim != 1:
            raise ValueError(f"{self.name}: wavelength_um must be 1-D")
        if self.values.ndim != 1:
            raise ValueError(f"{self.name}: values must be 1-D")
        if len(self.wavelength_um) != len(self.values):
            raise ValueError(
                f"{self.name}: wavelength_um and values length mismatch "
                f"({len(self.wavelength_um)} vs {len(self.values)})"
            )
        if not np.all(np.diff(self.wavelength_um) > 0):
            raise ValueError(f"{self.name}: wavelength_um must be strictly ascending")

    # ------------------------------------------------------------------
    # Grid property
    # ------------------------------------------------------------------

    @property
    def grid(self) -> SpectralGrid:
        """Return the wavelength axis as a SpectralGrid."""
        return SpectralGrid(wavelengths_um=self.wavelength_um)

    # ------------------------------------------------------------------
    # Numerical operations
    # ------------------------------------------------------------------

    def integrate(self) -> float:
        """Integrate values over wavelength using the trapezoidal rule.

        Returns
        -------
        float
            ∫ values dλ  [unit × µm]

        For spectral radiance [W/m²/sr/µm], the result is [W/m²/sr].
        """
        return float(np.trapezoid(self.values, self.wavelength_um))

    def resample(self, target_grid: SpectralGrid) -> SpectralData:
        """Resample to a new wavelength grid using linear interpolation.

        Parameters
        ----------
        target_grid:
            The destination wavelength grid in µm.

        Returns
        -------
        SpectralData
            New object on ``target_grid``.

        Raises
        ------
        ValueError
            If ``target_grid`` extends outside the range of this object's
            wavelengths.  Extrapolation is never performed silently.
        """
        t_min = target_grid.lam_min
        t_max = target_grid.lam_max
        s_min = float(self.wavelength_um[0])
        s_max = float(self.wavelength_um[-1])

        if t_min < s_min or t_max > s_max:
            raise ValueError(
                f"{self.name}: cannot resample — target grid [{t_min}, {t_max}] µm "
                f"extends outside source range [{s_min}, {s_max}] µm. "
                "Trim target_grid or extend the source data first."
            )

        new_values = np.interp(
            target_grid.wavelengths_um,
            self.wavelength_um,
            self.values,
        )
        return SpectralData(
            name=self.name,
            wavelength_um=target_grid.wavelengths_um.copy(),
            values=new_values,
            unit=self.unit,
            source=self.source,
            source_parameters=dict(self.source_parameters),
        )

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def _check_compatible(self, other: SpectralData) -> None:
        if not np.array_equal(self.wavelength_um, other.wavelength_um):
            raise ValueError(
                f"Arithmetic requires identical wavelength grids. "
                f"'{self.name}' and '{other.name}' have different grids. "
                "Use SpectralData.resample() to align them first."
            )

    def __add__(self, other: SpectralData | float | int) -> SpectralData:
        if isinstance(other, SpectralData):
            self._check_compatible(other)
            return SpectralData(
                name=f"{self.name} + {other.name}",
                wavelength_um=self.wavelength_um.copy(),
                values=self.values + other.values,
                unit=self.unit,
                source="arithmetic",
            )
        return SpectralData(
            name=f"{self.name} + {other}",
            wavelength_um=self.wavelength_um.copy(),
            values=self.values + float(other),
            unit=self.unit,
            source="arithmetic",
        )

    def __sub__(self, other: SpectralData | float | int) -> SpectralData:
        if isinstance(other, SpectralData):
            self._check_compatible(other)
            return SpectralData(
                name=f"{self.name} - {other.name}",
                wavelength_um=self.wavelength_um.copy(),
                values=self.values - other.values,
                unit=self.unit,
                source="arithmetic",
            )
        return SpectralData(
            name=f"{self.name} - {other}",
            wavelength_um=self.wavelength_um.copy(),
            values=self.values - float(other),
            unit=self.unit,
            source="arithmetic",
        )

    def __mul__(self, other: SpectralData | float | int) -> SpectralData:
        if isinstance(other, SpectralData):
            self._check_compatible(other)
            return SpectralData(
                name=f"{self.name} * {other.name}",
                wavelength_um=self.wavelength_um.copy(),
                values=self.values * other.values,
                unit=self.unit,
                source="arithmetic",
            )
        return SpectralData(
            name=f"{self.name} * {other}",
            wavelength_um=self.wavelength_um.copy(),
            values=self.values * float(other),
            unit=self.unit,
            source="arithmetic",
        )

    def __rmul__(self, other: float | int) -> SpectralData:
        return self.__mul__(other)

    def __truediv__(self, other: SpectralData | float | int) -> SpectralData:
        if isinstance(other, SpectralData):
            self._check_compatible(other)
            return SpectralData(
                name=f"{self.name} / {other.name}",
                wavelength_um=self.wavelength_um.copy(),
                values=self.values / other.values,
                unit=self.unit,
                source="arithmetic",
            )
        return SpectralData(
            name=f"{self.name} / {other}",
            wavelength_um=self.wavelength_um.copy(),
            values=self.values / float(other),
            unit=self.unit,
            source="arithmetic",
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "wavelength_um": self.wavelength_um.tolist(),
            "values": self.values.tolist(),
            "unit": self.unit,
            "source": self.source,
            "source_parameters": self.source_parameters,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpectralData:
        """Deserialize from a dict produced by to_dict()."""
        return cls(
            name=d["name"],
            wavelength_um=np.array(d["wavelength_um"], dtype=np.float64),
            values=np.array(d["values"], dtype=np.float64),
            unit=d["unit"],
            source=d["source"],
            source_parameters=dict(d.get("source_parameters", {})),
        )

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def plot(self, ax: matplotlib.axes.Axes | None = None) -> matplotlib.axes.Axes:
        """Plot values vs. wavelength.

        Parameters
        ----------
        ax:
            Existing matplotlib Axes to plot into, or ``None`` to create one.

        Returns
        -------
        matplotlib.axes.Axes
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise ImportError(
                "matplotlib is required for SpectralData.plot(). "
                "Install it with: pip install matplotlib"
            ) from exc

        if ax is None:
            _, ax = plt.subplots()
        ax.plot(self.wavelength_um, self.values, label=self.name)
        ax.set_xlabel("Wavelength (µm)")
        ax.set_ylabel(self.unit)
        ax.set_title(self.name)
        return ax


# ---------------------------------------------------------------------------
# SpectralDataStore
# ---------------------------------------------------------------------------


class SpectralDataStore:
    """Holds all spectral arrays interpolated to a common wavelength grid.

    Generators (filters, QE models, MODTRAN readers) produce SpectralData
    objects. The store interpolates them onto its grid on add().

    Parameters
    ----------
    grid_um:
        Common wavelength grid in µm (1-D, strictly ascending, ≥ 2 points).
        May be a numpy array or a SpectralGrid.
    """

    def __init__(self, grid_um: np.ndarray | SpectralGrid) -> None:
        if isinstance(grid_um, SpectralGrid):
            raw = grid_um.wavelengths_um
        else:
            raw = np.asarray(grid_um, dtype=np.float64)

        if raw.ndim != 1 or len(raw) < 2:
            raise ValueError("Grid must be a 1-D array with at least 2 points")
        if not np.all(np.diff(raw) > 0):
            raise ValueError("Grid must be strictly ascending in wavelength")
        self._grid: np.ndarray = raw.astype(np.float64)
        self._data: dict[str, np.ndarray] = {}
        self._metadata: dict[str, SpectralData] = {}

    @property
    def grid_um(self) -> np.ndarray:
        """Common wavelength grid in µm."""
        return self._grid

    def add(self, data: SpectralData) -> None:
        """Interpolate ``data`` onto the common grid and store it.

        Uses linear interpolation. Out-of-range values are extrapolated to the
        nearest endpoint (constant extrapolation) and a debug message is logged.

        Parameters
        ----------
        data:
            The spectral data to add.

        Raises
        ------
        ValueError
            If a SpectralData with this name has already been added.
        """
        if data.name in self._data:
            raise ValueError(f"SpectralData '{data.name}' already in store")

        # Check for extrapolation and warn
        if data.wavelength_um[0] > self._grid[0] or data.wavelength_um[-1] < self._grid[-1]:
            logger.debug(
                "SpectralDataStore.add('%s'): source range [%.4f, %.4f] µm does not "
                "cover store grid [%.4f, %.4f] µm — constant extrapolation applied.",
                data.name,
                data.wavelength_um[0],
                data.wavelength_um[-1],
                self._grid[0],
                self._grid[-1],
            )

        # Linear interpolation; clip to endpoints (constant extrapolation)
        interp = np.interp(
            self._grid,
            data.wavelength_um,
            data.values,
            left=data.values[0],
            right=data.values[-1],
        )
        self._data[data.name] = interp
        self._metadata[data.name] = data

    def get(self, name: str) -> np.ndarray:
        """Return the values of ``name`` on the common grid.

        Raises
        ------
        KeyError
            If ``name`` is not in the store.
        """
        if name not in self._data:
            raise KeyError(f"SpectralData '{name}' not in store")
        return self._data[name]

    def get_metadata(self, name: str) -> SpectralData:
        """Return the original SpectralData metadata for ``name``."""
        if name not in self._metadata:
            raise KeyError(f"SpectralData '{name}' not in store")
        return self._metadata[name]

    def has(self, name: str) -> bool:
        """Return True if ``name`` is present in the store."""
        return name in self._data

    def names(self) -> list[str]:
        """Return a list of all stored dataset names."""
        return list(self._data.keys())
