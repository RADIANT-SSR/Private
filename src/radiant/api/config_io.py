"""Config-document facade for structured (non-scalar) configuration.

Implements ADR-0009 D2/D3: the GUI and scripts author structured
configuration — today the ``optical_elements`` element train — as
**declarative documents** (the same entry dicts the YAML section
carries), and this module is the one bridge between those documents and
the io parsers. The GUI cannot import ``radiant.io`` (import contract);
it previews and commits documents through here, and validation happens
in exactly one place: :func:`radiant.io.element_config.parse_element_entries`.

Two operations:

- :func:`preview_optical_elements` — parse a document and return
  displayable per-element summaries **without mutating any sensor**
  (feeds the GUI import-preview dialog, ADR-0009 D5).
- :func:`normalize_element_document` — validate a document and resolve
  its relative spectral-file references to absolute paths so the stored
  document evaluates and round-trips independently of the current
  working directory (consumed by ``Sensor.set_optical_elements``).

Emissivity in previews is the element's Kirchhoff-derived value
(Rule 5) — it is reported, never accepted as an input here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.io.element_config import parse_element_entries
from radiant.io.zemax_zernike import load_zemax_zernike
from radiant.optics.errors import OpticsValidationError

# Entry keys whose string values are spectral-file references (resolved
# against base_dir by the io parser; absolutized by normalization).
_SPECTRAL_FILE_KEYS: tuple[str, ...] = (
    "reflectance",
    "transmittance",
    "R1",
    "T1",
    "R2",
    "T2",
    "alpha",
    "n_refr",
)

# Default preview grid: the full RADIANT VIS-LWIR span. Band means in a
# preview are computed on this grid unless the caller passes the band of
# interest (the GUI passes the sensor's filter band).
_PREVIEW_GRID_UM: npt.NDArray[np.float64] = np.linspace(0.4, 20.0, 101)


@dataclass(frozen=True, slots=True)
class ElementPreview:
    """Displayable summary of one parsed optical element (no physics objects).

    Attributes
    ----------
    name, kind, transfer_mode:
        Identity fields from the parsed element (kind/transfer_mode as
        lowercase strings).
    temperature_K, diameter_m, distance_to_fpa_m:
        Thermal/geometry scalars as parsed.
    reflectance_mean, transmittance_mean, emissivity_mean:
        Band-mean R / T / ε over the preview grid. Emissivity is the
        **Kirchhoff-derived** value (Rule 5) — mirrors ε = 1 − R,
        refractive per the element's cavity model.
    spectral_files:
        The entry keys that referenced a spectral CSV file (empty for a
        fully scalar entry).
    """

    name: str
    kind: str
    transfer_mode: str
    temperature_K: float
    diameter_m: float
    distance_to_fpa_m: float
    reflectance_mean: float
    transmittance_mean: float
    emissivity_mean: float
    spectral_files: tuple[str, ...]


def _parse_entry_for_display(
    entry: dict[str, Any],
    base_dir: str | Path | None,
    wavelength_um: npt.NDArray[np.float64] | None,
) -> Any:
    """Parse one entry for validation/preview, on its own spectral grid.

    With an explicit *wavelength_um* the entry parses (and resamples) onto that
    grid — the in-band view. Without one, the entry parses on its **native** grid
    (a spectral table keeps its own span; band coverage is checked at evaluate
    time against the sensor band, not here), falling back to the wide preview
    grid only when the entry is scalar-only and needs a broadcast grid. This
    keeps structural/Kirchhoff validation independent of any assumed band — a
    3–5 µm coating table must not fail a 0.4–20 µm default (found 2026-07-16).
    """
    if wavelength_um is not None:
        return parse_element_entries([entry], wavelength_um, base_dir=base_dir)[0]
    try:
        return parse_element_entries([entry], None, base_dir=base_dir)[0]
    except OpticsValidationError as exc:
        if "wavelength_um is required" not in str(exc):
            raise
        # Scalar-only entry: any grid broadcasts it losslessly.
        return parse_element_entries([entry], _PREVIEW_GRID_UM, base_dir=base_dir)[0]


def preview_optical_elements(
    entries: list[dict[str, Any]],
    *,
    wavelength_um: npt.NDArray[np.float64] | None = None,
    base_dir: str | Path | None = None,
) -> tuple[ElementPreview, ...]:
    """Parse an element document and return per-element display summaries.

    Runs the real io parser (single validation authority — a document
    that previews cleanly will also attach cleanly) and reduces each
    parsed element to plain display values. Nothing is mutated; no
    sensor is involved.

    Parameters
    ----------
    entries:
        The ``optical_elements`` document (list of entry mappings).
    wavelength_um:
        Grid for scalar broadcasting and band means. Pass the sensor
        band for in-band means; without it each element previews on its
        **own** spectral grid (scalar-only entries broadcast on the
        0.4–20 µm preview grid), so means are over the data's span.
    base_dir:
        Directory for relative spectral-file references (default: cwd).

    Raises
    ------
    radiant.io.element_config.ElementConfigError
        On any invalid entry — same error, same message, as attach time.
    """
    grid = None if wavelength_um is None else np.asarray(wavelength_um, np.float64)
    elements = [_parse_entry_for_display(entry, base_dir, grid) for entry in entries]
    previews: list[ElementPreview] = []
    for entry, element in zip(entries, elements, strict=True):
        files = tuple(k for k in _SPECTRAL_FILE_KEYS if isinstance(entry.get(k), str))
        previews.append(
            ElementPreview(
                name=element.name,
                kind=element.kind.value,
                transfer_mode=(
                    element.transfer_mode.value if element.transfer_mode is not None else ""
                ),
                temperature_K=float(element.temperature_K),
                diameter_m=float(element.diameter_m),
                distance_to_fpa_m=float(element.distance_to_fpa_m),
                reflectance_mean=float(np.mean(element.reflectance.values)),
                transmittance_mean=float(np.mean(element.transmittance.values)),
                emissivity_mean=float(np.mean(element.emissivity.values)),
                spectral_files=files,
            )
        )
    return tuple(previews)


def normalize_element_document(
    entries: list[dict[str, Any]],
    *,
    base_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Validate an element document and absolutize its file references.

    Returns a deep copy of *entries* in which every relative
    spectral-file reference is resolved against *base_dir* (default:
    cwd) to an absolute path — so the stored document evaluates and
    survives ``Sensor.save()`` regardless of where the config is later
    saved or loaded. Validation runs through the io parser first
    (fail-fast: an invalid document never gets stored).

    Raises
    ------
    radiant.io.element_config.ElementConfigError
        On any invalid entry.
    """
    # Fail fast through the single validation authority. Each entry validates on
    # its own spectral grid (band coverage is evaluate-time, not authoring-time);
    # parsed values are discarded.
    for entry in entries:
        _parse_entry_for_display(entry, base_dir, None)

    root = Path(base_dir) if base_dir is not None else Path.cwd()
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        clean = copy.deepcopy(entry)
        for key in _SPECTRAL_FILE_KEYS:
            value = clean.get(key)
            if isinstance(value, str) and not Path(value).is_absolute():
                clean[key] = str((root / value).resolve())
        normalized.append(clean)
    return normalized


