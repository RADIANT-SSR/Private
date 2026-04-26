"""YAML loader for mixed-train optical element lists.

Parses the ``optical_elements`` section of a YAML sensor config into
a list of :class:`~radiant.optics.element.OpticalElement` objects using
the factory functions (``make_reflective_element``, ``make_refractive_element``,
``make_refractive_cavity_element``).

Spectral inputs (reflectance, transmittance, coating properties) may be
specified as scalars or as file paths to CSV data.  File paths are
resolved relative to the YAML config file location.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from radiant.core.exceptions import RadiantError
from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement
from radiant.optics.element_factories import (
    make_reflective_element,
    make_refractive_cavity_element,
    make_refractive_element,
)

logger = logging.getLogger(__name__)


class ElementConfigError(RadiantError, ValueError):
    """Raised when element YAML configuration is invalid.

    Co-inherits from :class:`ValueError` for back-compat with existing
    ``pytest.raises(ValueError, ...)`` patterns; :class:`RadiantError`
    is the canonical base.
    """


def _load_spectral_csv(path: Path, name: str) -> SpectralData:
    """Load a two-column CSV (wavelength_um, value) into SpectralData."""
    if not path.exists():
        raise ElementConfigError(
            f"Spectral data file not found: {path}. "
            f"Check the file path for element property '{name}'."
        )
    wavelengths: list[float] = []
    values: list[float] = []
    with open(path) as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 2:
                continue
            wavelengths.append(float(row[0]))
            values.append(float(row[1]))
    if len(wavelengths) < 2:
        raise ElementConfigError(
            f"Spectral file '{path}' must have at least 2 data points, got {len(wavelengths)}."
        )
    return SpectralData(
        name=name,
        wavelength_um=np.array(wavelengths, dtype=np.float64),
        values=np.array(values, dtype=np.float64),
        unit="",
        source=f"CSV: {path.name}",
    )


def _resolve_spectral_or_scalar(
    value: Any,
    name: str,
    config_dir: Path,
) -> float | SpectralData:
    """Resolve a YAML value to float or SpectralData.

    If the value is a string, treat it as a file path (relative to
    config_dir) and load spectral data from CSV.  Otherwise return as float.
    """
    if isinstance(value, str):
        path = config_dir / value
        return _load_spectral_csv(path, name)
    return float(value)


def _require(entry: dict[str, Any], key: str, element_name: str) -> Any:
    """Get a required key from an element dict, or raise with clear message."""
    if key not in entry:
        raise ElementConfigError(
            f"Element '{element_name}': missing required field '{key}'. "
            f"Available fields: {list(entry.keys())}."
        )
    return entry[key]


def _parse_element(
    entry: dict[str, Any],
    wavelength_um: np.ndarray | None,
    config_dir: Path,
) -> OpticalElement:
    """Parse a single element dict into an OpticalElement."""
    name = _require(entry, "name", "<unnamed>")
    transfer_mode = _require(entry, "transfer_mode", name).upper()

    # Common geometry/thermal fields.
    temperature_K = float(entry.get("temperature_K", 0.0))
    diameter_m = float(entry.get("diameter_m", 1.0))
    distance_to_fpa_m = float(entry.get("distance_to_fpa_m", 1.0))

    if transfer_mode == "REFLECTIVE":
        reflectance = _resolve_spectral_or_scalar(
            _require(entry, "reflectance", name),
            f"{name}.reflectance",
            config_dir,
        )
        return make_reflective_element(
            name,
            reflectance,
            wavelength_um=wavelength_um,
            temperature_K=temperature_K,
            diameter_m=diameter_m,
            distance_to_fpa_m=distance_to_fpa_m,
        )

    if transfer_mode == "REFRACTIVE":
        # Check whether this is a simple or cavity element.
        if "R1" in entry:
            # Cavity element — all per-surface fields required.
            r1 = _resolve_spectral_or_scalar(
                _require(entry, "R1", name),
                f"{name}.R1",
                config_dir,
            )
            t1 = _resolve_spectral_or_scalar(
                _require(entry, "T1", name),
                f"{name}.T1",
                config_dir,
            )
            r2 = _resolve_spectral_or_scalar(
                _require(entry, "R2", name),
                f"{name}.R2",
                config_dir,
            )
            t2 = _resolve_spectral_or_scalar(
                _require(entry, "T2", name),
                f"{name}.T2",
                config_dir,
            )
            alpha = _resolve_spectral_or_scalar(
                _require(entry, "alpha", name),
                f"{name}.alpha",
                config_dir,
            )
            n_refr = _resolve_spectral_or_scalar(
                _require(entry, "n_refr", name),
                f"{name}.n_refr",
                config_dir,
            )
            thickness_m = float(_require(entry, "thickness_m", name))

            kind_str = entry.get("kind", "LENS").upper()
            kind = ElementKind(kind_str.lower())

            return make_refractive_cavity_element(
                name,
                R1=r1,
                T1=t1,
                R2=r2,
                T2=t2,
                alpha=alpha,
                n_refr=n_refr,
                thickness_m=thickness_m,
                kind=kind,
                wavelength_um=wavelength_um,
                temperature_K=temperature_K,
                diameter_m=diameter_m,
                distance_to_fpa_m=distance_to_fpa_m,
            )

        # Simple refractive element — just transmittance.
        transmittance = _resolve_spectral_or_scalar(
            _require(entry, "transmittance", name),
            f"{name}.transmittance",
            config_dir,
        )
        kind_str = entry.get("kind", "LENS").upper()
        kind = ElementKind(kind_str.lower())

        return make_refractive_element(
            name,
            transmittance,
            kind=kind,
            wavelength_um=wavelength_um,
            temperature_K=temperature_K,
            diameter_m=diameter_m,
            distance_to_fpa_m=distance_to_fpa_m,
        )

    raise ElementConfigError(
        f"Element '{name}': transfer_mode must be 'REFLECTIVE' or "
        f"'REFRACTIVE', got '{transfer_mode}'."
    )


def load_element_list(
    yaml_path: str | Path,
    wavelength_um: np.ndarray | None = None,
) -> list[OpticalElement]:
    """Load a mixed-train optical element list from a YAML file.

    Parameters
    ----------
    yaml_path:
        Path to the YAML config file containing an ``optical_elements``
        section.
    wavelength_um:
        Wavelength grid for broadcasting scalar inputs.  Required when
        any element property is specified as a scalar.

    Returns
    -------
    list[OpticalElement]
        Ordered list of optical elements from source to focal plane.
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise ElementConfigError(f"Config file not found: {yaml_path}")

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict) or "optical_elements" not in config:
        raise ElementConfigError(
            f"Config file '{yaml_path.name}' must contain an 'optical_elements' top-level key."
        )

    entries = config["optical_elements"]
    if not isinstance(entries, list) or not entries:
        raise ElementConfigError(
            f"'optical_elements' in '{yaml_path.name}' must be a non-empty list."
        )

    config_dir = yaml_path.parent
    elements: list[OpticalElement] = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ElementConfigError(
                f"Element {i} in '{yaml_path.name}' must be a mapping, got {type(entry).__name__}."
            )
        elements.append(_parse_element(entry, wavelength_um, config_dir))

    logger.info(
        "Loaded %d optical elements from '%s'.",
        len(elements),
        yaml_path.name,
    )
    return elements
