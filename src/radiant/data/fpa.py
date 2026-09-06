"""FPALibrary — named FPA/ROIC preset documents bundled with RADIANT (Gap 119).

A *preset* is a reviewed bundle of ``detector.*`` / ``readout.*`` parameter
values for a real focal-plane part (e.g. ``geosnap-18``), each value carrying
per-parameter source attribution to a citation, with values stored in the
source document's native unit (conversion happens at ``ParameterSet.set(...,
unit=...)`` — Rule 2). Format spec: ``docs/plans/FPA_Preset_Library_Plan.md``
§3.1 (format version 1).

Presets ship inside the package at ``src/radiant/data/tables/fpa/`` (one YAML
per part, filename ``<name>.yaml``) so a wheel install carries them. This
module validates the document *format* only; validation against the parameter
schema happens where importing the schema is legal — at apply time in the API
layer and exhaustively in ``tests/test_fpa_presets.py`` (plan §3.3/§6).

Usage::

    from radiant.data import FPALibrary

    lib = FPALibrary()
    lib.names()                # ['geosnap-18', ...]
    part = lib.part("geosnap-18")
    part.parameters["detector.pixel_pitch_x_um"].value   # 18.0 (native unit)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from radiant.core.exceptions import RadiantError

logger = logging.getLogger(__name__)

# Root of the bundled preset tree (sibling of the spectral tables; ships in
# the wheel). Resolved relative to this module, never the repo root (Rule 30).
_FPA_ROOT = Path(__file__).resolve().parent / "tables" / "fpa"

#: The one preset format version this loader understands.
FORMAT_VERSION = 1

#: Closed part-class taxonomy (plan §3.1/§3.2 — drives the minimum-set check).
PART_CLASSES = frozenset(
    {"cooled_ir", "cooled_ir_droic", "uncooled_bolometer", "scientific_visible", "swir"}
)

#: Closed basis enum: where a parameter value comes from (plan §3.1).
BASES = frozenset({"datasheet", "paper", "derived", "assumed"})

#: Parameter namespaces a preset may set (owner-confirmed scope boundary §8.2.4).
_ALLOWED_NAMESPACES = ("detector.", "readout.")

_TOP_REQUIRED = (
    "fpa_preset",
    "name",
    "vendor",
    "model",
    "part_class",
    "material",
    "band",
    "description",
    "parameters",
    "sources",
)
_TOP_OPTIONAL = ("qe_table", "notes")

_ENTRY_KEYS = frozenset({"value", "unit", "source", "basis", "location", "note"})
_SOURCE_REQUIRED = ("type", "title")
_SOURCE_OPTIONAL = ("authors", "venue", "publisher", "year", "url", "doi", "file", "retrieved")
_SOURCE_TYPES = frozenset({"vendor_datasheet", "paper", "web_page", "other"})


class FPAPresetError(RadiantError):
    """An FPA preset document is missing, malformed, or violates the format.

    Follows the Rule 15 actionable-error contract (``what / why / action /
    context``), like :class:`~radiant.core.parameters.ParameterBoundsError`.
    """

    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.what = what
        self.why = why
        self.action = action
        self.context = dict(context) if context else {}
        parts = [what]
        if why:
            parts.append(f"Why: {why}")
        if action:
            parts.append(f"Action: {action}")
        super().__init__(" | ".join(parts))


@dataclass(frozen=True)
class FPABand:
    """Spectral band of a part: label plus cut-on/cut-off wavelengths in µm."""

    label: str
    cut_on_um: float
    cut_off_um: float


@dataclass(frozen=True)
class FPAParameterEntry:
    """One preset parameter value with its attribution.

    ``value`` is in the *native unit of the cited document* (``unit``); the
    unit conversion to RADIANT canonical happens at apply time via
    ``ParameterSet.set(..., unit=...)``, never here (Rule 2).
    """

    value: Any
    unit: str | None
    basis: str
    source: str | None = None
    location: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class FPASource:
    """One citation a preset's values attribute to."""

    type: str
    title: str
    authors: str | None = None
    venue: str | None = None
    publisher: str | None = None
    year: int | None = None
    url: str | None = None
    doi: str | None = None
    file: str | None = None
    retrieved: str | None = None


@dataclass(frozen=True)
class FPAPreset:
    """A validated, immutable FPA preset document."""

    name: str
    vendor: str
    model: str
    part_class: str
    material: str
    band: FPABand
    description: str
    parameters: Mapping[str, FPAParameterEntry]
    sources: Mapping[str, FPASource]
    qe_table: str | None = None
    notes: str = ""
    path: Path | None = field(default=None, compare=False)


