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
from radiant.optics.errors import OpticsValidationError

logger = logging.getLogger(__name__)

# Entry keys whose string values are spectral-file references (resolved against
# the document's base directory by this parser). The one list every consumer
# reads — the api document facade (``radiant.api.config_io``) absolutizes these
# keys, and the ``configurations:`` section serializer relativizes them (CU-177
# parity), so a key added here is picked up by both without drift.
SPECTRAL_FILE_KEYS: tuple[str, ...] = (
    "reflectance",
    "transmittance",
    "R1",
    "T1",
    "R2",
    "T2",
    "alpha",
    "n_refr",
)

# Broadcast grid for validating a *scalar-only* entry that arrives without a
# band. Any grid broadcasts a scalar losslessly; the full RADIANT VIS–LWIR span
# is used so the choice is visible rather than arbitrary.
FALLBACK_GRID_UM: np.ndarray = np.linspace(0.4, 20.0, 101)


class ElementConfigError(RadiantError, ValueError):
    """Raised when element YAML configuration is invalid.

    Co-inherits from :class:`ValueError` for back-compat with existing
    ``pytest.raises(ValueError, ...)`` patterns; :class:`RadiantError`
    is the canonical base.
    """


def _load_spectral_csv(path: Path, name: str) -> SpectralData:
    """Load a two-column CSV (wavelength_um, value) into SpectralData."""
    # is_file(), not exists(): an empty or directory path must raise the actionable
    # error below, never leak IsADirectoryError from open() (Rule 15).
    if not path.is_file():
        raise ElementConfigError(
            f"Spectral data file not found: {path}. "
            f"Check the file path for element property '{name}' "
            f"(a scalar value or an existing two-column CSV is required)."
        )
    wavelengths: list[float] = []
    values: list[float] = []
    with open(path, encoding="utf-8") as f:
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


