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
    def test_reserved_keys_ignored(self) -> None:
        params = build_parameter_set()
        data = {
            "_extends": "some_parent.yaml",
            "_vars": {"ALT": 8000},
            "source": {"target": {"temperature": 300.0}},
        }
        # Should not raise — reserved keys are silently stripped.
        load_config(data, params)


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
        text = outfile.read_text()
        assert text.startswith("# custom header\n")

    @pytest.mark.level1
    def test_output_is_valid_yaml(self, tmp_path: Path) -> None:
        params = build_parameter_set()
        load_config(_full_config_dict(), params)
        params.resolve()
        outfile = tmp_path / "valid.yaml"
        save_config(params, outfile)
        parsed = yaml.safe_load(outfile.read_text())
        assert isinstance(parsed, dict)
