"""Tests for YAML configuration I/O.

Level 1: load/save round-trip, error handling, schema validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from radiant.api._param_registry import build_parameter_set
from radiant.core.parameters import Provenance
from radiant.io.config import ConfigError, _flatten, _unflatten, load_config, save_config

# ---------------------------------------------------------------------------
# Flatten / unflatten helpers
# ---------------------------------------------------------------------------


class TestFlatten:
    @pytest.mark.level1
    def test_simple(self) -> None:
        assert _flatten({"a": {"b": 1}}) == {"a.b": 1}

    @pytest.mark.level1
    def test_deep(self) -> None:
        assert _flatten({"a": {"b": {"c": 3}}}) == {"a.b.c": 3}

    @pytest.mark.level1
    def test_multiple_keys(self) -> None:
        result = _flatten({"x": 1, "y": {"z": 2}})
        assert result == {"x": 1, "y.z": 2}


class TestUnflatten:
    @pytest.mark.level1
    def test_simple(self) -> None:
        assert _unflatten({"a.b": 1}) == {"a": {"b": 1}}

    @pytest.mark.level1
    def test_deep(self) -> None:
        assert _unflatten({"a.b.c": 3}) == {"a": {"b": {"c": 3}}}

    @pytest.mark.level1
    def test_multiple_keys(self) -> None:
        result = _unflatten({"a.b": 1, "a.c": 2})
        assert result == {"a": {"b": 1, "c": 2}}

    @pytest.mark.level1
    def test_roundtrip(self) -> None:
        original = {"source": {"target": {"temperature": 300}}, "optics": {"f": 1.2}}
        assert _unflatten(_flatten(original)) == original


# ---------------------------------------------------------------------------
# load_config — happy paths
# ---------------------------------------------------------------------------


def _full_config_dict() -> dict[str, Any]:
    """Return a complete config dict covering all required parameters."""
    return {
        "source": {"target": {"temperature": 300.0, "emissivity": 0.95}},
        "optics": {
            "aperture_diameter_m": 0.30,
            "focal_length_m": 1.20,
            "transmission_scalar": 0.70,
        },
        "detector": {
            "pixel_pitch_x_um": 18.0,
            "pixel_pitch_y_um": 18.0,
            "qe_value": 0.70,
            "dark_rate_e_per_s": 100.0,
        },
        "geometry": {"sensor_altitude_m": 8000.0},
        "atmosphere": {"standard_atmosphere": "midlat_summer"},
        "spectral_integration": {
            "filter_min_um": 3.5,
            "filter_max_um": 5.0,
            "integration_time_s": 0.005,
        },
        "readout": {
            "read_noise_e_rms": 5.0,
            "gain_e_per_dn": 1.0,
            "adc_bits": 16,
        },
    }


class TestLoadConfigDict:
    """Test load_config with in-memory dicts."""

    @pytest.mark.level1
    def test_basic_dict(self) -> None:
        params = build_parameter_set()
        data = _full_config_dict()
        load_config(data, params)
        params.resolve()
        assert params.get("source.target.temperature") == pytest.approx(300.0, rel=1e-12)
        assert params.get("optics.aperture_diameter_m") == pytest.approx(0.30, rel=1e-12)

    @pytest.mark.level1
    def test_provenance_is_config_file(self) -> None:
        params = build_parameter_set()
        data = _full_config_dict()
        load_config(data, params)
        params.resolve()
        rv = params.get_resolved("source.target.temperature")
        assert rv.provenance == Provenance.CONFIG_FILE

    @pytest.mark.level1
    @pytest.mark.parametrize("reserved_key", ["_extends", "_imports", "_vars"])
    def test_reserved_keys_raise(self, reserved_key: str) -> None:
        """CU-050: unimplemented directives must raise, not silently strip.

        A config relying on `_extends`/`_imports`/`_vars` (documented as
        design targets in RADIANT_Config_Format.md §1.3–1.5) would otherwise
        load "successfully" with the directive ignored — producing physics
        from a different parameter set than the user intended (Rule 17).
        """
        params = build_parameter_set()
        data = {
            reserved_key: "anything",
            "source": {"target": {"temperature": 300.0}},
        }
        with pytest.raises(ConfigError) as excinfo:
            load_config(data, params)
        msg = str(excinfo.value)
        assert reserved_key in msg
        assert "not implemented" in msg
        # Actionable: tells the user what to do instead.
        assert "inline" in msg.lower() or "single complete config" in msg.lower()

    @pytest.mark.level1
    def test_reserved_key_error_names_all_offenders(self) -> None:
        """All present reserved keys are reported in one error, not one at a time."""
        params = build_parameter_set()
        data = {
            "_extends": "parent.yaml",
            "_vars": {"ALT": 8000},
            "source": {"target": {"temperature": 300.0}},
        }
        with pytest.raises(ConfigError) as excinfo:
            load_config(data, params)
        msg = str(excinfo.value)
        assert "_extends" in msg
        assert "_vars" in msg


# ---------------------------------------------------------------------------
# load_config — from YAML file
# ---------------------------------------------------------------------------


class TestLoadConfigFile:
    @pytest.mark.level1
    def test_load_example_yaml(self) -> None:
        """Load examples/mwir_leo_minimal.yaml and verify key values."""
        yaml_path = Path(__file__).parents[3] / "examples" / "mwir_leo_minimal.yaml"
        if not yaml_path.exists():
            # Fall back to project root path.
            yaml_path = Path("examples/mwir_leo_minimal.yaml")
        params = build_parameter_set()
        load_config(yaml_path, params)
        params.resolve()
        assert params.get("source.target.temperature") == pytest.approx(300.0, rel=1e-12)
        assert params.get("optics.aperture_diameter_m") == pytest.approx(0.30, rel=1e-12)
        assert params.get("spectral_integration.integration_time_s") == pytest.approx(
            0.005, rel=1e-12
        )
        assert params.get("readout.adc_bits") == 16

    @pytest.mark.level1
    def test_file_not_found(self, tmp_path: Path) -> None:
        params = build_parameter_set()
        with pytest.raises(ConfigError, match="File not found"):
            load_config(tmp_path / "nonexistent.yaml", params)

    @pytest.mark.level1
    def test_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml", encoding="utf-8")
        params = build_parameter_set()
        with pytest.raises(ConfigError, match="YAML parse error"):
            load_config(bad, params)

    @pytest.mark.level1
    def test_non_dict_top_level(self, tmp_path: Path) -> None:
        bad = tmp_path / "list.yaml"
        bad.write_text("- item1\n- item2\n", encoding="utf-8")
        params = build_parameter_set()
        with pytest.raises(ConfigError, match="Top-level YAML must be a mapping"):
            load_config(bad, params)


# ---------------------------------------------------------------------------
# load_config — error handling
# ---------------------------------------------------------------------------


class TestLoadConfigErrors:
    @pytest.mark.level1
    def test_unknown_parameter(self) -> None:
        params = build_parameter_set()
        data = {"bogus": {"nonexistent_param": 42}}
        with pytest.raises(ConfigError, match="Unknown parameter.*bogus.nonexistent_param"):
            load_config(data, params)

    @pytest.mark.level1
    def test_wrong_type_caught_on_resolve(self) -> None:
        """Type errors are caught by ParameterSet.resolve(), not load_config."""
        params = build_parameter_set()
        data = {"source": {"target": {"temperature": "not_a_number"}}}
        load_config(data, params)  # load succeeds — validation is deferred
        with pytest.raises((ValueError, TypeError)):
            params.set("source.target.emissivity", 0.95)
            params.set("optics.aperture_diameter_m", 0.30)
            params.set("optics.focal_length_m", 1.20)
            params.resolve()

    @pytest.mark.level1
    def test_bad_source_type(self) -> None:
        params = build_parameter_set()
        with pytest.raises(ConfigError, match="Expected a file path or dict"):
            load_config(42, params)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# save_config / round-trip
# ---------------------------------------------------------------------------


class TestSaveConfig:
    @pytest.mark.level1
    def test_round_trip(self, tmp_path: Path) -> None:
        """save → load → compare: values must match."""
        params1 = build_parameter_set()
        params1.set("source.target.temperature", 300.0)
        params1.set("source.target.emissivity", 0.95)
        params1.set("optics.aperture_diameter_m", 0.30)
        params1.set("optics.focal_length_m", 1.20)
        params1.set("optics.transmission_scalar", 0.70)
        params1.set("detector.pixel_pitch_x_um", 18.0)
        params1.set("detector.pixel_pitch_y_um", 18.0)
        params1.set("detector.qe_value", 0.70)
        params1.set("detector.dark_rate_e_per_s", 100.0)
        params1.set("geometry.sensor_altitude_m", 8000.0)
        params1.set("atmosphere.standard_atmosphere", "midlat_summer")
        params1.set("spectral_integration.filter_min_um", 3.5)
        params1.set("spectral_integration.filter_max_um", 5.0)
        params1.set("spectral_integration.integration_time_s", 0.005)
        params1.set("readout.read_noise_e_rms", 5.0)
        params1.set("readout.gain_e_per_dn", 1.0)
        params1.set("readout.adc_bits", 16)
        params1.resolve()

        outfile = tmp_path / "roundtrip.yaml"
        save_config(params1, outfile)

        # Reload into fresh params.
        params2 = build_parameter_set()
        load_config(outfile, params2)
        params2.resolve()

        # Compare all user-set values.
        for name in [
            "source.target.temperature",
            "optics.aperture_diameter_m",
            "optics.focal_length_m",
            "detector.pixel_pitch_x_um",
            "spectral_integration.integration_time_s",
            "readout.adc_bits",
        ]:
            v1 = params1.get(name)
            v2 = params2.get(name)
            if isinstance(v1, float):
                assert v2 == pytest.approx(v1, rel=1e-10), f"{name}: {v2} != {v1}"
            else:
                assert v2 == v1, f"{name}: {v2} != {v1}"

    @pytest.mark.level1
    def test_header_present(self, tmp_path: Path) -> None:
        params = build_parameter_set()
        load_config(_full_config_dict(), params)
        params.resolve()
        outfile = tmp_path / "with_header.yaml"
        save_config(params, outfile, header="# custom header\n")
        text = outfile.read_text(encoding="utf-8")
        assert text.startswith("# custom header\n")

    @pytest.mark.level1
    def test_output_is_valid_yaml(self, tmp_path: Path) -> None:
        params = build_parameter_set()
        load_config(_full_config_dict(), params)
        params.resolve()
        outfile = tmp_path / "valid.yaml"
        save_config(params, outfile)
        parsed = yaml.safe_load(outfile.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# _radiant metadata block (Gap 67)
# ---------------------------------------------------------------------------


class TestRadiantMetaBlock:
    @pytest.mark.level1
    def test_tolerances_applied_on_load(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = {
            "format": 1,
            "tolerances": {
                "detector.qe_value": {
                    "distribution": "gaussian",
                    "params": {"std": 0.02},
                }
            },
        }
        params = load_config(cfg, build_parameter_set())
        tol = params.tolerances()["detector.qe_value"]
        assert tol.distribution == "gaussian"
        assert tol.params == {"std": 0.02}

    @pytest.mark.level1
    def test_meta_block_not_treated_as_parameters(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = {"format": 1, "wavelength_points": 300}
        params = load_config(cfg, build_parameter_set())
        params.resolve()  # no unknown-parameter errors

    @pytest.mark.level1
    def test_caller_dict_not_mutated(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = {"format": 1}
        load_config(cfg, build_parameter_set())
        assert "_radiant" in cfg

    @pytest.mark.level1
    def test_non_mapping_meta_raises(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = ["not", "a", "mapping"]
        with pytest.raises(ConfigError, match="_radiant.*mapping"):
            load_config(cfg, build_parameter_set())

    @pytest.mark.level1
    def test_malformed_tolerance_spec_raises(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = {"tolerances": {"detector.qe_value": {"std": 0.02}}}
        with pytest.raises(ConfigError, match="distribution"):
            load_config(cfg, build_parameter_set())

    @pytest.mark.level1
    def test_tolerance_on_unknown_parameter_raises(self) -> None:
        cfg = _full_config_dict()
        cfg["_radiant"] = {
            "tolerances": {"detector.nope": {"distribution": "gaussian", "params": {"std": 1.0}}}
        }
        with pytest.raises(ConfigError, match="unknown parameter"):
            load_config(cfg, build_parameter_set())

    @pytest.mark.level1
    def test_read_radiant_meta(self, tmp_path: Path) -> None:
        from radiant.io.config import read_radiant_meta

        p = tmp_path / "cfg.yaml"
        p.write_text(
            "_radiant:\n  wavelength_points: 250\noptics:\n  f_number: 4.0\n", encoding="utf-8"
        )
        assert read_radiant_meta(p) == {"wavelength_points": 250}

    @pytest.mark.level1
    def test_read_radiant_meta_absent(self, tmp_path: Path) -> None:
        from radiant.io.config import read_radiant_meta

        p = tmp_path / "cfg.yaml"
        p.write_text("optics:\n  f_number: 4.0\n", encoding="utf-8")
        assert read_radiant_meta(p) == {}


class TestSaveConfigScopes:
    @pytest.mark.level1
    def test_inputs_scope_writes_only_explicit_inputs(self, tmp_path: Path) -> None:
        params = load_config(_full_config_dict(), build_parameter_set())
        params.resolve()
        p = save_config(params, tmp_path / "inputs.yaml", scope="inputs")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        flat = _flatten(raw)
        assert set(flat) == set(params.inputs())
        # Derived f_number must NOT be written in inputs scope.
        assert "optics.f_number" not in flat

    @pytest.mark.level1
    def test_resolved_scope_writes_defaults_too(self, tmp_path: Path) -> None:
        params = load_config(_full_config_dict(), build_parameter_set())
        params.resolve()
        p = save_config(params, tmp_path / "resolved.yaml", scope="resolved")
        flat = _flatten(yaml.safe_load(p.read_text(encoding="utf-8")))
        assert "optics.f_number" in flat  # derived value written

    @pytest.mark.level1
    def test_bad_scope_raises(self, tmp_path: Path) -> None:
        params = load_config(_full_config_dict(), build_parameter_set())
        params.resolve()
        with pytest.raises(ConfigError, match="scope"):
            save_config(params, tmp_path / "x.yaml", scope="everything")

    @pytest.mark.level1
    def test_meta_written_and_reloadable(self, tmp_path: Path) -> None:
        params = load_config(_full_config_dict(), build_parameter_set())
        params.resolve()
        p = save_config(
            params,
            tmp_path / "meta.yaml",
            meta={"format": 1, "wavelength_points": 123},
            scope="inputs",
        )
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert raw["_radiant"] == {"format": 1, "wavelength_points": 123}
        # And the file loads cleanly.
        load_config(p, build_parameter_set()).resolve()


# ---------------------------------------------------------------------------
# CU-177 — file-path parameters are stored portably (relative to the YAML)
# ---------------------------------------------------------------------------


class TestFilePathPortability:
    """save() relativizes is_file_path params; load() resolves them (CU-177)."""

    @staticmethod
    def _csv(dirpath: Path, name: str = "qe.csv") -> Path:
        p = dirpath / name
        p.write_text("wavelength_um,qe\n3.0,0.5\n5.0,0.6\n", encoding="utf-8")
        return p

    @pytest.mark.level1
    def test_save_writes_relative_path(self, tmp_path: Path) -> None:
        """An absolute is_file_path value is stored relative to the output dir."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv = self._csv(data_dir)  # <tmp>/data/qe.csv
        out_dir = tmp_path / "cfg" / "inputs"
        out_dir.mkdir(parents=True)

        params = build_parameter_set()
        params.set("detector.qe_table_path", str(csv.resolve()))
        save_config(params, out_dir / "s.yaml", scope="inputs")

        raw = yaml.safe_load((out_dir / "s.yaml").read_text(encoding="utf-8"))
        stored = raw["detector"]["qe_table_path"]
        assert not Path(stored).is_absolute()
        assert stored == "../../data/qe.csv"  # forward slashes, relative to inputs/

    @pytest.mark.level1
    def test_roundtrip_resolves_to_same_absolute(self, tmp_path: Path) -> None:
        """save (abs -> rel) then load (rel -> abs) recovers the original file."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv = self._csv(data_dir)
        out = tmp_path / "cfg" / "s.yaml"
        out.parent.mkdir()

        params = build_parameter_set()
        params.set("detector.qe_table_path", str(csv.resolve()))
        save_config(params, out, scope="inputs")

        reloaded = build_parameter_set()
        load_config(out, reloaded)
        loaded = reloaded.inputs()["detector.qe_table_path"]
        assert Path(loaded) == csv.resolve()
        assert Path(loaded).exists()

    @pytest.mark.level1
    def test_portable_across_move(self, tmp_path: Path) -> None:
        """Config + data copied to a new tree still resolves to the new location."""
        import shutil

        src = tmp_path / "checkoutA"
        (src / "data").mkdir(parents=True)
        (src / "cfg").mkdir()
        self._csv(src / "data")
        params = build_parameter_set()
        params.set("detector.qe_table_path", str((src / "data" / "qe.csv").resolve()))
        save_config(params, src / "cfg" / "s.yaml", scope="inputs")

        dst = tmp_path / "checkoutB"
        shutil.copytree(src, dst)

        reloaded = build_parameter_set()
        load_config(dst / "cfg" / "s.yaml", reloaded)
        loaded = reloaded.inputs()["detector.qe_table_path"]
        assert Path(loaded) == (dst / "data" / "qe.csv").resolve()
        assert Path(loaded).exists()

    @pytest.mark.level1
    def test_absolute_path_in_config_still_loads(self, tmp_path: Path) -> None:
        """Back-compat: a config with an absolute file-path value passes through."""
        csv = self._csv(tmp_path)
        cfg = tmp_path / "s.yaml"
        cfg.write_text(f"detector:\n  qe_table_path: {csv.resolve()}\n", encoding="utf-8")
        reloaded = build_parameter_set()
        load_config(cfg, reloaded)
        loaded = reloaded.inputs()["detector.qe_table_path"]
        assert Path(loaded) == csv.resolve()

    @pytest.mark.level1
    def test_non_file_path_string_untouched(self, tmp_path: Path) -> None:
        """A non-file-path str param is never rebased, even if it looks path-like."""
        out = tmp_path / "s.yaml"
        params = build_parameter_set()
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        save_config(params, out, scope="inputs")
        raw = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert raw["atmosphere"]["standard_atmosphere"] == "midlat_summer"

    @pytest.mark.level1
    def test_dict_source_leaves_relative_untouched(self) -> None:
        """A dict (no anchor) does not rebase a relative file-path value."""
        params = build_parameter_set()
        load_config({"detector": {"qe_table_path": "rel/qe.csv"}}, params)
        assert params.inputs()["detector.qe_table_path"] == "rel/qe.csv"