def _require_str(doc: Mapping[str, Any], key: str, *, path: Path) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FPAPresetError(
            what=f"Preset '{path.name}' field '{key}' is missing or not a non-empty string",
            why="Every preset names its part identity so provenance is auditable",
            action=f"Add '{key}: <text>' to {path}",
            context={"path": str(path), "field": key, "value": value},
        )
    return value


def _parse_band(raw: Any, *, path: Path) -> FPABand:
    if not isinstance(raw, Mapping):
        raise FPAPresetError(
            what=f"Preset '{path.name}' 'band' must be a mapping with label/cut_on_um/cut_off_um",
            why="The band block records the spectral envelope the sources describe",
            action="Write band: {label: MWIR, cut_on_um: 3.0, cut_off_um: 5.3}",
            context={"path": str(path), "band": raw},
        )
    missing = [k for k in ("label", "cut_on_um", "cut_off_um") if k not in raw]
    if missing:
        raise FPAPresetError(
            what=f"Preset '{path.name}' band block is missing {missing}",
            why="cut-on/cut-off in µm are the minimum spectral record for any part",
            action="Add the missing band keys (wavelengths in µm)",
            context={"path": str(path), "missing": missing},
        )
    return FPABand(
        label=str(raw["label"]),
        cut_on_um=float(raw["cut_on_um"]),
        cut_off_um=float(raw["cut_off_um"]),
    )


def _parse_entry(
    dotpath: str, raw: Any, source_keys: frozenset[str], *, path: Path
) -> FPAParameterEntry:
    ctx = {"path": str(path), "parameter": dotpath}
    if not dotpath.startswith(_ALLOWED_NAMESPACES):
        raise FPAPresetError(
            what=f"Preset '{path.name}' sets '{dotpath}', outside detector./readout.",
            why="Presets model the FPA/ROIC through readout only (plan §8.2.4); "
            "optics or geometry values from a core datasheet belong elsewhere",
            action="Remove the entry, or move the value to the document that owns it",
            context=ctx,
        )
    if not isinstance(raw, Mapping):
        raise FPAPresetError(
            what=f"Preset '{path.name}' entry '{dotpath}' must be a mapping, "
            f"got {type(raw).__name__}",
            why="Every value carries attribution: value/unit/source/basis/location",
            action="Write the entry as {value, unit, source, basis, location}",
            context=ctx,
        )
    unknown = sorted(set(raw) - _ENTRY_KEYS)
    if unknown:
        raise FPAPresetError(
            what=f"Preset '{path.name}' entry '{dotpath}' has unknown key(s) {unknown}",
            why="Unknown keys are usually typos that would silently drop attribution",
            action=f"Use only {sorted(_ENTRY_KEYS)}",
            context={**ctx, "unknown": unknown},
        )
    for required in ("value", "unit", "basis"):
        if required not in raw:
            raise FPAPresetError(
                what=f"Preset '{path.name}' entry '{dotpath}' is missing '{required}'",
                why="A preset value without unit and basis is not auditable",
                action=f"Add '{required}:' to the entry (unit may be null for "
                "dimensionless/enum values)",
                context=ctx,
            )
    basis = raw["basis"]
    if basis not in BASES:
        raise FPAPresetError(
            what=f"Preset '{path.name}' entry '{dotpath}' basis '{basis}' is not one of "
            f"{sorted(BASES)}",
            why="The basis grade is a closed enum consumers filter and display on",
            action="Use datasheet, paper, derived, or assumed",
            context={**ctx, "basis": basis},
        )
    source = raw.get("source")
    location = raw.get("location")
    note = raw.get("note")
    if basis == "assumed":
        if source is not None:
            raise FPAPresetError(
                what=f"Preset '{path.name}' entry '{dotpath}' is assumed but cites source "
                f"'{source}'",
                why="'assumed' means curator judgment with no supporting document; "
                "a cited value must use datasheet/paper/derived",
                action="Either drop the source (keep basis: assumed + note) or grade the basis "
                "by what the source supports",
                context={**ctx, "source": source},
            )
        if not isinstance(note, str) or not note.strip():
            raise FPAPresetError(
                what=f"Preset '{path.name}' entry '{dotpath}' is assumed but has no note",
                why="An assumption ships only with its justification (plan §3.1)",
                action="Add note: <why this value, what regime it assumes>",
                context=ctx,
            )
    else:
        if not isinstance(source, str) or source not in source_keys:
            raise FPAPresetError(
                what=f"Preset '{path.name}' entry '{dotpath}' cites source '{source}' which is "
                "not in the sources block",
                why="Every non-assumed value must attribute to a listed citation",
                action=f"Cite one of {sorted(source_keys)} or add the source",
                context={**ctx, "source": source, "available": sorted(source_keys)},
            )
        if not isinstance(location, str) or not location.strip():
            raise FPAPresetError(
                what=f"Preset '{path.name}' entry '{dotpath}' has no location",
                why="'Where in the document' is part of the attribution contract "
                "(for derived values, the location states the arithmetic)",
                action="Add location: <page/table/section, or the derivation>",
                context=ctx,
            )
    unit = raw.get("unit")
    return FPAParameterEntry(
        value=raw["value"],
        unit=None if unit is None else str(unit),
        basis=str(basis),
        source=source,
        location=location,
        note=note,
    )


