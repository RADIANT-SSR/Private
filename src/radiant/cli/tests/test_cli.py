"""Tests for the RADIANT CLI.

Uses Click's CliRunner for isolated invocation without subprocesses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from radiant.cli.main import cli

EXAMPLE_YAML = Path(__file__).parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _write_study(
    tmp_path: Path,
    *,
    section: str | None = None,
    name: str = "study.yaml",
    strip_band: bool = True,
) -> Path:
    """Write a two-configuration study config file (ADR-0010) built on the example.

    The default section makes MWIR/LWIR band variants: the shared body's
    ``filter_min_um`` / ``filter_max_um`` lines are dropped (``strip_band``),
    because a dot-path lives in the shared body **or** in the configured table,
    never both (ADR-0010 D-B). A caller that configures something else keeps
    the band shared.

    The integration time is shortened to 0.1 ms so neither band saturates the
    example's 2 Me- well — a clipped signal would make both configurations
    report the same SNR and mask exactly what these tests assert.
    """
    body = "\n".join(
        line.replace("integration_time_s: 0.005", "integration_time_s: 0.0001")
        for line in EXAMPLE_YAML.read_text(encoding="utf-8").splitlines()
        if not (strip_band and ("filter_min_um" in line or "filter_max_um" in line))
    )
    default_section = """
configurations:
  names: [MWIR, LWIR]
  active: LWIR
  baseline: MWIR
  wavelength_points:
    LWIR: 300
  parameters:
    spectral_integration.filter_min_um: [3.95, 8.0]
    spectral_integration.filter_max_um: [4.45, 12.0]
