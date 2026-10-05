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
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from radiant.core.exceptions import RadiantError
from radiant.core.spectral import SpectralData
from radiant.data.substrate import SubstrateError, SubstrateLibrary
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


def _finite_or_none(cell: str) -> float | None:
    """Parse *cell* as a finite float, or ``None`` if it is neither (CU-397).

    Returns a sentinel rather than raising, because the caller's next move depends on
    *where* the bad cell is — the first data-bearing row may legitimately be a column
    header — and an exception used for that branch would be control flow dressed as an
    error, as well as a bare built-in raise the Rule 15 gate rejects.

    ``nan`` and ``inf`` count as "not a number" here even though ``float()`` accepts
    both. Before this guard they were read as **data**: one ``NaN`` row in a coating
    file, interpolated onto the chain grid, produced seven NaN reflectances and seven
    NaN emissivities out of nine points with no error raised anywhere. A NaN in the
    *wavelength* column was caught incidentally downstream by SpectralData's ascending
    check, naming neither the file nor the line; a NaN in the *value* column was caught
    by nothing (Rule 17).
    """
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _looks_like_header(row: list[str]) -> bool:
    """True when *row* reads as a column-header line rather than corrupt data.

    Deliberately narrow. A header's cells are names — letters, underscores, maybe a
    unit in brackets — so a cell that is merely *malformed* ("3..5", "NaN", "inf") must
    not qualify, or a corrupt file would be silently truncated by one row instead of
    refused. "NaN" and "inf" are the trap: they carry letters but ``float()`` accepts
    them, so the letters test alone would wave through exactly the rows a physics input
    must never absorb (Rule 17). Blank cells do not qualify either — an empty leading
    field is a delimiter mistake, not a heading.
    """
    return all(_is_column_name(cell) for cell in row[:2])


def _is_column_name(cell: str) -> bool:
    """True when *cell* reads as a column name rather than a number or a blank."""
    text = cell.strip()
    if not text:
        return False
    try:
        float(text)  # includes "nan", "inf", "-Infinity"
    except ValueError:
        return any(ch.isalpha() for ch in text)
    return False


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
    # utf-8-sig, not utf-8: Excel writes a BOM by default, and a leading U+FEFF turns
    # the first number into an unparseable token. The same reason ``io/qe_csv.py``
    # uses it (CU-397).
    with open(path, encoding="utf-8-sig", newline="") as f:
        for lineno, row in enumerate(csv.reader(f), start=1):
            if not row or row[0].lstrip().startswith("#"):
                continue
            if len(row) < 2:
                continue
            wavelength = _finite_or_none(row[0])
            value = _finite_or_none(row[1])
            if wavelength is None or value is None:
                # A COLUMN-HEADER row is the overwhelmingly common case and is not an
                # error: it is what Excel, pandas and this repo's own substrate tables
                # all write. Skip exactly one, and only as the first data-bearing row,
                # so a non-numeric token further down is still the defect it is.
                if not wavelengths and _looks_like_header(row):
                    continue
                raise ElementConfigError(
                    f"Spectral file '{path}' line {lineno}: expected two finite "
                    f"numbers (wavelength_um, value) but found {row[0]!r}, {row[1]!r}. "
                    f"This file supplies element property '{name}'. Use two numeric "
                    "columns, with any commentary on lines starting with '#'; a single "
                    "column-header row is accepted and skipped. 'NaN' and 'inf' are "
                    "refused rather than interpolated — one of them spreads across the "
                    "whole grid."
                )
            wavelengths.append(wavelength)
            values.append(value)
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


# Element-document keys a model change deleted, mapped to the guidance an author
# needs. Silently ignoring one would leave a document that *looks* like it states
# a near-field geometry while the model no longer has one, so they are hard
# errors (Gap 128).
_REMOVED_ENTRY_KEYS: dict[str, str] = {
    "diameter_m": (
        "Per-element near-field geometry was deleted when the near-field "
        "model became étendue-conserving: the "
        "Lagrange invariant fixes what the focal plane can see, so every "
        "in-beam element is viewed through the one acceptance cone the working "
        "f/# sets — an element cannot subtend more, however large or close it "
        "is. Delete the key; the cone is derived from the effective pupil "
        "(optics.aperture_diameter_m, optics.focal_length_m, "
        "optics.cold_stop_undersize_frac)."
    ),
    "distance_to_fpa_m": (
        "Per-element near-field geometry was deleted when the near-field "
        "model became étendue-conserving: an element "
        "close to the focal plane does not contribute more near-field than one "
        "further away — both are seen through the same acceptance cone. Delete "
        "the key; nothing replaces it."
    ),
}


