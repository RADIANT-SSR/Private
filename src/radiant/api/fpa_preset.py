"""Apply a named FPA preset to a ParameterSet (Gap 119, plan §3.4).

The apply contract: **presets seed, explicit values win.** Every preset entry
is set through the ordinary ``ParameterSet.set(..., unit=...)`` boundary with
``Provenance.PRESET`` and source ``fpa:<part>/<source-key>`` — except entries
whose dot-path already has an explicit input (user or config file), which are
skipped and reported. Because the guard is state-based, apply order relative
to config loading does not matter: config values win whether the ``fpa:`` key
is processed before or after the parameter block.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from radiant.core.parameters import ParameterSet, Provenance
from radiant.data.fpa import FPALibrary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FPAApplyReport:
    """Record of one preset application (plan §3.4 override reporting).

    Attributes
    ----------
    part:
        Preset name that was applied.
    applied:
        Dot-paths the preset set (sorted).
    skipped_existing:
        Dot-paths the preset carries but did **not** set because an explicit
        user/config input already held them — those values won (sorted).
    qe_material:
        The QE library curve the preset selected via its ``qe_table``, or
        ``None`` if the preset ships no curve (or an explicit
        ``detector.qe_material`` already won).
    """

    part: str
    applied: tuple[str, ...]
    skipped_existing: tuple[str, ...]
    qe_material: str | None


def apply_fpa_preset(
    params: ParameterSet,
    name: str,
    *,
    library: FPALibrary | None = None,
) -> FPAApplyReport:
    """Apply preset *name* onto *params* and return the override report.

    Raises
    ------
    radiant.data.fpa.FPAPresetError
        If *name* is not in the library or its document is invalid.
    """
    part = (library or FPALibrary()).part(name)
    # Part switching is clean by construction: any previously applied preset's
    # values are removed first, so presets yield to presets — only explicit
    # user/config inputs are sacred (owner live-review 2026-09-06).
    remove_fpa_preset(params)
    existing = {
        dotpath
        for dotpath, prov in params.input_provenances().items()
        if prov is not Provenance.PRESET
    }
    applied: list[str] = []
    skipped: list[str] = []
    for dotpath in sorted(part.parameters):
        entry = part.parameters[dotpath]
        if dotpath in existing:
            skipped.append(dotpath)
            continue
        params.set(
            dotpath,
            entry.value,
            provenance=Provenance.PRESET,
            source=f"fpa:{name}/{entry.source or 'assumed'}",
            unit=entry.unit,
        )
        applied.append(dotpath)

    qe_material: str | None = None
    if part.qe_table is not None:
        if "detector.qe_material" in existing:
            skipped.append("detector.qe_material")
        else:
            params.set(
                "detector.qe_material",
                part.qe_table,
                provenance=Provenance.PRESET,
                source=f"fpa:{name}/qe_table",
            )
            applied.append("detector.qe_material")
            qe_material = part.qe_table

    logger.info(
        "Applied FPA preset '%s': %d parameters set, %d kept their explicit values",
        name,
        len(applied),
        len(skipped),
    )
    return FPAApplyReport(
        part=name,
        applied=tuple(applied),
        skipped_existing=tuple(sorted(skipped)),
        qe_material=qe_material,
    )


@dataclass(frozen=True)
class FPASourceInfo:
    """Citation record of one preset source, for display surfaces."""

    key: str
    type: str
    title: str
    year: int | None
    url: str | None
    doi: str | None
    file: str | None


@dataclass(frozen=True)
class FPAPartInfo:
    """Display metadata for one library part (GUI part selector, Gap 119 §3.6).

    A read-only projection of :class:`radiant.data.fpa.FPAPreset` — the GUI
    imports only ``radiant.api``, so this is its window into the library.
    """

    name: str
    vendor: str
    model: str
    part_class: str
    part_kind: str
    band_label: str
    description: str
    parameter_count: int
    basis_counts: tuple[tuple[str, int], ...]
    sources: tuple[FPASourceInfo, ...]


def available_fpa_parts(*, library: FPALibrary | None = None) -> tuple[FPAPartInfo, ...]:
    """All library parts as display metadata, sorted by part class then name."""
    lib = library or FPALibrary()
    infos: list[FPAPartInfo] = []
    for name in lib.names():
        part = lib.part(name)
        counts: dict[str, int] = {}
        for entry in part.parameters.values():
            counts[entry.basis] = counts.get(entry.basis, 0) + 1
        infos.append(
            FPAPartInfo(
                name=part.name,
                vendor=part.vendor,
                model=part.model,
                part_class=part.part_class,
                part_kind=part.part_kind,
                band_label=part.band.label,
                description=part.description.strip(),
                parameter_count=len(part.parameters),
                basis_counts=tuple(sorted(counts.items())),
                sources=tuple(
                    FPASourceInfo(
                        key=key,
                        type=src.type,
                        title=src.title,
                        year=src.year,
                        url=src.url,
                        doi=src.doi,
                        file=src.file,
                    )
                    for key, src in part.sources.items()
                ),
            )
        )
    infos.sort(key=lambda i: (i.part_class, i.name))
    return tuple(infos)


def remove_fpa_preset(params: ParameterSet) -> tuple[str, ...]:
    """Clear every input carrying ``Provenance.PRESET`` from *params*.

    The inverse of :func:`apply_fpa_preset`: preset-seeded values revert to
    schema defaults / consistency-group derivation (a clean custom starting
    point), while explicit user/config inputs — including post-apply overrides
    — are untouched. Returns the cleared dot-paths, sorted.
    """
    cleared = sorted(
        dotpath for dotpath, prov in params.input_provenances().items() if prov is Provenance.PRESET
    )
    for dotpath in cleared:
        params.clear_input(dotpath)
    if cleared:
        logger.info("Removed FPA preset values: %d parameter(s) cleared", len(cleared))
    return tuple(cleared)