"""
    path = tmp_path / name
    path.write_text(
        body + (default_section if section is None else section),
        encoding="utf-8",
        newline="\n",
    )
    return path


# ---------------------------------------------------------------------------
# radiant run
# ---------------------------------------------------------------------------


class TestRunCommand:
    @pytest.mark.level2
    def test_run_example(self, runner: CliRunner) -> None:
        """Running the example YAML produces SNR output."""
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        assert result.exit_code == 0, result.output
        assert "SNR:" in result.output
        assert "Signal:" in result.output

    @pytest.mark.level1
    def test_run_rejects_a_configuration_set_file_without_the_flag(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """`radiant run` refuses a study file rather than running its shared body."""
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["run", str(study)])
        assert result.exit_code != 0
        # The refusal names every configuration and the flag that resolves it.
        assert "'MWIR'" in result.output
        assert "'LWIR'" in result.output
        assert "--configuration" in result.output

    @pytest.mark.level2
    def test_run_shows_noise_terms(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        assert result.exit_code == 0
        assert "shot" in result.output
        assert "read" in result.output
        assert "dark_shot" in result.output
        assert "quantization" in result.output

    @pytest.mark.level2
    def test_run_set_override(self, runner: CliRunner) -> None:
        """--set changes the result."""
        r1 = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        r2 = runner.invoke(
            cli,
            [
                "run",
                str(EXAMPLE_YAML),
                "--set",
                "optics.aperture_diameter_m=0.50",
            ],
        )
        assert r1.exit_code == 0
        assert r2.exit_code == 0
        # Overriding a parameter changes the metric.
        snr1 = _extract_snr(r1.output)
        snr2 = _extract_snr(r2.output)
        assert snr2 != snr1

    @pytest.mark.level2
    def test_run_set_unknown_param(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "run",
                str(EXAMPLE_YAML),
                "--set",
                "typo.nonexistent=42",
            ],
        )
        assert result.exit_code != 0
        assert "unknown parameter" in result.output.lower()

    @pytest.mark.level2
    def test_run_set_bad_format(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "run",
                str(EXAMPLE_YAML),
                "--set",
                "no_equals_sign",
            ],
        )
        assert result.exit_code != 0

    @pytest.mark.level2
    def test_run_file_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", "/tmp/does_not_exist_xyz.yaml"])
        assert result.exit_code != 0

    @pytest.mark.level2
    def test_run_invalid_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml", encoding="utf-8")
        result = runner.invoke(cli, ["run", str(bad)])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    @pytest.mark.level2
    def test_run_json_format(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "metrics" in data
        assert "snr" in data["metrics"]

    @pytest.mark.level2
    def test_run_csv_format(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--format", "csv"])
        assert result.exit_code == 0, result.output
        assert "metric,value" in result.output
        assert "snr," in result.output

    @pytest.mark.level2
    def test_run_quiet(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--quiet"])
        assert result.exit_code == 0, result.output
        assert "SNR:" in result.output
        # Quiet suppresses noise term details
        assert "Signal:" not in result.output

    @pytest.mark.level2
    def test_run_output_file(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        result = runner.invoke(
            cli,
            [
                "run",
                str(EXAMPLE_YAML),
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "metrics" in data

    @pytest.mark.level2
    def test_run_provenance_file(self, runner: CliRunner, tmp_path: Path) -> None:
        prov = tmp_path / "provenance.json"
        result = runner.invoke(
            cli,
            [
                "run",
                str(EXAMPLE_YAML),
                "--provenance",
                str(prov),
            ],
        )
        assert result.exit_code == 0, result.output
        assert prov.exists()
        data = json.loads(prov.read_text(encoding="utf-8"))
        assert "parameters" in data


# ---------------------------------------------------------------------------
# radiant validate
# ---------------------------------------------------------------------------


class TestValidateCommand:
    @pytest.mark.level1
    def test_validate_ok(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", str(EXAMPLE_YAML)])
        assert result.exit_code == 0, result.output
        assert "Config OK" in result.output

    @pytest.mark.level1
    def test_validate_file_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", "/tmp/does_not_exist_xyz.yaml"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @pytest.mark.level1
    def test_validate_invalid_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml", encoding="utf-8")
        result = runner.invoke(cli, ["validate", str(bad)])
        assert result.exit_code != 0

    @pytest.mark.level1
    def test_validate_missing_required(self, runner: CliRunner, tmp_path: Path) -> None:
        """YAML with only one param → resolve fails for missing required params."""
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text(
            "source:\n  target:\n    temperature: 300\n",
            encoding="utf-8",
        )
        result = runner.invoke(cli, ["validate", str(incomplete)])
        assert result.exit_code != 0
        assert "validation failed" in result.output.lower()

    @pytest.mark.level1
    def test_validate_unknown_param(self, runner: CliRunner, tmp_path: Path) -> None:
        """YAML with unknown parameter key → error."""
        bad_param = tmp_path / "bad_param.yaml"
        bad_param.write_text(
            "bogus:\n  fake_param: 42\n",
            encoding="utf-8",
        )
        result = runner.invoke(cli, ["validate", str(bad_param)])
        assert result.exit_code != 0
        assert "unknown parameter" in result.output.lower()

    @pytest.mark.level1
    def test_validate_reports_every_configuration_of_a_study(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """A study validates every configuration, one line each (ADR-0010)."""
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["validate", str(study)])
        assert result.exit_code == 0, result.output
        assert "Study OK" in result.output
        assert "2 configuration(s)" in result.output
        # One line per configuration, each carrying that configuration's band
        # and grid density with units.
        assert "MWIR" in result.output and "LWIR" in result.output
        assert "3.950–4.450 µm" in result.output
        assert "8.000–12.000 µm" in result.output
        assert "500 grid points" in result.output
        assert "300 grid points" in result.output

    @pytest.mark.level1
    def test_validate_set_override(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "validate",
                str(EXAMPLE_YAML),
                "--set",
                "optics.aperture_diameter_m=0.50",
            ],
        )
        assert result.exit_code == 0
        assert "Config OK" in result.output


# ---------------------------------------------------------------------------
# radiant explain
# ---------------------------------------------------------------------------


class TestExplainCommand:
    @pytest.mark.level1
    def test_explain_derived_param(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "explain",
                str(EXAMPLE_YAML),
                "optics.f_number",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "f_number" in result.output
        assert "4.0" in result.output

    @pytest.mark.level1
    def test_explain_user_set_param(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "explain",
                str(EXAMPLE_YAML),
                "optics.aperture_diameter_m",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "0.3" in result.output

    @pytest.mark.level1
    def test_explain_with_override(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "explain",
                str(EXAMPLE_YAML),
                "optics.aperture_diameter_m",
                "--set",
                "optics.aperture_diameter_m=0.50",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "0.5" in result.output

    @pytest.mark.level1
    def test_explain_unknown_param(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "explain",
                str(EXAMPLE_YAML),
                "bogus.param",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# radiant sweep
# ---------------------------------------------------------------------------


class TestSweepCommand:
    @pytest.mark.level2
    def test_sweep_basic(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "sweep",
                str(EXAMPLE_YAML),
                "optics.aperture_diameter_m",
                "--min",
                "0.20",
                "--max",
                "0.40",
                "--steps",
                "3",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "snr" in result.output.lower()
        # Should have 3 rows + header + separator = 5 lines minimum
        lines = [line for line in result.output.strip().splitlines() if line.strip()]
        assert len(lines) >= 5

    @pytest.mark.level2
    def test_sweep_output_csv(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "sweep.csv"
        result = runner.invoke(
            cli,
            [
                "sweep",
                str(EXAMPLE_YAML),
                "optics.aperture_diameter_m",
                "--min",
                "0.20",
                "--max",
                "0.30",
                "--steps",
                "2",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "value,snr" in content

    @pytest.mark.level2
    def test_sweep_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "sweep.json"
        result = runner.invoke(
            cli,
            [
                "sweep",
                str(EXAMPLE_YAML),
                "optics.aperture_diameter_m",
                "--min",
                "0.20",
                "--max",
                "0.30",
                "--steps",
                "2",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "values" in data
        assert "metric_values" in data


# ---------------------------------------------------------------------------
# radiant tolerance
# ---------------------------------------------------------------------------


class TestToleranceCommand:
    @pytest.mark.level2
    def test_tolerance_basic(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "tolerance",
                str(EXAMPLE_YAML),
                "--trials",
                "10",
                "--tolerance",
                "optics.aperture_diameter_m gaussian std_fraction=0.02",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Monte Carlo" in result.output
        assert "10 trials" in result.output

    @pytest.mark.level2
    def test_tolerance_no_tolerances(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "tolerance",
                str(EXAMPLE_YAML),
                "--trials",
                "5",
            ],
        )
        assert result.exit_code != 0
        assert "no tolerances" in result.output.lower()

    @pytest.mark.level2
    def test_tolerance_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "mc.json"
        result = runner.invoke(
            cli,
            [
                "tolerance",
                str(EXAMPLE_YAML),
                "--trials",
                "5",
                "--tolerance",
                "optics.transmission_scalar gaussian std_fraction=0.05",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["n_trials"] == 5


# ---------------------------------------------------------------------------
# radiant compare
# ---------------------------------------------------------------------------


class TestCompareCommand:
    @pytest.mark.level2
    def test_compare_same_config(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            [
                "compare",
                str(EXAMPLE_YAML),
                str(EXAMPLE_YAML),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Delta" in result.output
        # Same config → all deltas should be +0.0000
        assert "+0.0000" in result.output

    @pytest.mark.level2
    def test_compare_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "cmp.json"
        result = runner.invoke(
            cli,
            [
                "compare",
                str(EXAMPLE_YAML),
                str(EXAMPLE_YAML),
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "metrics" in data


# ---------------------------------------------------------------------------
# radiant schema
# ---------------------------------------------------------------------------


class TestSchemaCommand:
    @pytest.mark.level1
    def test_schema_text(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema"])
        assert result.exit_code == 0, result.output
        assert "Name" in result.output
        assert "optics.aperture_diameter_m" in result.output

    @pytest.mark.level1
    def test_schema_json(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]

    @pytest.mark.level1
    def test_schema_stage_filter(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--stage", "detector"])
        assert result.exit_code == 0, result.output
        assert "detector" in result.output
        # Should not contain optics params
        assert "optics.aperture" not in result.output

    @pytest.mark.level1
    def test_schema_unknown_stage(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--stage", "bogus"])
        assert result.exit_code == 0  # Not an error, just empty
        assert "No parameters found" in result.output


# ---------------------------------------------------------------------------
# radiant template
# ---------------------------------------------------------------------------


class TestTemplateCommand:
    @pytest.mark.level1
    def test_template_list(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "list"])
        assert result.exit_code == 0, result.output
        assert "mwir_leo_pushbroom" in result.output
        assert "vnir_aerial" in result.output
        assert "lwir_geo" in result.output
        assert "swir_leo" in result.output

    @pytest.mark.level1
    def test_template_show(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "show", "mwir_leo_pushbroom"])
        assert result.exit_code == 0, result.output
        assert "aperture_diameter_m" in result.output
        assert "0.3" in result.output

    @pytest.mark.level1
    def test_template_show_unknown(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "show", "nonexistent"])
        assert result.exit_code != 0
        assert "unknown template" in result.output.lower()

    @pytest.mark.level1
    def test_template_create(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "test.yaml"
        result = runner.invoke(
            cli,
            [
                "template",
                "create",
                "mwir_leo_pushbroom",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "aperture_diameter_m" in content


# ---------------------------------------------------------------------------
# radiant convert
# ---------------------------------------------------------------------------


class TestConvertCommand:
    @pytest.mark.level1
    def test_convert_um_to_m(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "18", "um", "m"])
        assert result.exit_code == 0, result.output
        assert "1.8e-05" in result.output

    @pytest.mark.level1
    def test_convert_deg_to_rad(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "45", "deg", "rad"])
        assert result.exit_code == 0, result.output
        assert "0.785" in result.output

    @pytest.mark.level1
    def test_convert_ms_to_s(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "5", "ms", "s"])
        assert result.exit_code == 0, result.output
        assert "0.005" in result.output

    @pytest.mark.level1
    def test_convert_unknown_unit(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "1", "parsec", "m"])
        assert result.exit_code != 0
        assert "no conversion" in result.output.lower()


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


class TestHelpText:
    @pytest.mark.level1
    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "RADIANT" in result.output

    @pytest.mark.level1
    def test_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    @pytest.mark.level1
    def test_validate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    @pytest.mark.level1
    def test_explain_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["explain", "--help"])
        assert result.exit_code == 0
        assert "param" in result.output.lower()

    @pytest.mark.level1
    def test_sweep_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["sweep", "--help"])
        assert result.exit_code == 0
        assert "--min" in result.output

    @pytest.mark.level1
    def test_tolerance_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["tolerance", "--help"])
        assert result.exit_code == 0
        assert "--trials" in result.output

    @pytest.mark.level1
    def test_compare_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["compare", "--help"])
        assert result.exit_code == 0

    @pytest.mark.level1
    def test_schema_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--help"])
        assert result.exit_code == 0
        assert "--stage" in result.output

    @pytest.mark.level1
    def test_template_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "--help"])
        assert result.exit_code == 0

    @pytest.mark.level1
    def test_convert_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_snr(output: str) -> float:
    """Extract the SNR value from CLI output."""
    for line in output.splitlines():
        if line.strip().startswith("SNR:"):
            return float(line.split(":")[1].strip())
    raise ValueError(f"SNR not found in output:\n{output}")


class TestElementSectionConfigs:
    """CU-153: run/validate accept optical_elements-bearing configs (Sensor.save output)."""

    @staticmethod
    def _element_config(tmp_path):
        from radiant.api import Sensor

        repo = Path(__file__).resolve()
        while not (repo / "pyproject.toml").exists():
            repo = repo.parent
        s = Sensor.from_yaml(repo / "examples" / "mwir_leo_minimal.yaml")
        s.set_optical_elements(
            [
                {
                    "name": "M1",
                    "transfer_mode": "REFLECTIVE",
                    "reflectance": 0.97,
                    "temperature_K": 293.0,
                    "diameter_m": 0.3,
                    "distance_to_fpa_m": 1.0,
                }
            ]
        )
        path = tmp_path / "with_elements.yaml"
        s.save(path)
        return path

    def test_run_executes_element_config(self, tmp_path) -> None:
        from click.testing import CliRunner

        from radiant.cli.run import run

        path = self._element_config(tmp_path)
        result = CliRunner().invoke(run, [str(path), "--quiet"])
        assert result.exit_code == 0, result.output
        assert "SNR" in result.output

    def test_validate_accepts_element_config(self, tmp_path) -> None:
        from click.testing import CliRunner

        from radiant.cli.validate import validate

        path = self._element_config(tmp_path)
        result = CliRunner().invoke(validate, [str(path)])
        assert result.exit_code == 0, result.output

    def test_validate_reports_bad_element_section(self, tmp_path) -> None:
        from click.testing import CliRunner

        from radiant.cli.validate import validate

        path = self._element_config(tmp_path)
        text = path.read_text(encoding="utf-8").replace(
            "transfer_mode: REFLECTIVE", "transfer_mode: SIDEWAYS"
        )
        path.write_text(text, encoding="utf-8")
        result = CliRunner().invoke(validate, [str(path)])
        assert result.exit_code != 0
        assert "optical_elements" in result.output


# ---------------------------------------------------------------------------
# Study config files (ADR-0010) — multi-config Phase 5
# ---------------------------------------------------------------------------


class TestRunStudyConfigFiles:
    """`radiant run study.yaml --configuration NAME` (ADR-0010, plan §5 Phase 5)."""

    @pytest.mark.level2
    def test_runs_the_named_configuration(self, runner: CliRunner, tmp_path: Path) -> None:
        """The named configuration evaluates, and the output says which one it was."""
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["run", str(study), "--configuration", "LWIR"])
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0] == "Configuration: LWIR"
        assert "SNR:" in result.output

    @pytest.mark.level2
    def test_each_configuration_gives_its_own_result(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The two band configurations are materialized separately, not shared."""
        study = _write_study(tmp_path)
        mwir = runner.invoke(cli, ["run", str(study), "--configuration", "MWIR"])
        lwir = runner.invoke(cli, ["run", str(study), "--configuration", "LWIR"])
        assert mwir.exit_code == 0 and lwir.exit_code == 0, mwir.output + lwir.output
        assert _extract_snr(mwir.output) != _extract_snr(lwir.output)

    @pytest.mark.level1
    def test_active_is_not_honored_implicitly(self, runner: CliRunner, tmp_path: Path) -> None:
        """`active: LWIR` is GUI state — it must not silently pick the configuration."""
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["run", str(study)])
        assert result.exit_code != 0
        assert "active" in result.output
        assert "--configuration" in result.output

    @pytest.mark.level1
    def test_unknown_configuration_names_the_available_ones(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["run", str(study), "--configuration", "SWIR"])
        assert result.exit_code != 0
        assert "'SWIR'" in result.output
        assert "MWIR" in result.output and "LWIR" in result.output

    @pytest.mark.level1
    def test_flag_on_a_plain_config_is_refused(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--configuration", "MWIR"])
        assert result.exit_code != 0
        assert "plain config file" in result.output

    @pytest.mark.level1
    def test_json_output_carries_the_configuration(self, runner: CliRunner, tmp_path: Path) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["run", str(study), "--configuration", "MWIR", "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["configuration"] == "MWIR"
        assert "snr" in data["metrics"]

    @pytest.mark.level1
    def test_csv_output_carries_the_configuration_column(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["run", str(study), "--configuration", "MWIR", "--format", "csv"]
        )
        assert result.exit_code == 0, result.output
        lines = result.output.strip().splitlines()
        assert lines[0] == "configuration,metric,value"
        assert all(line.startswith("MWIR,") for line in lines[1:])

    @pytest.mark.level1
    def test_plain_config_csv_shape_is_unchanged(self, runner: CliRunner) -> None:
        """The configuration column appears for studies only (no regression)."""
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--format", "csv"])
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0] == "metric,value"

    @pytest.mark.level1
    def test_output_and_provenance_files_name_the_configuration(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        out = tmp_path / "result.json"
        prov = tmp_path / "prov.json"
        result = runner.invoke(
            cli,
            [
                "run",
                str(study),
                "--configuration",
                "LWIR",
                "--output",
                str(out),
                "--provenance",
                str(prov),
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(out.read_text(encoding="utf-8"))["configuration"] == "LWIR"
        assert json.loads(prov.read_text(encoding="utf-8"))["configuration"] == "LWIR"

    @pytest.mark.level2
    def test_set_override_applies_to_the_materialized_configuration(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        base = runner.invoke(cli, ["run", str(study), "--configuration", "MWIR"])
        overridden = runner.invoke(
            cli,
            [
                "run",
                str(study),
                "--configuration",
                "MWIR",
                "--set",
                "optics.aperture_diameter_m=0.50",
            ],
        )
        assert base.exit_code == 0 and overridden.exit_code == 0, overridden.output
        assert _extract_snr(base.output) != _extract_snr(overridden.output)

    @pytest.mark.level1
    def test_unknown_set_parameter_is_actionable(self, runner: CliRunner, tmp_path: Path) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["run", str(study), "--configuration", "MWIR", "--set", "typo.nope=1"]
        )
        assert result.exit_code != 0
        assert "unknown parameter" in result.output.lower()

    @pytest.mark.level1
    def test_wavelength_span_flags_are_refused(self, runner: CliRunner, tmp_path: Path) -> None:
        """Each configuration spans its own band (D-F) — a CLI span would contradict it."""
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["run", str(study), "--configuration", "MWIR", "--wavelength-min", "3.0"]
        )
        assert result.exit_code != 0
        assert "--wavelength-min" in result.output

    @pytest.mark.level2
    def test_explicit_wavelength_points_override_the_configuration(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The flag's *default* must not overwrite the study's own point count."""
        study = _write_study(tmp_path)
        default_run = runner.invoke(cli, ["run", str(study), "--configuration", "LWIR"])
        coarse = runner.invoke(
            cli, ["run", str(study), "--configuration", "LWIR", "--wavelength-points", "25"]
        )
        assert default_run.exit_code == 0 and coarse.exit_code == 0, coarse.output
        # LWIR carries wavelength_points: 300; the unflagged run must use it,
        # so a 25-point run differs.
        assert _extract_snr(default_run.output) != _extract_snr(coarse.output)

    @pytest.mark.level1
    def test_a_broken_section_reports_the_loader_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Section violations surface as the api layer's actionable error."""
        study = _write_study(
            tmp_path,
            section=(
                "\nconfigurations:\n  names: [A, B]\n  parameters:\n"
                "    spectral_integration.filter_min_um: [3.95]\n"
            ),
        )
        result = runner.invoke(cli, ["run", str(study), "--configuration", "A"])
        assert result.exit_code != 0
        assert "filter_min_um" in result.output


class TestValidateStudyConfigFiles:
    """`radiant validate study.yaml` validates every configuration (validate_all)."""

    @staticmethod
    def _partly_broken(tmp_path: Path) -> Path:
        """A study whose second configuration over-constrains the f-number group."""
        return _write_study(
            tmp_path,
            strip_band=False,
            section=(
                "\nconfigurations:\n  names: [good, bad]\n  parameters:\n"
                "    optics.f_number: [4.0, 6.0]\n"
            ),
        )

    @pytest.mark.level1
    def test_one_failing_configuration_does_not_hide_the_others(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = self._partly_broken(tmp_path)
        result = runner.invoke(cli, ["validate", str(study)])
        assert result.exit_code != 0
        assert "good" in result.output and "ok" in result.output
        assert "ERROR" in result.output
        assert "1 failed" in result.output

    @pytest.mark.level1
    def test_shared_set_override_applies_to_the_base(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["validate", str(study), "--set", "optics.aperture_diameter_m=0.50"]
        )
        assert result.exit_code == 0, result.output
        assert "Study OK" in result.output

    @pytest.mark.level1
    def test_set_on_a_configured_parameter_is_refused(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """One value has no unambiguous target across N configurations (Rule 17)."""
        study = _write_study(tmp_path)
        result = runner.invoke(
            cli, ["validate", str(study), "--set", "spectral_integration.filter_min_um=4.0"]
        )
        assert result.exit_code != 0
        assert "configured parameter" in result.output

    @pytest.mark.level1
    def test_unknown_set_parameter_is_actionable(self, runner: CliRunner, tmp_path: Path) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["validate", str(study), "--set", "typo.nope=1"])
        assert result.exit_code != 0
        assert "unknown parameter" in result.output.lower()

    @pytest.mark.level1
    def test_configuration_count_and_configured_count_reported(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        study = _write_study(tmp_path)
        result = runner.invoke(cli, ["validate", str(study)])
        assert result.exit_code == 0, result.output
        assert "2 configuration(s), 2 configured parameter(s), 0 failed." in result.output