__all__ = [
    "ElementPreview",
    "ZernikePreview",
    "preview_zemax_zernike",
    "preview_optical_elements",
    "normalize_element_document",
]


@dataclass(frozen=True, slots=True)
class ZernikePreview:
    """Displayable summary of a Zemax Zernike export (no physics objects).

    ``rms_waves`` is the RSS of every non-piston coefficient (piston Z1 carries
    no image-quality information); ``coefficients`` are (Noll index, waves)
    pairs in index order for the GUI's confirmation table.
    """

    n_terms: int
    reference_wavelength_um: float | None
    rms_waves: float
    coefficients: tuple[tuple[int, float], ...]


def preview_zemax_zernike(path: str | Path) -> ZernikePreview:
    """Parse a Zemax Zernike export for display — the D5 confirm-before-Apply view.

    Runs the real io parser (same errors as attach time); nothing is mutated.
    The GUI shows this summary before committing ``optics.zernike_file``.
    """
    result = load_zemax_zernike(path)
    non_piston = [c for noll, c in result.zernike_coeffs.items() if noll != 1]
    rms = float(np.sqrt(np.sum(np.square(non_piston)))) if non_piston else 0.0
    return ZernikePreview(
        n_terms=result.n_terms,
        reference_wavelength_um=result.reference_wavelength_um,
        rms_waves=rms,
        coefficients=tuple(sorted(result.zernike_coeffs.items())),
    )