def _parse_source(key: str, raw: Any, *, path: Path) -> FPASource:
    ctx = {"path": str(path), "source": key}
    if not isinstance(raw, Mapping):
        raise FPAPresetError(
            what=f"Preset '{path.name}' source '{key}' must be a mapping",
            why="A citation is a structured record, not a bare string",
            action="Write the source as {type: ..., title: ..., url/doi: ...}",
            context=ctx,
        )
    unknown = sorted(set(raw) - set(_SOURCE_REQUIRED) - set(_SOURCE_OPTIONAL))
    if unknown:
        raise FPAPresetError(
            what=f"Preset '{path.name}' source '{key}' has unknown key(s) {unknown}",
            why="Unknown keys are usually typos that would silently drop citation detail",
            action=f"Use only {sorted(set(_SOURCE_REQUIRED) | set(_SOURCE_OPTIONAL))}",
            context={**ctx, "unknown": unknown},
        )
    for required in _SOURCE_REQUIRED:
        if not isinstance(raw.get(required), str) or not raw[required].strip():
            raise FPAPresetError(
                what=f"Preset '{path.name}' source '{key}' is missing '{required}'",
                why="type and title are the minimum identity of a citation",
                action=f"Add '{required}:' to the source",
                context=ctx,
            )
    if raw["type"] not in _SOURCE_TYPES:
        raise FPAPresetError(
            what=f"Preset '{path.name}' source '{key}' type '{raw['type']}' is not one of "
            f"{sorted(_SOURCE_TYPES)}",
            why="The source type is a closed enum",
            action="Use vendor_datasheet, paper, web_page, or other",
            context={**ctx, "type": raw["type"]},
        )
    if not raw.get("url") and not raw.get("doi"):
        raise FPAPresetError(
            what=f"Preset '{path.name}' source '{key}' has neither url nor doi",
            why="A citation nobody can locate is not a citation (wheel users get "
            "the URL/DOI; the committed PDF is repo-only, plan §3.5)",
            action="Add url: (fetch URL, Wayback URL if delisted) or doi:",
            context=ctx,
        )
    year = raw.get("year")
    return FPASource(
        type=str(raw["type"]),
        title=str(raw["title"]),
        authors=raw.get("authors"),
        venue=raw.get("venue"),
        publisher=raw.get("publisher"),
        year=None if year is None else int(year),
        url=raw.get("url"),
        doi=raw.get("doi"),
        file=raw.get("file"),
        retrieved=raw.get("retrieved"),
    )


