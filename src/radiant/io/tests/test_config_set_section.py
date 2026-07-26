"""Tests for the ``configurations:`` structured section (ADR-0010 D-D, Phase 2).

Covers the load-time validation matrix of `docs/archive/Multi_Configuration_Plan.md`
§6 Phase 2 at the io level: every violation is a `ConfigError` naming the config
file, the configuration, and the parameter — never a padded or dropped value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.io.config import ConfigError
from radiant.io.config_set_section import (
    SECTION_KEY,
    ConfigurationsSection,
    parse_configurations_section,
    serialize_configurations_section,
)


def _params() -> Any:
    return build_parameter_set()


def _minimal(**overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {"names": ["MWIR", "LWIR"]}
    raw.update(overrides)
    return raw


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestParseValid:
    def test_minimal_section_defaults_active_and_baseline(self) -> None:
        section = parse_configurations_section(_minimal(), _params())
        assert section.names == ("MWIR", "LWIR")
        assert section.active == "MWIR"
        assert section.baseline == "MWIR"
        assert dict(section.wavelength_points) == {}
        assert dict(section.parameters) == {}

    def test_full_section(self) -> None:
        raw = _minimal(
            active="LWIR",
            baseline="MWIR",
            wavelength_points={"LWIR": 300},
            parameters={
                "spectral_integration.filter_min_um": [3.95, 8.0],
                "detector.qe_value": [0.75, 0.62],
            },
        )
        section = parse_configurations_section(raw, _params(), path="study.yaml")
        assert section.active == "LWIR"
        assert section.baseline == "MWIR"
        assert section.wavelength_points == {"LWIR": 300}
        assert section.parameters["detector.qe_value"] == (0.75, 0.62)

    def test_single_configuration_is_valid(self) -> None:
        section = parse_configurations_section({"names": ["Nominal"]}, _params())
        assert section.names == ("Nominal",)
        assert section.active == "Nominal"

    def test_eight_configurations_allowed(self) -> None:
        names = [f"C{i}" for i in range(8)]
        section = parse_configurations_section({"names": names}, _params())
        assert len(section.names) == 8


# ---------------------------------------------------------------------------
# Validation matrix (plan §6 Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestValidationMatrix:
    def test_value_list_length_mismatch(self) -> None:
        raw = _minimal(parameters={"detector.qe_value": [0.75]})
        with pytest.raises(ConfigError) as exc:
            parse_configurations_section(raw, _params(), path="study.yaml")
        msg = str(exc.value)
        assert "study.yaml" in msg  # file
        assert "MWIR" in msg and "LWIR" in msg  # configurations
        assert "detector.qe_value" in msg  # parameter
        assert "never padded" in msg

    def test_duplicate_names(self) -> None:
        raw = {"names": ["MWIR", "MWIR"]}
        with pytest.raises(ConfigError, match="repeats configuration 'MWIR'") as exc:
            parse_configurations_section(raw, _params(), path="study.yaml")
        assert "study.yaml" in str(exc.value)

    def test_dotpath_in_both_stores(self) -> None:
        raw = _minimal(parameters={"detector.qe_value": [0.75, 0.62]})
        with pytest.raises(ConfigError) as exc:
            parse_configurations_section(
                raw,
                _params(),
                shared_inputs={"detector.qe_value": 0.8},
                path="study.yaml",
            )
        msg = str(exc.value)
        assert "study.yaml" in msg
        assert "detector.qe_value" in msg
        assert "shared" in msg and "ADR-0010 D-B" in msg
        assert "MWIR" in msg

    def test_unknown_dotpath_keeps_did_you_mean(self) -> None:
        raw = _minimal(parameters={"detector.qe_valu": [0.75, 0.62]})
        with pytest.raises(ConfigError) as exc:
            parse_configurations_section(raw, _params(), path="study.yaml")
        msg = str(exc.value)
        assert "study.yaml" in msg
        assert "detector.qe_valu" in msg
        assert "Did you mean" in msg or "did you mean" in msg

    def test_more_than_max_configurations(self) -> None:
        raw = {"names": [f"C{i}" for i in range(9)]}
        with pytest.raises(ConfigError) as exc:
            parse_configurations_section(raw, _params(), path="study.yaml", max_configurations=8)
        msg = str(exc.value)
        assert "study.yaml" in msg
        assert "9 configurations" in msg and "maximum is 8" in msg

    def test_active_names_non_member(self) -> None:
        with pytest.raises(ConfigError, match="'configurations.active' names configuration"):
            parse_configurations_section(_minimal(active="SWIR"), _params(), path="study.yaml")

    def test_baseline_names_non_member(self) -> None:
        with pytest.raises(ConfigError, match="'configurations.baseline'"):
            parse_configurations_section(_minimal(baseline="SWIR"), _params())

    def test_missing_names(self) -> None:
        with pytest.raises(ConfigError, match="missing the required 'names' list"):
            parse_configurations_section({"active": "MWIR"}, _params())

    def test_empty_names(self) -> None:
        with pytest.raises(ConfigError, match="at least one"):
            parse_configurations_section({"names": []}, _params())

    def test_non_string_name(self) -> None:
        with pytest.raises(ConfigError, match="not a non-empty string"):
            parse_configurations_section({"names": ["MWIR", ""]}, _params())

    def test_section_not_a_mapping(self) -> None:
        with pytest.raises(ConfigError, match="must be a mapping"):
            parse_configurations_section(["MWIR"], _params())

    def test_unknown_section_key(self) -> None:
        with pytest.raises(ConfigError, match="unknown key"):
            parse_configurations_section(_minimal(parmeters={}), _params())

    def test_parameters_value_not_a_list(self) -> None:
        raw = _minimal(parameters={"detector.qe_value": 0.75})
        with pytest.raises(ConfigError, match="must be a list of 2 values"):
            parse_configurations_section(raw, _params())

    def test_parameters_string_value_is_not_a_list(self) -> None:
        """A bare string must not be read as a two-character sequence."""
        raw = _minimal(parameters={"detector.qe_table_path": "ab"})
        with pytest.raises(ConfigError, match="must be a list of 2 values"):
            parse_configurations_section(raw, _params())

    def test_same_parameter_twice_via_deprecated_alias(self) -> None:
        """A canonical name and its deprecated alias are one row, not two."""
        raw = _minimal(
            parameters={
                "geometry.sensor_altitude_m": [700e3, 500e3],
                "platform.h_sensor": [700e3, 500e3],  # deprecated alias of the above
            }
        )
        with pytest.warns(DeprecationWarning), pytest.raises(ConfigError, match="twice"):
            parse_configurations_section(raw, _params(), path="study.yaml")

    def test_serialize_refuses_a_sparse_column(self) -> None:
        section = ConfigurationsSection(
            names=("A", "B"),
            active="A",
            baseline="A",
            parameters={"detector.qe_value": (0.7,)},
        )
        with pytest.raises(ConfigError, match="refusing to write a sparse"):
            serialize_configurations_section(section, _params())

    def test_wavelength_points_unknown_member(self) -> None:
        raw = _minimal(wavelength_points={"SWIR": 300})
        with pytest.raises(ConfigError, match="wavelength_points' names configuration 'SWIR'"):
            parse_configurations_section(raw, _params(), path="study.yaml")

    def test_wavelength_points_too_small(self) -> None:
        raw = _minimal(wavelength_points={"LWIR": 1})
        with pytest.raises(ConfigError, match="must be an integer >= 2"):
            parse_configurations_section(raw, _params())

    def test_wavelength_points_bool_rejected(self) -> None:
        raw = _minimal(wavelength_points={"LWIR": True})
        with pytest.raises(ConfigError, match="must be an integer >= 2"):
            parse_configurations_section(raw, _params())

    def test_wavelength_points_not_a_mapping(self) -> None:
        with pytest.raises(ConfigError, match="must be a mapping"):
            parse_configurations_section(_minimal(wavelength_points=[300]), _params())


# ---------------------------------------------------------------------------
# CU-177 file-path parity
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestFilePathParity:
    def test_relative_values_resolve_against_the_config_dir(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        (data / "qe.csv").write_text("wavelength_um,qe\n3.0,0.5\n", encoding="utf-8")
        raw = _minimal(parameters={"detector.qe_table_path": ["data/qe.csv", "data/qe.csv"]})

        section = parse_configurations_section(
            raw, _params(), path=tmp_path / "study.yaml", base_dir=tmp_path
        )
        values = section.parameters["detector.qe_table_path"]
        assert all(Path(v).is_absolute() for v in values)
        assert Path(values[0]) == (data / "qe.csv").resolve()

    def test_absolute_values_relativize_on_serialize(self, tmp_path: Path) -> None:
        abs_path = (tmp_path / "data" / "qe.csv").resolve()
        section = ConfigurationsSection(
            names=("A", "B"),
            active="A",
            baseline="A",
            parameters={"detector.qe_table_path": (str(abs_path), str(abs_path))},
        )
        out = serialize_configurations_section(section, _params(), relative_to=tmp_path / "cfg")
        stored = out["parameters"]["detector.qe_table_path"]
        assert stored == ["../data/qe.csv", "../data/qe.csv"]  # forward slashes (Rule 30)

    def test_non_file_path_values_untouched_by_relativize(self, tmp_path: Path) -> None:
        section = ConfigurationsSection(
            names=("A", "B"),
            active="A",
            baseline="A",
            parameters={"detector.qe_value": (0.7, 0.6)},
        )
        out = serialize_configurations_section(section, _params(), relative_to=tmp_path)
        assert out["parameters"]["detector.qe_value"] == [0.7, 0.6]


# ---------------------------------------------------------------------------
# Serialize / parse symmetry
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestSerializeRoundTrip:
    def test_document_reparses_to_an_equal_section(self) -> None:
        section = ConfigurationsSection(
            names=("MWIR", "LWIR"),
            active="LWIR",
            baseline="MWIR",
            wavelength_points={"LWIR": 300},
            parameters={"detector.qe_value": (0.75, 0.62)},
        )
        doc = serialize_configurations_section(section, _params())
        again = parse_configurations_section(doc, _params())
        assert again == section

    def test_empty_optional_keys_are_omitted(self) -> None:
        section = ConfigurationsSection(names=("Only",), active="Only", baseline="Only")
        doc = serialize_configurations_section(section, _params())
        assert set(doc) == {"names", "active", "baseline"}

    def test_section_key_constant(self) -> None:
        assert SECTION_KEY == "configurations"