def _reject_removed_keys(entry: dict[str, Any], element_name: str) -> None:
    """Raise on any element key a model change removed (Rule 15, Rule 17)."""
    for key, guidance in _REMOVED_ENTRY_KEYS.items():
        if key in entry:
            raise ElementConfigError(
                f"Element '{element_name}': '{key}' is no longer an element field. {guidance}"
            )


#: Keys a REFLECTIVE row must not carry — they belong to the refractive model.
#: ``emissivity`` is refused on every element: Rule 5 derives it (ε = 1 − R for a
#: mirror, 1 − T − R through a lens), so an entered value would either be ignored
#: or over-specify the element. A ``reflectance`` on a REFRACTIVE row is *not*
#: refused: a lens surface's reflectance is a real property (the cavity model
#: reads R1/R2, and the simple model's ε = 1 − T − R has a place for it), and the
#: element editor's entry-faithfulness contract carries it through unchanged.
_REFLECTIVE_FOREIGN_KEYS: tuple[str, ...] = ("transmittance", "alpha", "n_refr", "thickness_m")


#: The keys that make a REFRACTIVE entry a *cavity* entry rather than a simple one.
#: Named here because two places must agree on it: the parser, which branches on it, and
#: the inert-substrate check below, which refuses a substrate the other branch would
#: ignore. They disagreed when the substrate door landed (Gap 142) — the door was built
#: in the cavity branch only, so a substrate named on a simple refractive row was
#: accepted, round-tripped into saved YAML, and left emissivity at 0.0: the one quantity
#: the analyst chose the material to obtain. Same failure mode as CU-365.
_CAVITY_SURFACE_KEYS: tuple[str, ...] = ("R1", "T1", "R2", "T2")


def _is_cavity_entry(entry: dict[str, Any]) -> bool:
    """True when a REFRACTIVE entry carries surface coatings, so the cavity model runs."""
    return any(key in entry for key in _CAVITY_SURFACE_KEYS)


def entry_supports_substrate(entry: dict[str, Any]) -> bool:
    """True when a named ``substrate:`` on *entry* would reach the computed answer.

    The public form of the rule :func:`_reject_overspecified_keys` enforces, so a
    caller that wants to *offer* the choice (the GUI's substrate picker) and the parser
    that *validates* it cannot drift apart. A substrate acts only through the cavity
    emission model, which runs for a REFRACTIVE entry carrying surface coatings.
    """
    return str(entry.get("transfer_mode", "")).strip().upper() == "REFRACTIVE" and _is_cavity_entry(
        entry
    )


def _reject_overspecified_keys(
    entry: dict[str, Any], element_name: str, transfer_mode: str
) -> None:
    """Refuse ``emissivity`` on any element and refractive keys on a mirror (CU-365).

    Before this check the keys were silently ignored, retained in the document and
    round-tripped into saved YAML — the author believed their emissivity was in
    effect while Kirchhoff derivation governed (Rule 5, Rule 17).
    """
    if "emissivity" in entry:
        raise ElementConfigError(
            f"Element '{element_name}': 'emissivity' is not an element input. "
            "An optical element's emissivity is derived from its reflectance and "
            "transmittance (ε = 1 − R for a mirror, ε = 1 − T − R through a lens); an "
            "entered value would over-specify it. Remove the key — or, to raise the "
            "element's thermal emission, lower its reflectance/transmittance and set "
            "temperature_K."
        )
    foreign = _REFLECTIVE_FOREIGN_KEYS if transfer_mode == "REFLECTIVE" else ()
    present = [key for key in foreign if key in entry]
    if present:
        raise ElementConfigError(
            f"Element '{element_name}': {present} do not apply to transfer_mode = "
            f"'{transfer_mode}' and would be silently ignored. A REFLECTIVE element takes "
            "'reflectance'; 'transmittance', 'alpha', 'n_refr' and 'thickness_m' belong to "
            "a REFRACTIVE element. Remove the stray key or change transfer_mode."
        )
    if "substrate" in entry and not _is_cavity_entry(entry):
        raise ElementConfigError(
            f"Element '{element_name}': 'substrate' = {entry['substrate']!r} has nothing "
            "to act on here and would be silently ignored. A substrate supplies the bulk "
            "absorption coefficient α and the refractive index n, and those enter the "
            "answer only through the cavity emission model — which also needs the lens "
            "thickness and its surface coatings, neither of which a material can supply. "
            + (
                "A REFLECTIVE element has no bulk to absorb in: light does not pass "
                "through it, so its emissivity is fixed at 1 − R. Remove 'substrate', "
                "or change transfer_mode to REFRACTIVE and "
                "give the cavity fields below."
                if transfer_mode == "REFLECTIVE"
                else "This is a simple refractive element, defined by a single "
                "'transmittance', and that model takes the remaining 1 − T to be "
                "reflection rather than absorption — its emissivity is zero by "
                "construction, so there is no absorption term for a substrate to "
                "supply. Add 'thickness_m' and at least one surface coating value "
                "(R1/T1/R2/T2) to make it a cavity element, which models the bulk "
                "absorption the substrate describes — or remove 'substrate'."
            )
        )