def _parse_preset(doc: Any, *, path: Path) -> FPAPreset:
    """Validate a raw YAML document and build the frozen :class:`FPAPreset`."""
    if not isinstance(doc, Mapping):
        raise FPAPresetError(
            what=f"Preset file '{path.name}' is not a YAML mapping",
            why="A preset is a structured document (plan §3.1), not a scalar or list",
            action="Start from an existing preset in tables/fpa/ as a template",
            context={"path": str(path)},
        )
    unknown_top = sorted(set(doc) - set(_TOP_REQUIRED) - set(_TOP_OPTIONAL))
    if unknown_top:
        raise FPAPresetError(
            what=f"Preset '{path.name}' has unknown top-level key(s) {unknown_top}",
            why="Unknown keys are usually typos; the format is closed so drift is loud",
            action=f"Use only {sorted(set(_TOP_REQUIRED) | set(_TOP_OPTIONAL))}",
            context={"path": str(path), "unknown": unknown_top},
        )
    missing_top = [k for k in _TOP_REQUIRED if k not in doc]
    if missing_top:
        raise FPAPresetError(
            what=f"Preset '{path.name}' is missing required key(s) {missing_top}",
            why="Identity, attribution, and format version are all mandatory",
            action="Add the missing keys (see plan §3.1 for the format)",
            context={"path": str(path), "missing": missing_top},
        )
    if doc["fpa_preset"] != FORMAT_VERSION:
        raise FPAPresetError(
            what=f"Preset '{path.name}' declares fpa_preset={doc['fpa_preset']!r}; this loader "
            f"understands version {FORMAT_VERSION}",
            why="The format version gates incompatible future format changes",
            action=f"Set 'fpa_preset: {FORMAT_VERSION}' or upgrade RADIANT",
            context={"path": str(path), "version": doc["fpa_preset"]},
        )
    name = _require_str(doc, "name", path=path)
    if path.stem != name:
        raise FPAPresetError(
            what=f"Preset file '{path.name}' declares name '{name}' — filename and name must match",
            why="The filename is the lookup key; a mismatch makes the part unloadable "
            "under its declared name",
            action=f"Rename the file to '{name}.yaml' or fix the name field",
            context={"path": str(path), "name": name},
        )
    part_class = _require_str(doc, "part_class", path=path)
    if part_class not in PART_CLASSES:
        raise FPAPresetError(
            what=f"Preset '{path.name}' part_class '{part_class}' is not one of "
            f"{sorted(PART_CLASSES)}",
            why="The part class is a closed taxonomy driving the per-class minimum-set check",
            action="Use one of the listed classes",
            context={"path": str(path), "part_class": part_class},
        )
    raw_sources = doc["sources"]
    if not isinstance(raw_sources, Mapping) or not raw_sources:
        raise FPAPresetError(
            what=f"Preset '{path.name}' sources block is missing or empty",
            why="A preset with no citations cannot attribute any value",
            action="Add at least one source (type, title, url or doi)",
            context={"path": str(path)},
        )
    sources = {
        str(key): _parse_source(str(key), raw, path=path) for key, raw in raw_sources.items()
    }
    raw_params = doc["parameters"]
    if not isinstance(raw_params, Mapping) or not raw_params:
        raise FPAPresetError(
            what=f"Preset '{path.name}' parameters block is missing or empty",
            why="A preset that sets nothing models nothing",
            action="Add the sourced detector.*/readout.* values (plan §3.2 minimum set)",
            context={"path": str(path)},
        )
    source_keys = frozenset(sources)
    parameters = {
        str(dotpath): _parse_entry(str(dotpath), raw, source_keys, path=path)
        for dotpath, raw in raw_params.items()
    }
    qe_table = doc.get("qe_table")
    return FPAPreset(
        name=name,
        vendor=_require_str(doc, "vendor", path=path),
        model=_require_str(doc, "model", path=path),
        part_class=part_class,
        material=_require_str(doc, "material", path=path),
        band=_parse_band(doc["band"], path=path),
        description=_require_str(doc, "description", path=path),
        parameters=MappingProxyType(parameters),
        sources=MappingProxyType(sources),
        qe_table=None if qe_table is None else str(qe_table),
        notes=str(doc.get("notes", "")),
        path=path,
    )


class FPALibrary:
    """Access to the bundled named-FPA preset library.

    Parameters
    ----------
    data_root:
        Override path to the preset directory. Defaults to the bundled
        ``tables/fpa/`` directory inside the package.
    """

    def __init__(self, data_root: Path | None = None) -> None:
        self._root = Path(data_root) if data_root is not None else _FPA_ROOT

    def names(self) -> list[str]:
        """Return the sorted list of available part names."""
        if not self._root.is_dir():
            return []
        return sorted(p.stem for p in self._root.glob("*.yaml"))

    def part(self, name: str) -> FPAPreset:
        """Load and format-validate the preset for *name*.

        Raises
        ------
        FPAPresetError
            If no part of that name exists, or its document violates the
            preset format (plan §3.1).
        """
        path = self._root / f"{name}.yaml"
        if not path.exists():
            raise FPAPresetError(
                what=f"Unknown FPA part '{name}'",
                why="Only parts shipped in the preset library (or the data_root "
                "override) can be loaded by name",
                action=f"Choose one of: {', '.join(self.names()) or '(library is empty)'}",
                context={"name": name, "root": str(self._root)},
            )
        with open(path, encoding="utf-8") as fh:
            try:
                doc = yaml.safe_load(fh)
            except yaml.YAMLError as exc:
                raise FPAPresetError(
                    what=f"Preset file '{path.name}' is not valid YAML: {exc}",
                    why="The preset never reached format validation",
                    action="Fix the YAML syntax",
                    context={"path": str(path)},
                ) from exc
        return _parse_preset(doc, path=path)
