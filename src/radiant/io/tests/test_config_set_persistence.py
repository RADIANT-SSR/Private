"""ConfigurationSet persistence — the `configurations:` document end to end.

(ADR-0010 D-D, multi-configuration Phase 2.)

Covers `docs/archive/Multi_Configuration_Plan.md` §6 Phase 2 at the api level:
full round trip, the unchanged shared-only format, load-time validation surfacing
as `ConfigError`, CU-177 file-path parity for configured values, and the
actionable refusal when a section-bearing config file is opened as a plain
`Sensor`.

Lives in `io/tests` because it asserts the **document** (`ConfigurationSet.save`
is the io format's writer); the model-level behaviour is in
`api/tests/test_config_set.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.io.config import ConfigError

_MWIR_YAML = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def dual_band() -> ConfigurationSet:
    """A two-configuration MWIR/LWIR study with a per-configuration grid."""
    cs = ConfigurationSet(Sensor.from_yaml(_MWIR_YAML), names=["MWIR", "LWIR"])
    cs.configure("spectral_integration.filter_min_um", [3.95, 8.0])
    cs.configure("spectral_integration.filter_max_um", [4.45, 12.0])
    cs.configure("detector.qe_value")
    cs.set_value("detector.qe_value", "LWIR", 0.62)
    cs.set_wavelength_points("LWIR", 300)
    cs.active = "LWIR"
    cs.baseline = "MWIR"
    return cs


def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestRoundTrip:
    def test_save_load_reproduces_the_set(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        path = dual_band.save(tmp_path / "study.yaml")
        loaded = ConfigurationSet.load(path)

        assert loaded.names() == ("MWIR", "LWIR")  # names and order
        assert dict(loaded.configured()) == dict(dual_band.configured())  # input units
        assert loaded.active == "LWIR"
        assert loaded.baseline == "MWIR"

    def test_per_configuration_wavelength_points_survive(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        loaded = ConfigurationSet.load(dual_band.save(tmp_path / "study.yaml"))
        assert len(loaded.sensor_for("LWIR")._wavelength_grid()) == 300
        assert len(loaded.sensor_for("MWIR")._wavelength_grid()) == 500

    def test_shared_wavelength_points_survive(self, tmp_path: Path) -> None:
        cs = ConfigurationSet(Sensor.from_yaml(_MWIR_YAML), names=["A", "B"])
        cs.set_wavelength_points(None, 120)
        loaded = ConfigurationSet.load(cs.save(tmp_path / "study.yaml"))
        assert _read(tmp_path / "study.yaml")["_radiant"]["wavelength_points"] == 120
        assert len(loaded.sensor_for("B")._wavelength_grid()) == 120

    def test_tolerances_stay_shared_and_survive(self, tmp_path: Path) -> None:
        base = Sensor.from_yaml(_MWIR_YAML)
        base.set_tolerance("detector.dark_rate_e_per_s", "gaussian", std=5.0)
        cs = ConfigurationSet(base, names=["A", "B"])
        loaded = ConfigurationSet.load(cs.save(tmp_path / "study.yaml"))
        tol = loaded.base.tolerances()["detector.dark_rate_e_per_s"]
        assert tol.distribution == "gaussian"
        assert tol.params["std"] == pytest.approx(5.0, rel=1e-12)

    def test_element_document_survives(self, tmp_path: Path) -> None:
        base = Sensor.from_yaml(_MWIR_YAML)
        base.set_optical_elements(
            [
                {
                    "name": "M1",
                    "transfer_mode": "REFLECTIVE",
                    "reflectance": 0.97,
                    "temperature_K": 293.0,
                    "diameter_m": 0.30,
                    "distance_to_fpa_m": 0.9,
                }
            ]
        )
        cs = ConfigurationSet(base, names=["A", "B"])
        cs.configure("detector.qe_value", [0.7, 0.6])
        loaded = ConfigurationSet.load(cs.save(tmp_path / "study.yaml"))
        doc = loaded.base.optical_elements()
        assert doc is not None and doc[0]["name"] == "M1"

    def test_metrics_reproduce_after_round_trip(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        """The physics a reloaded study computes is the physics it was saved with."""
        loaded = ConfigurationSet.load(dual_band.save(tmp_path / "study.yaml"))
        for name in dual_band.names():
            before = dual_band.sensor_for(name).evaluate().metrics["snr"]
            after = loaded.sensor_for(name).evaluate().metrics["snr"]
            assert after == pytest.approx(before, rel=1e-12)

    def test_to_yaml_matches_the_saved_document(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        path = dual_band.save(tmp_path / "study.yaml")
        from_string = yaml.safe_load(dual_band.to_yaml(relative_to=tmp_path))
        assert from_string == _read(path)

    def test_save_returns_the_written_path(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        out = tmp_path / "nested" / "study.yaml"
        assert dual_band.save(out) == out
        assert out.exists()

    def test_saved_file_is_utf8_with_lf_newlines(
        self, dual_band: ConfigurationSet, tmp_path: Path
    ) -> None:
        """Rule 30: explicit encoding and byte-stable newlines via the save path."""
        path = dual_band.save(tmp_path / "study.yaml")
        raw = path.read_bytes()
        assert b"\r\n" not in raw
        raw.decode("utf-8")  # raises if not valid UTF-8


# ---------------------------------------------------------------------------
# Backward compatibility and the degenerate case
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestFormatCompatibility:
    def test_plain_sensor_save_is_unchanged(self, tmp_path: Path) -> None:
        """A Sensor without a set writes today's document — no new keys (Gap 67)."""
        Sensor.from_yaml(_MWIR_YAML).save(tmp_path / "plain.yaml")
        raw = _read(tmp_path / "plain.yaml")
        assert "configurations" not in raw

    def test_degenerate_set_differs_only_by_the_section(self, tmp_path: Path) -> None:
        """Documented choice: the section is always written, even for one configuration.

        Keeping it makes the file self-identifying as a study and preserves the
        configuration's *name* across the round trip (omitting it would silently
        rename a lone renamed configuration on reload).
        """
        base = Sensor.from_yaml(_MWIR_YAML)
        plain = _read(base.save(tmp_path / "plain.yaml"))
        cs = ConfigurationSet(base.clone(), names=["Nominal"])
        study = _read(cs.save(tmp_path / "study.yaml"))

        assert set(study) - set(plain) == {"configurations"}
        assert {k: v for k, v in study.items() if k != "configurations"} == plain
        assert study["configurations"] == {
            "names": ["Nominal"],
            "active": "Nominal",
            "baseline": "Nominal",
        }
        assert ConfigurationSet.load(tmp_path / "study.yaml").names() == ("Nominal",)

    def test_plain_config_loads_as_a_one_configuration_set(self, tmp_path: Path) -> None:
        path = Sensor.from_yaml(_MWIR_YAML).save(tmp_path / "plain.yaml")
        cs = ConfigurationSet.load(path)
        assert len(cs) == 1
        assert dict(cs.configured()) == {}
        assert cs.base.get("optics.aperture_diameter_m") == pytest.approx(0.30, rel=1e-12)

    def test_example_config_still_loads_through_sensor(self) -> None:
        """Registering a new section key must not disturb section-free configs."""
        assert Sensor.from_yaml(_MWIR_YAML).get("optics.aperture_diameter_m") > 0