def _spectral_from_inline(mapping: dict[str, Any], name: str) -> SpectralData:
    """Build SpectralData from an inline ``{wavelength_um: [...], values: [...]}`` table.

    The inline form (ADR-0009 follow-on, owner request 2026-07-16) lets an element
    document carry a spectral response directly — pasted or typed in the GUI's
    spectrum dialog, or hand-written in YAML — with no external CSV dependency; it
    round-trips through ``Sensor.save``/``load`` verbatim.
    """
    unknown = sorted(set(mapping) - {"wavelength_um", "values"})
    if unknown:
        raise ElementConfigError(
            f"Inline spectrum for '{name}': unknown key(s) {unknown}. "
            "An inline spectral table has exactly two keys: "
            "'wavelength_um' and 'values'."
        )
    try:
        wavelengths = np.asarray(mapping["wavelength_um"], dtype=np.float64)
        values = np.asarray(mapping["values"], dtype=np.float64)
    except KeyError as exc:
        raise ElementConfigError(
            f"Inline spectrum for '{name}': missing required key {exc}. "
            "Provide both 'wavelength_um' and 'values' lists."
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ElementConfigError(
            f"Inline spectrum for '{name}': entries must be numeric "
            f"({exc}). Provide two equal-length numeric lists."
        ) from exc
    if wavelengths.ndim != 1 or values.ndim != 1 or wavelengths.size != values.size:
        raise ElementConfigError(
            f"Inline spectrum for '{name}': 'wavelength_um' and 'values' must be "
            f"equal-length 1-D lists, got {wavelengths.shape} vs {values.shape}."
        )
    if wavelengths.size < 2:
        raise ElementConfigError(
            f"Inline spectrum for '{name}' must have at least 2 points, got {wavelengths.size}."
        )
    return SpectralData(
        name=name,
        wavelength_um=wavelengths,
        values=values,
        unit="",
        source="inline table",
    )


def _resolve_spectral_or_scalar(
    value: Any,
    name: str,
    config_dir: Path,
) -> float | SpectralData:
    """Resolve a YAML value to float or SpectralData.

    A string is a CSV file path (relative to config_dir); a mapping is an inline
    ``{wavelength_um: [...], values: [...]}`` spectral table; anything else is a
    scalar.
    """
    if isinstance(value, str):
        path = config_dir / value
        return _load_spectral_csv(path, name)
    if isinstance(value, dict):
        return _spectral_from_inline(value, name)
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


def parse_element_entries(
    entries: Any,
    wavelength_um: np.ndarray | None = None,
    base_dir: str | Path | None = None,
    *,
    source_label: str = "<document>",
) -> list[OpticalElement]:
    """Parse a declarative ``optical_elements`` document into elements.

    This is the document-level seam under :func:`load_element_list`
    (ADR-0009 D2): the same entry dicts, whether read from a YAML file
    or authored in memory (GUI element editor, scripting), pass through
    this one parser — it is the single validation authority for element
    documents.

    Parameters
    ----------
    entries:
        The ``optical_elements`` document: a non-empty list of mappings.
    wavelength_um:
        Wavelength grid for broadcasting scalar inputs.  Required when
        any element property is specified as a scalar.
    base_dir:
        Directory against which relative spectral-file references are
        resolved.  Defaults to the current working directory.
    source_label:
        Name used in error messages (a file name or ``"<document>"``).

    Returns
    -------
    list[OpticalElement]
        Ordered list of optical elements from source to focal plane.
    """
    if not isinstance(entries, list) or not entries:
        raise ElementConfigError(
            f"'optical_elements' in '{source_label}' must be a non-empty list."
        )

    config_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    elements: list[OpticalElement] = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ElementConfigError(
                f"Element {i} in '{source_label}' must be a mapping, got {type(entry).__name__}."
            )
        elements.append(_parse_element(entry, wavelength_um, config_dir))
    return elements


def validate_element_entry(
    entry: dict[str, Any],
    *,
    wavelength_um: np.ndarray | None = None,
    base_dir: str | Path | None = None,
) -> OpticalElement:
    """Parse **one** element entry for validation, on a grid it cannot fail.

    The band-agnostic entry point onto :func:`parse_element_entries` (still the
    single validation authority — this is one call into it, not a second
    parser). It exists because authoring-time validation has no band: a caller
    holding an entry dict — the GUI preview, ``Sensor.set_optical_elements``
    normalization, or a per-configuration override in the ``configurations:``
    section — must be able to reject a malformed or Kirchhoff-violating entry
    without asserting which band it will later be evaluated on.

    With an explicit *wavelength_um* the entry parses (and resamples) onto that
    grid — the in-band view. Without one it parses on its **native** grid, so a
    spectral table keeps its own span and a 3–5 µm coating table does not fail
    against a 0.4–20 µm default (band coverage is checked at evaluate time
    against the sensor band, not here); only a scalar-only entry, which has no
    native grid, falls back to :data:`FALLBACK_GRID_UM`.

    Raises
    ------
    ElementConfigError, radiant.optics.errors.OpticsValidationError
        On any invalid entry — the same errors, with the same messages, that
        attach time raises.
    """
    if wavelength_um is not None:
        return parse_element_entries([entry], wavelength_um, base_dir=base_dir)[0]
    try:
        return parse_element_entries([entry], None, base_dir=base_dir)[0]
    except OpticsValidationError as exc:
        if "wavelength_um is required" not in str(exc):
            raise
        # Scalar-only entry: any grid broadcasts it losslessly.
        return parse_element_entries([entry], FALLBACK_GRID_UM, base_dir=base_dir)[0]


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

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict) or "optical_elements" not in config:
        raise ElementConfigError(
            f"Config file '{yaml_path.name}' must contain an 'optical_elements' top-level key."
        )

    elements = parse_element_entries(
        config["optical_elements"],
        wavelength_um,
        base_dir=yaml_path.parent,
        source_label=yaml_path.name,
    )

    logger.info(
        "Loaded %d optical elements from '%s'.",
        len(elements),
        yaml_path.name,
    )
    return elements
