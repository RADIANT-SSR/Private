"""Tests for the config-document facade (ADR-0009 / GUI plan FW-1).

Covers the declarative optical-element document path end to end:
preview (no mutation), attach + evaluate (full-prescription dispatch),
save/load persistence parity (D4), precedence vs raw injections, file
normalization, and the bare-loader section guard (Rule 17).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from radiant.api import Sensor, preview_optical_elements
from radiant.api._param_registry import build_parameter_set
from radiant.api.config_io import normalize_element_document
from radiant.io.config import ConfigError, load_config, save_config
from radiant.io.element_config import ElementConfigError

# Walk up to the repo root (pyproject.toml) so the test is location-robust.
_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / "pyproject.toml").exists():
    _REPO_ROOT = _REPO_ROOT.parent
_EXAMPLE = _REPO_ROOT / "examples" / "mwir_leo_minimal.yaml"


def _mirror(name: str, reflectance: float = 0.97, temperature_K: float = 293.0) -> dict[str, Any]:
    return {
        "name": name,
        "transfer_mode": "REFLECTIVE",
        "reflectance": reflectance,
        "temperature_K": temperature_K,
        "diameter_m": 0.30,
        "distance_to_fpa_m": 0.9,
    }


def _train() -> list[dict[str, Any]]:
    return [
        _mirror("M1"),
        _mirror("M2", reflectance=0.96),
        {
            "name": "cold_filter",
            "transfer_mode": "REFRACTIVE",
            "kind": "FILTER",
            "transmittance": 0.90,
            "temperature_K": 240.0,
            "diameter_m": 0.05,
            "distance_to_fpa_m": 0.05,
        },
    ]


# ---------------------------------------------------------------------------
# preview_optical_elements
# ---------------------------------------------------------------------------


class TestPreview:
    def test_kirchhoff_derived_emissivity_mirror(self) -> None:
        (p,) = preview_optical_elements([_mirror("M1", reflectance=0.97)])
        assert p.name == "M1"
        assert p.kind == "mirror"
        assert p.reflectance_mean == pytest.approx(0.97, abs=1e-12)
        # Rule 5: epsilon = 1 - R, derived, never an input.
        assert p.emissivity_mean == pytest.approx(0.03, abs=1e-12)
        assert p.spectral_files == ()

    def test_simple_refractive_has_zero_emissivity(self) -> None:
        previews = preview_optical_elements(_train())
        flt = previews[2]
        assert flt.transmittance_mean == pytest.approx(0.90, abs=1e-12)
        assert flt.emissivity_mean == pytest.approx(0.0, abs=1e-12)

    def test_invalid_entry_raises_element_config_error(self) -> None:
        bad = [{"name": "M1", "transfer_mode": "REFLECTIVE"}]  # missing reflectance
        with pytest.raises(ElementConfigError, match="reflectance"):
            preview_optical_elements(bad)

    def test_spectral_file_reference_reported(self, tmp_path: Path) -> None:
        csv = tmp_path / "gold.csv"
        csv.write_text("3.0,0.98\n5.0,0.985\n")
        entry = _mirror("M1")
        entry["reflectance"] = "gold.csv"
        (p,) = preview_optical_elements([entry], base_dir=tmp_path)
        assert p.spectral_files == ("reflectance",)
        assert 0.97 < p.reflectance_mean < 0.99


# ---------------------------------------------------------------------------
# normalize_element_document
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_relative_file_refs_become_absolute(self, tmp_path: Path) -> None:
        csv = tmp_path / "gold.csv"
        csv.write_text("3.0,0.98\n5.0,0.985\n")
        entry = _mirror("M1")
        entry["reflectance"] = "gold.csv"
        (norm,) = normalize_element_document([entry], base_dir=tmp_path)
        assert Path(norm["reflectance"]).is_absolute()
        assert Path(norm["reflectance"]) == csv.resolve()

    def test_scalar_entries_unchanged_and_copied(self) -> None:
        entries = _train()
        normalized = normalize_element_document(entries)
        assert normalized == entries
        assert normalized is not entries
        assert normalized[0] is not entries[0]

    def test_invalid_document_never_stored(self) -> None:
        with pytest.raises(ElementConfigError):
            normalize_element_document([{"name": "x", "transfer_mode": "SIDEWAYS"}])


# ---------------------------------------------------------------------------
# Sensor.set_optical_elements — attach + evaluate
# ---------------------------------------------------------------------------


class TestSensorAttach:
    def test_evaluate_runs_full_prescription(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        result = s.evaluate()
        assert result.stage_outputs["optics"]["transmission_input_mode"] == "full_prescription"

    def test_elements_change_results_physically(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        baseline = s.clone().evaluate()
        s.set_optical_elements(_train())
        with_train = s.evaluate()
        # The 0.97*0.96*0.90 train is lossier than the scalar default:
        # signal must drop, and the change must be real (not noise).
        assert with_train.metrics["snr"] < baseline.metrics["snr"]

    def test_clear_with_none_restores_baseline(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        baseline = s.clone().evaluate()
        s.set_optical_elements(_train())
        s.set_optical_elements(None)
        assert s.optical_elements() is None
        restored = s.evaluate()
        assert restored.metrics["snr"] == pytest.approx(baseline.metrics["snr"], rel=1e-12)

    def test_explicit_injection_overrides_document(self) -> None:
        # Rule of precedence: set_stage_output wins over the document.
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        grid = np.linspace(3.4, 5.0, 50)
        from radiant.io.element_config import parse_element_entries

        override = parse_element_entries([_mirror("only", reflectance=0.5)], grid)
        s.set_stage_output("optics_config", "element_list", override)
        merged = s._merged_extras()
        assert merged is not None
        assert merged["optics_config"]["element_list"] is override

    def test_optical_elements_returns_copy(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        doc = s.optical_elements()
        assert doc is not None
        doc[0]["reflectance"] = 0.1  # mutating the copy must not affect the sensor
        doc2 = s.optical_elements()
        assert doc2 is not None
        assert doc2[0]["reflectance"] == pytest.approx(0.97, abs=1e-12)

    def test_clone_carries_document(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        c = s.clone()
        assert c.optical_elements() == s.optical_elements()


# ---------------------------------------------------------------------------
# Persistence parity (ADR-0009 D4): save -> load round-trip
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_load_round_trip_identical_results(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        first = s.evaluate()

        path = tmp_path / "with_elements.yaml"
        s.save(path)
        assert "optical_elements" in path.read_text()

        s2 = Sensor.load(path)
        doc = s2.optical_elements()
        assert doc is not None and len(doc) == 3
        second = s2.evaluate()
        assert second.metrics["snr"] == pytest.approx(first.metrics["snr"], rel=1e-12)

    def test_save_without_elements_writes_no_section(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        path = tmp_path / "plain.yaml"
        s.save(path)
        assert "optical_elements" not in path.read_text()

    def test_from_dict_accepts_section(self) -> None:
        s = Sensor.from_dict(
            {
                "optics": {"aperture_diameter_m": 0.3, "f_number": 4.0},
                "optical_elements": _train(),
            }
        )
        doc = s.optical_elements()
        assert doc is not None and [e["name"] for e in doc] == ["M1", "M2", "cold_filter"]


# ---------------------------------------------------------------------------
# Bare-loader guard (Rule 17): sections never silently dropped
# ---------------------------------------------------------------------------


class TestLoaderGuard:
    def test_bare_load_config_raises_on_section(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        path = tmp_path / "x.yaml"
        s.save(path)
        with pytest.raises(ConfigError, match="Sensor.load"):
            load_config(path, build_parameter_set())

    def test_sections_out_receives_document(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.set_optical_elements(_train())
        path = tmp_path / "x.yaml"
        s.save(path)
        sections: dict[str, Any] = {}
        load_config(path, build_parameter_set(), sections_out=sections)
        assert [e["name"] for e in sections["optical_elements"]] == ["M1", "M2", "cold_filter"]

    def test_save_config_rejects_unknown_section(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.evaluate()
        with pytest.raises(ConfigError, match="unknown structured section"):
            save_config(
                s._params,
                tmp_path / "y.yaml",
                scope="inputs",
                sections={"not_a_section": []},
            )


class TestResetAll:
    """Gap 93: Sensor.reset_all reverts edits by provenance scope."""

    def test_user_set_scope_clears_edits_keeps_config_inputs(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        # An input NOT in the config file, set interactively: cleared by reset.
        s.set("platform.jitter_rms_urad", 5.0)
        s.reset_all()
        assert "platform.jitter_rms_urad" not in s._params.inputs()
        # Untouched config-file inputs survive: the sensor still resolves.
        assert "optics.aperture_diameter_m" in s._params.inputs()
        s.evaluate()

    def test_edited_config_value_reverts_to_default_not_file(self) -> None:
        """An edit replaces provenance: reset gives the schema default, not the
        file value — the documented no-layered-history semantics (Gap 93)."""
        s = Sensor.from_yaml(_EXAMPLE)
        s.set("optics.aperture_diameter_m", 0.5)  # config value, edited → USER_SET
        s.reset_all()
        assert "optics.aperture_diameter_m" not in s._params.inputs()

    def test_all_scope_clears_everything(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.reset_all(scope="all")
        from radiant.core.parameters import ParameterSet  # noqa: F401 — type check only

        assert dict(s._params.inputs()) == {}

    def test_bad_scope_raises_actionable(self) -> None:
        from radiant.api.errors import ApiValidationError

        s = Sensor.from_yaml(_EXAMPLE)
        with pytest.raises(ApiValidationError, match="scope"):
            s.reset_all(scope="everything")
