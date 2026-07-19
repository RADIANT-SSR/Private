"""SpectralLibrary — load bundled spectral data (materials, detectors, solar).

The library reads CSV files shipped in the ``data/`` directory at the
repository root and returns :class:`~radiant.core.spectral.SpectralData`
objects ready for use in RADIANT signal-chain calculations.

Usage::

    from radiant.data import SpectralLibrary

    lib = SpectralLibrary()
    emiss = lib.material("aluminum")       # SpectralData
    qe    = lib.detector_qe("silicon")     # SpectralData
    solar = lib.solar()                    # SpectralData
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from radiant.core.spectral import SpectralData

logger = logging.getLogger(__name__)

# Root of the ``data/`` tree — three levels up from this file
# (this file is src/radiant/data/library.py → repo root is ../../../)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_ROOT = _REPO_ROOT / "data"


def _load_csv(path: Path, value_column: str) -> tuple[np.ndarray, np.ndarray]:
    """Read a two-column CSV (wavelength_um, *value_column*).

    Returns (wavelength_um, values) as float64 arrays.
    """
    wavelengths: list[float] = []
    values: list[float] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or value_column not in reader.fieldnames:
            raise KeyError(
                f"CSV '{path.name}' missing column '{value_column}'; "
                f"found columns: {reader.fieldnames}"
            )
        for row in reader:
            wavelengths.append(float(row["wavelength_um"]))
            values.append(float(row[value_column]))
    return np.array(wavelengths, dtype=np.float64), np.array(values, dtype=np.float64)


class SpectralLibrary:
    """Provides access to the bundled RADIANT spectral data library.

    Parameters
    ----------
    data_root:
        Override path to the ``data/`` directory.  Defaults to the
        ``data/`` directory at the repository root.
    """

    def __init__(self, data_root: Path | None = None) -> None:
        self._root = Path(data_root) if data_root is not None else _DATA_ROOT
        self._manifest: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Material emissivity
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, Any]:
        """Load and cache the emissivity manifest."""
        if self._manifest is None:
            manifest_path = self._root / "emissivity" / "manifest.yaml"
            with open(manifest_path, encoding="utf-8") as fh:
                self._manifest = yaml.safe_load(fh)
        return self._manifest  # type: ignore[return-value]

    def materials(self) -> list[str]:
        """Return sorted list of available material names."""
        return sorted(self._load_manifest().keys())

    def material(self, name: str) -> SpectralData:
        """Load emissivity spectrum for a material.

        Parameters
        ----------
        name:
            Material name (e.g. ``"aluminum"``, ``"vegetation_green"``).

        Returns
        -------
        SpectralData
            Emissivity vs. wavelength (dimensionless, 0–1).
        """
        manifest = self._load_manifest()
        if name not in manifest:
            raise KeyError(
                f"Unknown material '{name}'. Available: {', '.join(sorted(manifest.keys()))}"
            )
        entry = manifest[name]
        csv_path = self._root / "emissivity" / entry["filename"]
        wl, vals = _load_csv(csv_path, "emissivity")
        return SpectralData(
            name=f"emissivity_{name}",
            wavelength_um=wl,
            values=vals,
            unit="dimensionless",
            source=entry.get("source_citation", "RADIANT data library"),
            source_parameters={
                "material": name,
                "description": entry.get("description", ""),
                "default_temperature_K": entry.get("default_temperature_K"),
            },
        )

    def material_info(self, name: str) -> dict[str, Any]:
        """Return manifest metadata for a material (description, temperature, citation)."""
        manifest = self._load_manifest()
        if name not in manifest:
            raise KeyError(
                f"Unknown material '{name}'. Available: {', '.join(sorted(manifest.keys()))}"
            )
        return dict(manifest[name])

    # ------------------------------------------------------------------
    # Detector QE
    # ------------------------------------------------------------------

    def detectors(self) -> list[str]:
        """Return sorted list of available detector QE material names."""
        det_dir = self._root / "detectors"
        if not det_dir.is_dir():
            return []
        return sorted(p.stem for p in det_dir.glob("*.csv"))

    def detector_qe(self, material: str) -> SpectralData:
        """Load quantum efficiency spectrum for a detector material.

        Parameters
        ----------
        material:
            Detector material name (e.g. ``"silicon"``, ``"hgcdte_mwir"``).

        Returns
        -------
        SpectralData
            QE vs. wavelength (dimensionless, 0–1).
        """
        csv_path = self._root / "detectors" / f"{material}.csv"
        if not csv_path.exists():
            available = self.detectors()
            raise KeyError(
                f"Unknown detector material '{material}'. Available: {', '.join(available)}"
            )
        wl, vals = _load_csv(csv_path, "qe")
        return SpectralData(
            name=f"qe_{material}",
            wavelength_um=wl,
            values=vals,
            unit="dimensionless",
            source="RADIANT detector data library",
            source_parameters={"detector_material": material},
        )

    # ------------------------------------------------------------------
    # Solar irradiance
    # ------------------------------------------------------------------

    def solar(self) -> SpectralData:
        """Load the AM0 (exo-atmospheric) solar spectral irradiance.

        Returns
        -------
        SpectralData
            Solar irradiance in W/m²/µm vs. wavelength.
        """
        csv_path = self._root / "solar" / "solar_irradiance_am0.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Solar irradiance file not found: {csv_path}")
        wl, vals = _load_csv(csv_path, "irradiance_W_per_m2_per_um")
        return SpectralData(
            name="solar_irradiance_am0",
            wavelength_um=wl,
            values=vals,
            unit="W/m²/µm",
            source="RADIANT solar data library (Planck-fit to Kopp & Lean 2011 TSI)",
        )
