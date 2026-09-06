"""Level 0 tests for the FPA preset library (Gap 119, plan Phase 0).

The preset document format is the contract here (plan §3.1): every parameter
value carries per-parameter source attribution (``source``/``basis``/
``location``), values are stored in datasheet-native units, and format
violations raise actionable :class:`~radiant.data.fpa.FPAPresetError`\\ s.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from radiant.core.exceptions import RadiantError
from radiant.data.fpa import FPALibrary, FPAPreset, FPAPresetError

# A complete, valid preset document exercising every format feature:
# native-unit values, all four basis grades, an enum value, a null-unit
# entry, and both source kinds (vendor datasheet + paper).
VALID_PRESET: dict[str, Any] = {
    "fpa_preset": 1,
    "name": "testpart-18",
    "vendor": "Testcorp",
    "model": "TestPart-18",
    "part_class": "cooled_ir_droic",
    "material": "HgCdTe",
    "band": {"label": "MWIR", "cut_on_um": 3.0, "cut_off_um": 5.3},
    "description": "Fixture part for format tests.",
    "parameters": {
        "detector.pixel_pitch_x_um": {
            "value": 18.0,
            "unit": "um",
            "source": "ds2023",
            "basis": "datasheet",
            "location": "p. 2, spec table",
        },
        "readout.architecture": {
            "value": "digital_counting",
            "unit": None,
            "source": "spie2021",
            "basis": "paper",
            "location": "§2",
        },
        "readout.count_packet_e": {
            "value": 4.4e3,
            "unit": "e-",
            "source": "spie2021",
            "basis": "derived",
            "location": "LSB well / 2^16, §3",
        },
        "detector.dark_rate_e_per_s": {
            "value": 1.0e5,
            "unit": "e-/s",
            "basis": "assumed",
            "note": "typical MW HgCdTe at 110 K; no public figure",
        },
    },
    "qe_table": None,
    "sources": {
        "ds2023": {
            "type": "vendor_datasheet",
            "title": "TestPart Product Datasheet",
            "publisher": "Testcorp",
            "year": 2023,
            "url": "https://example.com/testpart.pdf",
            "file": "testpart_datasheet_2023.pdf",
        },
        "spie2021": {
            "type": "paper",
            "title": "Characterization of the TestPart DROIC",
            "authors": "A. Author, B. Author",
            "venue": "Proc. SPIE 11000",
            "year": 2021,
            "doi": "10.1117/12.0000000",
        },
    },
    "notes": "Free-text curation notes.",
}


def write_preset(root: Path, doc: dict[str, Any], filename: str | None = None) -> Path:
    """Write *doc* as a preset YAML under *root* and return the path."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / (filename or f"{doc.get('name', 'broken')}.yaml")
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def fpa_root(tmp_path: Path) -> Path:
    """A temporary preset root holding one valid preset."""
    root = tmp_path / "fpa"
    write_preset(root, VALID_PRESET)
    return root