# ---------------------------------------------------------------------------
# Rule 17 — a study is never loaded as a single configuration
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestSectionBearingFileRefusal:
    @pytest.fixture()
    def study(self, dual_band: ConfigurationSet, tmp_path: Path) -> Path:
        return dual_band.save(tmp_path / "study.yaml")

    def test_sensor_load_raises_actionably(self, study: Path) -> None:
        with pytest.raises(ConfigError) as exc:
            Sensor.load(study)
        msg = str(exc.value)
        assert "configurations" in msg
        assert "ConfigurationSet.load" in msg
        assert str(study) in msg

    def test_sensor_from_yaml_raises_actionably(self, study: Path) -> None:
        with pytest.raises(ConfigError, match="ConfigurationSet.load"):
            Sensor.from_yaml(study)

    def test_bare_load_config_raises_actionably(self, study: Path) -> None:
        from radiant.api._param_registry import build_parameter_set
        from radiant.io.config import load_config

        with pytest.raises(ConfigError, match="ConfigurationSet.load"):
            load_config(study, build_parameter_set())

    def test_from_dict_raises_actionably(self) -> None:
        with pytest.raises(ConfigError, match="ConfigurationSet.load"):
            Sensor.from_dict({"configurations": {"names": ["A"]}})

    def test_opt_in_caller_receives_the_section(self, study: Path) -> None:
        sections: dict[str, Any] = {}
        sensor = Sensor.load(study, sections_out=sections)
        assert sections["configurations"]["names"] == ["MWIR", "LWIR"]
        assert isinstance(sensor, Sensor)


