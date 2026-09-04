"""Config-document facade for structured (non-scalar) configuration.

Implements ADR-0009 D2/D3: the GUI and scripts author structured
configuration — today the ``optical_elements`` element train — as
**declarative documents** (the same entry dicts the YAML section
carries), and this module is the one bridge between those documents and
the io parsers. The GUI cannot import ``radiant.io`` (import contract);
it previews and commits documents through here, and validation happens
in exactly one place: :func:`radiant.io.element_config.parse_element_entries`.

Three operations:

- :func:`preview_optical_elements` — parse a document and return
  displayable per-element summaries **without mutating any sensor**
  (feeds the GUI import-preview dialog, ADR-0009 D5).
- :func:`normalize_element_document` — validate a document and resolve
  its relative spectral-file references to absolute paths so the stored
  document evaluates and round-trips independently of the current
  working directory (consumed by ``Sensor.set_optical_elements``).
- :func:`read_template_meta` — the ``_radiant.template`` metadata block
  of a config file (mission-template name/blurb/specs/tune_next, §4.4a
  welcome screen) without loading a sensor.

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

from radiant.api.errors import ApiValidationError
from radiant.io.element_config import SPECTRAL_FILE_KEYS, validate_element_entry
from radiant.io.zemax_zernike import load_zemax_zernike

# Entry keys whose string values are spectral-file references (resolved
# against base_dir by the io parser; absolutized by normalization). Owned by
# the io parser so this facade and the ``configurations:`` section serializer
# cannot drift from it.
_SPECTRAL_FILE_KEYS: tuple[str, ...] = SPECTRAL_FILE_KEYS


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

    Thin alias over :func:`radiant.io.element_config.validate_element_entry`,
    which owns the band-agnostic parse (native grid first, wide fallback grid
    only for a scalar-only entry) so this facade and the ``configurations:``
    section parser validate entries identically.
    """
    return validate_element_entry(entry, wavelength_um=wavelength_um, base_dir=base_dir)


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


def read_template_meta(path: str | Path) -> dict[str, Any]:
    """The ``_radiant.template`` metadata block of *path* (or ``{}``).

    The GUI's welcome screen and post-load guidance read mission-template
    metadata through this seam (the GUI cannot import ``radiant.io``).
    Raises :class:`radiant.io.config.ConfigError` on unreadable YAML,
    mirroring :func:`radiant.io.config.read_radiant_meta`; a config with no
    template block returns ``{}``.
    """
    from radiant.io.config import read_radiant_meta

    meta = read_radiant_meta(path).get("template", {})
    return dict(meta) if isinstance(meta, dict) else {}


__all__ = [
    "ElementPreview",
    "SpectralImportPreview",
    "preview_spectral_import",
    "load_measured_curve_file",
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


@dataclass(frozen=True, slots=True)
class SpectralImportPreview:
    """Displayable parse of a spectral import file (D5 confirm-before-Apply view).

    ``series`` holds (label-with-unit, values) pairs over ``wavelength_um`` —
    one pair for a QE curve, transmittance + path radiance for a tape7.
    """

    kind: str
    source: str
    n_points: int
    wavelength_um: npt.NDArray[np.float64]
    series: tuple[tuple[str, npt.NDArray[np.float64]], ...]


def preview_spectral_import(kind: str, path: str | Path) -> SpectralImportPreview:
    """Parse a spectral import file for display, without mutating anything.

    ``kind="qe_csv"`` runs the vendor QE loader (header unit auto-detection —
    the same parse attach-time takes via ``detector.qe_table_path``);
    ``kind="tape7"`` runs the MODTRAN tape7 reader (canonical units — the same
    parse ``atmosphere.modtran.tape7_path`` takes). Same errors as attach time.
    """
    if kind == "qe_csv":
        from radiant.io.qe_csv import load_qe_csv

        curve = load_qe_csv(path)
        return SpectralImportPreview(
            kind=kind,
            source=str(path),
            n_points=curve.n_points,
            wavelength_um=curve.wavelength_um,
            series=(("QE [fraction]", curve.qe),),
        )
    if kind == "tape7":
        from radiant.atmosphere.modtran import Tape7Import

        imported = Tape7Import.from_file(path)
        return SpectralImportPreview(
            kind=kind,
            source=str(path),
            n_points=int(imported.wavelength_um.size),
            wavelength_um=imported.wavelength_um,
            series=(
                ("Transmittance [-]", imported.transmittance),
                ("Path radiance [W/m²/sr/µm]", imported.path_radiance),
            ),
        )
    raise ApiValidationError(
        f"preview_spectral_import: unknown kind {kind!r} (expected 'qe_csv' or 'tape7')."
    )


def load_measured_curve_file(path: str | Path, **kwargs: Any) -> Any:
    """Load a two-column measured curve (GT-5 facade over ``io.measurement``).

    The gui import contract forbids ``radiant.gui → radiant.io``; the overlay
    dialog reaches the loader through this one re-export. Same signature and
    errors as :func:`radiant.io.measurement.load_measured_curve`.
    """
    from radiant.io.measurement import load_measured_curve

    return load_measured_curve(path, **kwargs)