class TestValidPreset:
    def test_round_trips_every_field(self, fpa_root: Path) -> None:
        part = FPALibrary(data_root=fpa_root).part("testpart-18")
        assert isinstance(part, FPAPreset)
        assert part.name == "testpart-18"
        assert part.vendor == "Testcorp"
        assert part.model == "TestPart-18"
        assert part.part_class == "cooled_ir_droic"
        assert part.material == "HgCdTe"
        assert part.band.label == "MWIR"
        assert part.band.cut_on_um == pytest.approx(3.0, rel=1e-12)
        assert part.band.cut_off_um == pytest.approx(5.3, rel=1e-12)
        assert part.qe_table is None
        assert part.notes.startswith("Free-text")

    def test_parameter_entries_preserve_native_values(self, fpa_root: Path) -> None:
        part = FPALibrary(data_root=fpa_root).part("testpart-18")
        pitch = part.parameters["detector.pixel_pitch_x_um"]
        assert pitch.value == pytest.approx(18.0, rel=1e-12)
        assert pitch.unit == "um"
        assert pitch.basis == "datasheet"
        assert pitch.source == "ds2023"
        assert pitch.location == "p. 2, spec table"
        arch = part.parameters["readout.architecture"]
        assert arch.value == "digital_counting"
        assert arch.unit is None
        assumed = part.parameters["detector.dark_rate_e_per_s"]
        assert assumed.basis == "assumed"
        assert assumed.source is None
        assert "no public figure" in (assumed.note or "")

    def test_sources_resolve(self, fpa_root: Path) -> None:
        part = FPALibrary(data_root=fpa_root).part("testpart-18")
        ds = part.sources["ds2023"]
        assert ds.type == "vendor_datasheet"
        assert ds.url == "https://example.com/testpart.pdf"
        assert ds.file == "testpart_datasheet_2023.pdf"
        paper = part.sources["spie2021"]
        assert paper.doi == "10.1117/12.0000000"
        assert paper.file is None

    def test_names_sorted(self, fpa_root: Path) -> None:
        second = copy.deepcopy(VALID_PRESET)
        second["name"] = "apart-10"
        write_preset(fpa_root, second)
        assert FPALibrary(data_root=fpa_root).names() == ["apart-10", "testpart-18"]

    def test_empty_root_lists_nothing(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert FPALibrary(data_root=empty).names() == []

    def test_shipped_root_is_default_and_valid(self) -> None:
        # The bundled tables/fpa/ directory: every shipped preset (none yet in
        # Phase 0) must load cleanly; names() must not raise.
        lib = FPALibrary()
        for name in lib.names():
            lib.part(name)


class TestFormatViolations:
    def _reject(self, root: Path, doc: dict[str, Any], match: str) -> None:
        if doc.get("name") == VALID_PRESET["name"]:
            doc["name"] = "bad"
        write_preset(root, doc, filename="bad.yaml")
        with pytest.raises(FPAPresetError, match=match):
            FPALibrary(data_root=root).part("bad")

    def test_unknown_part_is_actionable(self, fpa_root: Path) -> None:
        with pytest.raises(FPAPresetError, match="testpart-18"):
            FPALibrary(data_root=fpa_root).part("no-such-part")

    def test_error_is_radiant_error(self, fpa_root: Path) -> None:
        with pytest.raises(RadiantError):
            FPALibrary(data_root=fpa_root).part("no-such-part")

    def test_missing_top_level_key(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        del doc["vendor"]
        self._reject(tmp_path, doc, match="vendor")

    def test_unsupported_format_version(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["fpa_preset"] = 99
        self._reject(tmp_path, doc, match="fpa_preset")

    def test_bad_part_class(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["part_class"] = "warp_core"
        self._reject(tmp_path, doc, match="part_class")

    def test_bad_basis(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["parameters"]["detector.pixel_pitch_x_um"]["basis"] = "vibes"
        self._reject(tmp_path, doc, match="basis")

    def test_dangling_source_key(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["parameters"]["detector.pixel_pitch_x_um"]["source"] = "nope2020"
        self._reject(tmp_path, doc, match="nope2020")

    def test_assumed_requires_note(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        del doc["parameters"]["detector.dark_rate_e_per_s"]["note"]
        self._reject(tmp_path, doc, match="note")

    def test_assumed_rejects_source(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["parameters"]["detector.dark_rate_e_per_s"]["source"] = "ds2023"
        self._reject(tmp_path, doc, match="assumed")

    def test_sourced_entry_requires_location(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        del doc["parameters"]["detector.pixel_pitch_x_um"]["location"]
        self._reject(tmp_path, doc, match="location")

    def test_namespace_outside_detector_readout(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["parameters"]["optics.aperture_diameter_m"] = {
            "value": 0.1,
            "unit": "m",
            "source": "ds2023",
            "basis": "datasheet",
            "location": "p. 1",
        }
        self._reject(tmp_path, doc, match="optics.aperture_diameter_m")

    def test_unknown_entry_key(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        doc["parameters"]["detector.pixel_pitch_x_um"]["sorce"] = "ds2023"
        self._reject(tmp_path, doc, match="sorce")

    def test_source_needs_url_or_doi(self, tmp_path: Path) -> None:
        doc = copy.deepcopy(VALID_PRESET)
        del doc["sources"]["ds2023"]["url"]
        self._reject(tmp_path, doc, match="url")

    def test_filename_must_match_name(self, tmp_path: Path) -> None:
        write_preset(tmp_path, VALID_PRESET, filename="wrong-slug.yaml")
        with pytest.raises(FPAPresetError, match="wrong-slug"):
            FPALibrary(data_root=tmp_path).part("wrong-slug")