def _substrate_optical_constants(
    substrate_name: str, element_name: str, wavelength_um: np.ndarray | None
) -> tuple[SpectralData, SpectralData]:
    """Resolve a named substrate to ``(alpha, n_refr)`` on the chain grid (Gap 142).

    Resolution happens here, pre-chain, so the optics stage sees an ordinary cavity
    element and Rule 6 is untouched — the stage never learns that a library exists.
    """
    try:
        material = SubstrateLibrary().material(substrate_name)
        if wavelength_um is None:
            # Native-grid parse (the structural-validation path, which has no chain
            # grid yet): a substrate IS a spectral property, so it keeps its own stored
            # extent, exactly as a spectral file does. Resampling onto the generic
            # fallback grid would be wrong here — that grid runs to 20 µm, past the
            # window of every material in the library, so it would turn a structurally
            # valid entry into a spurious out-of-window refusal. The real window check
            # happens at evaluation, against the grid that will actually be used.
            grid = material.wavelength_um
            n_values, alpha_values = material.n_refr, material.alpha_per_m
        else:
            grid = wavelength_um
            n_values, alpha_values = material.resample(wavelength_um)
    except SubstrateError as exc:
        raise ElementConfigError(f"optical element '{element_name}': {exc}") from exc
    alpha = SpectralData(
        name=f"{element_name}.alpha",
        wavelength_um=grid.copy(),
        values=alpha_values,
        unit="1/m",
        source=f"substrate library: {material.name} (tier {material.tier})",
    )
    n_refr = SpectralData(
        name=f"{element_name}.n_refr",
        wavelength_um=grid.copy(),
        values=n_values,
        unit="",
        source=f"substrate library: {material.name} (tier {material.tier})",
    )
    return alpha, n_refr


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
    _reject_removed_keys(entry, str(name))
    transfer_mode = _require(entry, "transfer_mode", name).upper()
    _reject_overspecified_keys(entry, str(name), transfer_mode)

    # Common thermal field. An element carries no geometry (Gap 128).
    temperature_K = float(entry.get("temperature_K", 0.0))

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
        )

    if transfer_mode == "REFRACTIVE":
        # Check whether this is a simple or cavity element.
        if _is_cavity_entry(entry):
            # Cavity element. Surfaces are lossless (Gap 127 Rule 4): per
            # surface, give R or T and the factory derives the complement;
            # giving both requires R + T = 1 (validated by CavityModel).
            def _surface_value(key: str) -> float | SpectralData | None:
                if key not in entry:
                    return None
                return _resolve_spectral_or_scalar(entry[key], f"{name}.{key}", config_dir)

            r1 = _surface_value("R1")
            t1 = _surface_value("T1")
            r2 = _surface_value("R2")
            t2 = _surface_value("T2")
            # Two doors onto the same two quantities (Gap 142, plan §7.5):
            #   substrate: germanium        -> alpha(lambda), n(lambda) from the library
            #   alpha: ... / n_refr: ...    -> stated explicitly (the custom-material path)
            # The named door is a CONVENIENCE OVER the explicit one, never a
            # replacement: an analyst with their own measured alpha must still be able
            # to state it. Giving both over-specifies the element and is refused here,
            # at the single validation authority, exactly as a mirror carrying both a
            # reflectance and an emissivity is (Rule 5).
            substrate_name = entry.get("substrate")
            explicit_optical = [k for k in ("alpha", "n_refr") if k in entry]
            if substrate_name is not None and explicit_optical:
                raise ElementConfigError(
                    f"optical element '{name}' names substrate "
                    f"'{substrate_name}' and also sets "
                    f"{' and '.join(repr(k) for k in explicit_optical)}. A substrate "
                    "supplies exactly those quantities, so giving both over-specifies "
                    "the element and there is no rule for which should win. Keep the "
                    "substrate for a library material, or drop it and state alpha and "
                    "n_refr yourself for a custom one. thickness_m stays either way — "
                    "it belongs to the lens, not to the material."
                )
            if substrate_name is not None:
                alpha, n_refr = _substrate_optical_constants(
                    str(substrate_name), name, wavelength_um
                )
                if wavelength_um is None:
                    # The substrate supplied the only real grid in this entry, so the
                    # rest of it (scalar coatings) broadcasts onto that rather than
                    # onto the generic fallback — which spans 0.4-20 µm, wider than
                    # any material's window, and would turn a structurally valid entry
                    # into a spurious out-of-window refusal.
                    wavelength_um = alpha.wavelength_um
            else:
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