# ---------------------------------------------------------------------------
# Load-time validation (plan §6 Phase 2) through the api entry point
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestLoadValidation:
    @staticmethod
    def _write(tmp_path: Path, section: dict[str, Any], **body: Any) -> Path:
        doc: dict[str, Any] = {
            "spectral_integration": {"filter_min_um": 3.7, "filter_max_um": 4.8},
            "configurations": section,
        }
        doc.update(body)
        path = tmp_path / "study.yaml"
        path.write_text(yaml.dump(doc, sort_keys=True), encoding="utf-8", newline="\n")
        return path

    def test_length_mismatch(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            {"names": ["A", "B", "C"], "parameters": {"detector.qe_value": [0.7, 0.6]}},
        )
        with pytest.raises(ConfigError) as exc:
            ConfigurationSet.load(path)
        msg = str(exc.value)
        assert "study.yaml" in msg and "detector.qe_value" in msg and "'A', 'B', 'C'" in msg

    def test_duplicate_names(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, {"names": ["A", "A"]})
        with pytest.raises(ConfigError, match="repeats configuration 'A'"):
            ConfigurationSet.load(path)

    def test_dotpath_in_both_stores(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            {"names": ["A", "B"], "parameters": {"detector.qe_value": [0.7, 0.6]}},
            detector={"qe_value": 0.8},
        )
        with pytest.raises(ConfigError) as exc:
            ConfigurationSet.load(path)
        assert "ADR-0010 D-B" in str(exc.value)

    def test_unknown_dotpath(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path, {"names": ["A", "B"], "parameters": {"detector.qe_valu": [0.7, 0.6]}}
        )
        with pytest.raises(ConfigError, match="detector.qe_valu"):
            ConfigurationSet.load(path)

    def test_nine_configurations(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, {"names": [f"C{i}" for i in range(9)]})
        with pytest.raises(ConfigError, match="maximum is 8"):
            ConfigurationSet.load(path)

    def test_out_of_bounds_configured_value(self, tmp_path: Path) -> None:
        """A schema-rejected value surfaces as a ConfigError naming file + config."""
        path = self._write(
            tmp_path, {"names": ["A", "B"], "parameters": {"detector.qe_value": [0.7, 5.0]}}
        )
        with pytest.raises(ConfigError) as exc:
            ConfigurationSet.load(path)
        msg = str(exc.value)
        assert "study.yaml" in msg and "'B'" in msg and "detector.qe_value" in msg


# ---------------------------------------------------------------------------
# CU-177 parity for configured file-path values
# ---------------------------------------------------------------------------


@pytest.mark.level1
class TestConfiguredFilePathPortability:
    @staticmethod
    def _csv(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("wavelength_um,qe\n3.0,0.5\n5.0,0.6\n", encoding="utf-8")
        return path

    def test_configured_paths_relativize_and_resolve(self, tmp_path: Path) -> None:
        csv_a = self._csv(tmp_path / "data" / "qe_a.csv")
        csv_b = self._csv(tmp_path / "data" / "qe_b.csv")
        cs = ConfigurationSet(Sensor.from_yaml(_MWIR_YAML), names=["A", "B"])
        cs.configure("detector.qe_table_path", [str(csv_a.resolve()), str(csv_b.resolve())])

        out_dir = tmp_path / "cfg"
        path = cs.save(out_dir / "study.yaml")

        stored = _read(path)["configurations"]["parameters"]["detector.qe_table_path"]
        assert stored == ["../data/qe_a.csv", "../data/qe_b.csv"]  # relative, forward slashes

        loaded = ConfigurationSet.load(path)
        values = loaded.configured()["detector.qe_table_path"]
        assert Path(values[0]) == csv_a.resolve()
        assert Path(values[1]) == csv_b.resolve()
