"""Tabulated atmosphere model — user-provided spectral data from files.

Loads pre-computed transmittance, path radiance, and (optionally) downwelling
emission from CSV or NPZ files.  The data are geometry-agnostic: the loaded
values are returned verbatim for any query geometry, resampled to the
requested wavelength grid via ``SpectralData.resample()``.

Per ``docs/RADIANT_Atmosphere.md`` section 3.2 the tabulated model does NOT
rescale with geometry.  Users who need geometry-dependent interpolation
between multiple tabulated runs should use
:class:`~radiant.atmosphere.interpolated.InterpolatedAtmosphere`.

File formats
------------
**CSV** — two columns, first is ``wavelength_um``, second is the quantity
value.  A header row is auto-detected: if the first field cannot be parsed
as a float, it is treated as a header and skipped.

**NPZ** — numpy compressed archive with keys ``wavelength_um``,
``transmittance``, ``path_radiance``, and optionally ``atm_emission_down``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData, SpectralGrid

logger = logging.getLogger(__name__)


def _load_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a two-column CSV file as (wavelength_um, values).

    Auto-detects and skips a header row if present.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file has fewer than two usable rows or cannot be parsed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Tabulated atmosphere CSV not found: {path}. "
            "Check the file path and ensure the file exists."
        )

    lines = path.read_text().strip().splitlines()
    if not lines:
        raise ValueError(
            f"Tabulated atmosphere CSV is empty: {path}. "
            "Provide a file with at least two rows of (wavelength_um, value)."
        )

    # Detect header: try parsing the first row as floats.
    start = 0
    try:
        float(lines[0].split(",")[0].strip())
    except ValueError:
        start = 1

    rows: list[tuple[float, float]] = []
    for i, line in enumerate(lines[start:], start=start):
        parts = line.split(",")
        if len(parts) < 2:
            raise ValueError(
                f"Tabulated atmosphere CSV line {i + 1} in {path} has "
                f"fewer than 2 columns: {line!r}. Expected (wavelength_um, value)."
            )
        try:
            wl = float(parts[0].strip())
            val = float(parts[1].strip())
        except ValueError as err:
            raise ValueError(
                f"Tabulated atmosphere CSV line {i + 1} in {path} cannot be "
                f"parsed as floats: {line!r}."
            ) from err
        rows.append((wl, val))

    if len(rows) < 2:
        raise ValueError(
            f"Tabulated atmosphere CSV {path} has fewer than 2 data rows. "
            "At least 2 wavelength samples are required."
        )

    arr = np.array(rows, dtype=np.float64)
    return arr[:, 0], arr[:, 1]


def _validate_spectral_array(
    wavelength_um: np.ndarray,
    values: np.ndarray,
    label: str,
    source_path: str,
) -> None:
    """Validate a loaded spectral array before constructing SpectralData."""
    if wavelength_um.ndim != 1:
        raise ValueError(
            f"Tabulated {label} from {source_path}: wavelength_um must be 1-D, "
            f"got shape {wavelength_um.shape}."
        )
    if values.ndim != 1:
        raise ValueError(
            f"Tabulated {label} from {source_path}: values must be 1-D, "
            f"got shape {values.shape}."
        )
    if len(wavelength_um) != len(values):
        raise ValueError(
            f"Tabulated {label} from {source_path}: wavelength_um length "
            f"({len(wavelength_um)}) != values length ({len(values)})."
        )
    if len(wavelength_um) < 2:
        raise ValueError(
            f"Tabulated {label} from {source_path}: at least 2 samples "
            f"required, got {len(wavelength_um)}."
        )
    if not np.all(np.diff(wavelength_um) > 0):
        raise ValueError(
            f"Tabulated {label} from {source_path}: wavelength_um must be "
            "strictly ascending."
        )
    if np.any(wavelength_um <= 0.0):
        raise ValueError(
            f"Tabulated {label} from {source_path}: wavelength_um must be "
            "strictly positive."
        )


@dataclass(frozen=True)
class TabulatedAtmosphere:
    """Atmosphere model loaded from user-provided spectral files.

    The three spectral arrays (transmittance, path_radiance,
    atm_emission_down) are loaded at construction time and served
    verbatim — resampled to the query wavelength grid — for every call
    to :meth:`build_state`.

    Parameters
    ----------
    transmittance_data:
        Spectral transmittance, dimensionless [0, 1].
    path_radiance_data:
        Upwelling path radiance [W/m^2/sr/um].
    atm_emission_down_data:
        Downwelling atmospheric emission [W/m^2/sr/um].  May be all zeros
        if unavailable.
    name:
        Human-readable label for provenance.
    source_path:
        Path or description of where the data came from.
    """

    transmittance_data: SpectralData
    path_radiance_data: SpectralData
    atm_emission_down_data: SpectralData
    name: str = "tabulated_atmosphere"
    source_path: str = ""
    _tag: str = field(default="tabulated", init=False, repr=False)

    def __post_init__(self) -> None:
        tau = self.transmittance_data.values
        if np.any(tau < 0.0) or np.any(tau > 1.0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': transmittance values "
                f"out of [0, 1] (min={float(tau.min()):g}, max={float(tau.max()):g}). "
                "Transmittance is a probability and must be bounded."
            )
        if np.any(self.path_radiance_data.values < 0.0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': path_radiance has "
                "negative values. Path radiance must be non-negative."
            )
        if np.any(self.atm_emission_down_data.values < 0.0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': atm_emission_down has "
                "negative values. Downwelling emission must be non-negative."
            )

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_csv(
        cls,
        tau_file: str | Path,
        lpath_file: str | Path,
        ldown_file: str | Path | None = None,
        name: str = "tabulated_atmosphere",
    ) -> TabulatedAtmosphere:
        """Load from CSV files (two columns: wavelength_um, value).

        Parameters
        ----------
        tau_file:
            Path to transmittance CSV.
        lpath_file:
            Path to path radiance CSV.
        ldown_file:
            Path to downwelling emission CSV, or ``None`` for zeros.
        name:
            Human-readable label.
        """
        tau_wl, tau_vals = _load_csv(Path(tau_file))
        _validate_spectral_array(tau_wl, tau_vals, "transmittance", str(tau_file))

        lp_wl, lp_vals = _load_csv(Path(lpath_file))
        _validate_spectral_array(lp_wl, lp_vals, "path_radiance", str(lpath_file))

        provenance: dict[str, Any] = {
            "model": "tabulated",
            "tau_file": str(tau_file),
            "lpath_file": str(lpath_file),
        }

        transmittance = SpectralData(
            name="atm.transmittance.tabulated",
            wavelength_um=tau_wl,
            values=tau_vals,
            unit="",
            source=f"Tabulated CSV: {tau_file}",
            source_parameters=provenance,
        )
        path_radiance = SpectralData(
            name="atm.path_radiance.tabulated",
            wavelength_um=lp_wl,
            values=lp_vals,
            unit="W/m²/sr/µm",
            source=f"Tabulated CSV: {lpath_file}",
            source_parameters=provenance,
        )

        if ldown_file is not None:
            ld_wl, ld_vals = _load_csv(Path(ldown_file))
            _validate_spectral_array(ld_wl, ld_vals, "atm_emission_down", str(ldown_file))
            provenance["ldown_file"] = str(ldown_file)
            atm_emission_down = SpectralData(
                name="atm.emission_down.tabulated",
                wavelength_um=ld_wl,
                values=ld_vals,
                unit="W/m²/sr/µm",
                source=f"Tabulated CSV: {ldown_file}",
                source_parameters=provenance,
            )
        else:
            logger.warning(
                "TabulatedAtmosphere '%s': no downwelling emission file provided. "
                "Defaulting to zeros on the transmittance wavelength grid.",
                name,
            )
            atm_emission_down = SpectralData(
                name="atm.emission_down.tabulated",
                wavelength_um=tau_wl.copy(),
                values=np.zeros_like(tau_wl),
                unit="W/m²/sr/µm",
                source="TabulatedAtmosphere default (zeros)",
                source_parameters=provenance,
            )

        return cls(
            transmittance_data=transmittance,
            path_radiance_data=path_radiance,
            atm_emission_down_data=atm_emission_down,
            name=name,
            source_path=str(tau_file),
        )

    @classmethod
    def from_npz(
        cls,
        npz_file: str | Path,
        name: str = "tabulated_atmosphere",
    ) -> TabulatedAtmosphere:
        """Load from a NumPy NPZ archive.

        Required keys: ``wavelength_um``, ``transmittance``,
        ``path_radiance``.  Optional key: ``atm_emission_down``.

        Parameters
        ----------
        npz_file:
            Path to the ``.npz`` file.
        name:
            Human-readable label.
        """
        npz_path = Path(npz_file)
        if not npz_path.exists():
            raise FileNotFoundError(
                f"Tabulated atmosphere NPZ not found: {npz_path}. "
                "Check the file path and ensure the file exists."
            )

        data = np.load(npz_path)
        required = ("wavelength_um", "transmittance", "path_radiance")
        for key in required:
            if key not in data:
                raise ValueError(
                    f"Tabulated atmosphere NPZ {npz_path} is missing required "
                    f"key '{key}'. Required keys: {required}."
                )

        wl = np.asarray(data["wavelength_um"], dtype=np.float64)
        tau_vals = np.asarray(data["transmittance"], dtype=np.float64)
        lp_vals = np.asarray(data["path_radiance"], dtype=np.float64)

        _validate_spectral_array(wl, tau_vals, "transmittance", str(npz_file))
        _validate_spectral_array(wl, lp_vals, "path_radiance", str(npz_file))

        provenance: dict[str, Any] = {
            "model": "tabulated",
            "npz_file": str(npz_file),
        }

        transmittance = SpectralData(
            name="atm.transmittance.tabulated",
            wavelength_um=wl.copy(),
            values=tau_vals,
            unit="",
            source=f"Tabulated NPZ: {npz_file}",
            source_parameters=provenance,
        )
        path_radiance = SpectralData(
            name="atm.path_radiance.tabulated",
            wavelength_um=wl.copy(),
            values=lp_vals,
            unit="W/m²/sr/µm",
            source=f"Tabulated NPZ: {npz_file}",
            source_parameters=provenance,
        )

        if "atm_emission_down" in data:
            ld_vals = np.asarray(data["atm_emission_down"], dtype=np.float64)
            _validate_spectral_array(wl, ld_vals, "atm_emission_down", str(npz_file))
            atm_emission_down = SpectralData(
                name="atm.emission_down.tabulated",
                wavelength_um=wl.copy(),
                values=ld_vals,
                unit="W/m²/sr/µm",
                source=f"Tabulated NPZ: {npz_file}",
                source_parameters=provenance,
            )
        else:
            logger.warning(
                "TabulatedAtmosphere '%s': NPZ file %s has no "
                "'atm_emission_down' key. Defaulting to zeros.",
                name,
                npz_file,
            )
            atm_emission_down = SpectralData(
                name="atm.emission_down.tabulated",
                wavelength_um=wl.copy(),
                values=np.zeros_like(wl),
                unit="W/m²/sr/µm",
                source="TabulatedAtmosphere default (zeros)",
                source_parameters=provenance,
            )

        return cls(
            transmittance_data=transmittance,
            path_radiance_data=path_radiance,
            atm_emission_down_data=atm_emission_down,
            name=name,
            source_path=str(npz_file),
        )

    # ------------------------------------------------------------------
    # Atmosphere protocol
    # ------------------------------------------------------------------

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Return the tabulated data resampled to *wavelength_um*.

        The loaded data are resampled onto the requested wavelength grid
        via linear interpolation.  Extrapolation beyond the source data
        range raises ``ValueError``.

        The *geometry* is recorded on the returned
        :class:`AtmosphericState` for downstream use but does **not**
        affect the spectral values — tabulated data are delivered as-is.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um must be "
                f"1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um needs at "
                f"least two samples, got {lam.size}."
            )
        if not np.all(np.diff(lam) > 0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um must be "
                "strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um must be "
                "strictly positive."
            )

        target_grid = SpectralGrid(wavelengths_um=lam)

        tau_resampled = self.transmittance_data.resample(target_grid)
        lpath_resampled = self.path_radiance_data.resample(target_grid)
        ldown_resampled = self.atm_emission_down_data.resample(target_grid)

        return AtmosphericState(
            transmittance=SpectralData(
                name="atm.transmittance.tabulated",
                wavelength_um=lam,
                values=tau_resampled.values,
                unit="",
                source=self.transmittance_data.source,
                source_parameters=self.transmittance_data.source_parameters,
            ),
            path_radiance=SpectralData(
                name="atm.path_radiance.tabulated",
                wavelength_um=lam,
                values=lpath_resampled.values,
                unit="W/m²/sr/µm",
                source=self.path_radiance_data.source,
                source_parameters=self.path_radiance_data.source_parameters,
            ),
            atm_emission_down=SpectralData(
                name="atm.emission_down.tabulated",
                wavelength_um=lam,
                values=ldown_resampled.values,
                unit="W/m²/sr/µm",
                source=self.atm_emission_down_data.source,
                source_parameters=self.atm_emission_down_data.source_parameters,
            ),
            geometry=geometry,
            derivation_chain=(
                f"TabulatedAtmosphere(source={self.source_path})",
                "Geometry-agnostic: values not rescaled with viewing geometry",
            ),
        )

    def evaluate(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
        params: ParameterSet,
    ) -> AtmosphericQuantities:
        """Thin adapter over the legacy τ / L_path / L_atm_down tables.

        Tabulated files pre-date the Option C two-leg split, so the new
        fields are populated as follows:

        - ``tau_sun == tau_up == tau_full_up`` = the single tabulated
          ``transmittance`` resampled to the chain grid.  The legacy
          pipeline collapsed both legs into one factor; the tabulated
          files carry the same collapse.  A UserWarning is emitted so
          the caller sees that the two-leg split has been degraded.
        - ``L_path_up == L_path_full`` = the single tabulated path
          radiance.  Surface target assumption (h_tgt == 0) still
          applies — ``h_tgt > 0`` raises :class:`NotImplementedError`.
        - ``E_TOA`` = ``toa_solar_spectral_irradiance`` on the chain grid
          (tabulated files do not carry the solar spectrum).
        - ``E_sky_scattered`` = 0 (not tabulated).
        - ``E_sky_thermal`` = ``π · L_atm_down`` — converts the tabulated
          downwelling radiance to an irradiance using the Lambertian
          hemisphere integral, consistent with how the assembly equation
          divides ``E_sky`` by π downstream.
        """
        import warnings

        if los.h_tgt > 0.0:
            raise NotImplementedError(
                f"TabulatedAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 "
                "(airborne targets) is a Stage 5 deliverable; v1 supports "
                "only surface-level tabulated runs."
            )
        _ = params  # unused; tabulated is geometry-agnostic by design.

        lam = np.asarray(wavelength_um, dtype=np.float64)
        # Reuse the standard input validation via build_state path shape
        # checks by constructing a grid directly (we do not need the
        # build_state product here).
        if lam.ndim != 1 or lam.size < 2 or not np.all(np.diff(lam) > 0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um must be "
                "a strictly ascending 1-D array of length ≥ 2."
            )
        if np.any(lam <= 0.0):
            raise ValueError(
                f"TabulatedAtmosphere '{self.name}': wavelength_um must be strictly positive."
            )

        warnings.warn(
            (
                "TabulatedAtmosphere.evaluate: backend does not carry the "
                "Option C two-leg split — collapsing τ_sun=τ_up=τ_full_up and "
                "L_path_up=L_path_full to the single tabulated value.  "
                "Two-leg scenarios need a richer tabulated format (Stage 6+)."
            ),
            UserWarning,
            stacklevel=2,
        )

        target_grid = SpectralGrid(wavelengths_um=lam)
        tau = np.asarray(self.transmittance_data.resample(target_grid).values, dtype=np.float64)
        lpath = np.asarray(
            self.path_radiance_data.resample(target_grid).values, dtype=np.float64
        )
        ldown = np.asarray(
            self.atm_emission_down_data.resample(target_grid).values, dtype=np.float64
        )

        E_TOA = np.asarray(toa_solar_spectral_irradiance(lam), dtype=np.float64)
        E_sky_thermal = np.pi * ldown
        E_sky_scattered = np.zeros_like(lam)

        # Clamp for the __post_init__ non-negative invariants.
        E_sky_thermal = np.maximum(E_sky_thermal, 0.0)

        return AtmosphericQuantities(
            wavelength_um=lam,
            tau_sun=tau,
            tau_up=tau.copy(),
            tau_full_up=tau.copy(),
            E_TOA=E_TOA,
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=lpath,
            L_path_full=lpath.copy(),
        )
