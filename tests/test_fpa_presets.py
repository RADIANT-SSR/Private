"""Shipped-FPA-preset conformance suite (Gap 119, plan §6).

Lives outside ``radiant.data`` because these checks need both the preset
library and the parameter schema (``data/`` may import ``core`` only). Covers
every preset shipped in ``src/radiant/data/tables/fpa/``:

1. **Schema conformance** — every dot-path exists, every value passes
   bounds/enum validation, every unit string converts, via the ordinary
   ``ParameterSet.set(..., unit=...)`` boundary (Rule 16 — the same validation
   hand entry gets).
2. **Provenance completeness** — enforced by the loader; re-asserted here for
   the shipped set.
3. **Reference documents** — every cited ``file:`` exists under
   ``docs/validation/fpa_datasheets/`` and its SHA-256 matches the manifest.
4. **Minimum viable set per part class** (plan §3.2, as implementable today —
   the bolometer class records NEDT in ``notes`` because no schema parameter
   can hold it; Gap 101).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from radiant.api.session import RadiantSession
from radiant.core.parameters import Provenance
from radiant.data import FPALibrary, FPAPreset

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASHEET_DIR = REPO_ROOT / "docs" / "validation" / "fpa_datasheets"
MANIFEST = DATASHEET_DIR / "MANIFEST.md"

LIBRARY = FPALibrary()
SHIPPED = LIBRARY.names()

# Per-class minimum parameter set (plan §3.2, implementable subset).
_ALL_CLASSES_MIN = {
    "detector.pixel_pitch_x_um",
    "detector.pixel_pitch_y_um",
    "detector.n_pixels_cross",
}
_CLASS_MIN: dict[str, set[str]] = {
    "cooled_ir": {
        "readout.full_well_capacity_e",
        "readout.read_noise_e_rms",
        "detector.detector_temperature_K",
    },
    "cooled_ir_droic": {
        "readout.architecture",
        "readout.counter_bits",
        "readout.count_packet_e",
        "readout.residue_readout",
    },
    "uncooled_bolometer": set(),  # NEDT lives in notes — no schema parameter yet (Gap 101)
    "scientific_visible": {
        "readout.full_well_capacity_e",
        "readout.read_noise_e_rms",
        "detector.dark_rate_e_per_s",
    },
    "swir": set(),
}


def _manifest_hashes() -> dict[str, str]:
    """Parse MANIFEST.md table rows into {filename: sha256}."""
    out: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([^`]+\.pdf)`.*`([0-9a-f]{64})`", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def test_library_ships_tranche_one() -> None:
    for expected in (
        "geosnap-18",
        "geosnap-10",
        "flir-neutrino-lc",
        "flir-boson-plus-640",
        "teledyne-h2rg-2p5",
        "dfpa-generic",
    ):
        assert expected in SHIPPED


@pytest.mark.parametrize("name", SHIPPED)
def test_preset_loads(name: str) -> None:
    part = LIBRARY.part(name)
    assert isinstance(part, FPAPreset)
    assert part.band.cut_on_um < part.band.cut_off_um


@pytest.mark.parametrize("name", SHIPPED)
def test_preset_applies_to_schema(name: str) -> None:
    """Every entry sets cleanly on a fresh default ParameterSet."""
    part = LIBRARY.part(name)
    params = RadiantSession.default_params()
    for dotpath, entry in part.parameters.items():
        params.set(
            dotpath,
            entry.value,
            provenance=Provenance.PRESET,
            source=f"fpa:{name}/{entry.source or 'assumed'}",
            unit=entry.unit,
        )


@pytest.mark.parametrize("name", SHIPPED)
def test_cited_documents_exist_and_match_manifest(name: str) -> None:
    part = LIBRARY.part(name)
    manifest = _manifest_hashes()
    for key, src in part.sources.items():
        if src.file is None:
            continue
        pdf = DATASHEET_DIR / src.file
        assert pdf.exists(), f"{name}:{key} cites missing file {src.file}"
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        assert src.file in manifest, f"{src.file} has no MANIFEST.md row"
        assert digest == manifest[src.file], f"{src.file} hash != manifest"


@pytest.mark.parametrize("name", SHIPPED)
def test_minimum_set_for_class(name: str) -> None:
    part = LIBRARY.part(name)
    required = _ALL_CLASSES_MIN | _CLASS_MIN[part.part_class]
    missing = sorted(required - set(part.parameters))
    assert not missing, f"{name} ({part.part_class}) missing minimum set: {missing}"
    if part.part_class == "uncooled_bolometer":
        assert "NEDT" in part.notes, "bolometer preset must record NEDT conditions in notes"
    if part.part_class in ("cooled_ir", "scientific_visible"):
        assert "detector.qe_value" in part.parameters or part.qe_table is not None


@pytest.mark.parametrize("name", SHIPPED)
def test_qe_table_reference_resolves(name: str) -> None:
    part = LIBRARY.part(name)
    if part.qe_table is not None:
        from radiant.data import SpectralLibrary

        assert part.qe_table in SpectralLibrary().detectors()
