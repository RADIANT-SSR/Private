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


# ---------------------------------------------------------------------------
# radiant run
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_run_example(self, runner: CliRunner) -> None:
        """Running the example YAML produces SNR output."""
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        assert result.exit_code == 0, result.output
        assert "SNR:" in result.output
        assert "Signal:" in result.output

    def test_run_shows_noise_terms(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        assert result.exit_code == 0
        assert "shot" in result.output
        assert "read" in result.output
        assert "dark_shot" in result.output
        assert "quantization" in result.output

    def test_run_set_override(self, runner: CliRunner) -> None:
        """--set changes the result."""
        r1 = runner.invoke(cli, ["run", str(EXAMPLE_YAML)])
        r2 = runner.invoke(cli, [
            "run", str(EXAMPLE_YAML),
            "--set", "optics.aperture_diameter_m=0.50",
        ])
        assert r1.exit_code == 0
        assert r2.exit_code == 0
        # Overriding a parameter changes the metric.
        snr1 = _extract_snr(r1.output)
        snr2 = _extract_snr(r2.output)
        assert snr2 != snr1

    def test_run_set_unknown_param(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "run", str(EXAMPLE_YAML),
            "--set", "typo.nonexistent=42",
        ])
        assert result.exit_code != 0
        assert "unknown parameter" in result.output.lower()

    def test_run_set_bad_format(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "run", str(EXAMPLE_YAML),
            "--set", "no_equals_sign",
        ])
        assert result.exit_code != 0

    def test_run_file_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", "/tmp/does_not_exist_xyz.yaml"])
        assert result.exit_code != 0

    def test_run_invalid_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml", encoding="utf-8")
        result = runner.invoke(cli, ["run", str(bad)])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    def test_run_json_format(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "metrics" in data
        assert "snr" in data["metrics"]

    def test_run_csv_format(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--format", "csv"])
        assert result.exit_code == 0, result.output
        assert "metric,value" in result.output
        assert "snr," in result.output

    def test_run_quiet(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", str(EXAMPLE_YAML), "--quiet"])
        assert result.exit_code == 0, result.output
        assert "SNR:" in result.output
        # Quiet suppresses noise term details
        assert "Signal:" not in result.output

    def test_run_output_file(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        result = runner.invoke(cli, [
            "run", str(EXAMPLE_YAML), "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        data = json.loads(out.read_text())
        assert "metrics" in data

    def test_run_provenance_file(self, runner: CliRunner, tmp_path: Path) -> None:
        prov = tmp_path / "provenance.json"
        result = runner.invoke(cli, [
            "run", str(EXAMPLE_YAML), "--provenance", str(prov),
        ])
        assert result.exit_code == 0, result.output
        assert prov.exists()
        data = json.loads(prov.read_text())
        assert "parameters" in data


# ---------------------------------------------------------------------------
# radiant validate
# ---------------------------------------------------------------------------


class TestValidateCommand:
    def test_validate_ok(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", str(EXAMPLE_YAML)])
        assert result.exit_code == 0, result.output
        assert "Config OK" in result.output

    def test_validate_file_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", "/tmp/does_not_exist_xyz.yaml"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_validate_invalid_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml", encoding="utf-8")
        result = runner.invoke(cli, ["validate", str(bad)])
        assert result.exit_code != 0

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

    def test_validate_set_override(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "validate", str(EXAMPLE_YAML),
            "--set", "optics.aperture_diameter_m=0.50",
        ])
        assert result.exit_code == 0
        assert "Config OK" in result.output


# ---------------------------------------------------------------------------
# radiant explain
# ---------------------------------------------------------------------------


class TestExplainCommand:
    def test_explain_derived_param(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "explain", str(EXAMPLE_YAML), "optics.f_number",
        ])
        assert result.exit_code == 0, result.output
        assert "f_number" in result.output
        assert "4.0" in result.output

    def test_explain_user_set_param(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "explain", str(EXAMPLE_YAML), "optics.aperture_diameter_m",
        ])
        assert result.exit_code == 0, result.output
        assert "0.3" in result.output

    def test_explain_with_override(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "explain", str(EXAMPLE_YAML), "optics.aperture_diameter_m",
            "--set", "optics.aperture_diameter_m=0.50",
        ])
        assert result.exit_code == 0, result.output
        assert "0.5" in result.output

    def test_explain_unknown_param(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "explain", str(EXAMPLE_YAML), "bogus.param",
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# radiant sweep
# ---------------------------------------------------------------------------


class TestSweepCommand:
    def test_sweep_basic(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "sweep", str(EXAMPLE_YAML), "optics.aperture_diameter_m",
            "--min", "0.20", "--max", "0.40", "--steps", "3",
        ])
        assert result.exit_code == 0, result.output
        assert "snr" in result.output.lower()
        # Should have 3 rows + header + separator = 5 lines minimum
        lines = [line for line in result.output.strip().splitlines() if line.strip()]
        assert len(lines) >= 5

    def test_sweep_output_csv(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "sweep.csv"
        result = runner.invoke(cli, [
            "sweep", str(EXAMPLE_YAML), "optics.aperture_diameter_m",
            "--min", "0.20", "--max", "0.30", "--steps", "2",
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text()
        assert "value,snr" in content

    def test_sweep_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "sweep.json"
        result = runner.invoke(cli, [
            "sweep", str(EXAMPLE_YAML), "optics.aperture_diameter_m",
            "--min", "0.20", "--max", "0.30", "--steps", "2",
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text())
        assert "values" in data
        assert "metric_values" in data


# ---------------------------------------------------------------------------
# radiant tolerance
# ---------------------------------------------------------------------------


class TestToleranceCommand:
    def test_tolerance_basic(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "tolerance", str(EXAMPLE_YAML), "--trials", "10",
            "--tolerance", "optics.aperture_diameter_m gaussian std_fraction=0.02",
        ])
        assert result.exit_code == 0, result.output
        assert "Monte Carlo" in result.output
        assert "10 trials" in result.output

    def test_tolerance_no_tolerances(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "tolerance", str(EXAMPLE_YAML), "--trials", "5",
        ])
        assert result.exit_code != 0
        assert "no tolerances" in result.output.lower()

    def test_tolerance_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "mc.json"
        result = runner.invoke(cli, [
            "tolerance", str(EXAMPLE_YAML), "--trials", "5",
            "--tolerance", "optics.transmission_scalar gaussian std_fraction=0.05",
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text())
        assert data["n_trials"] == 5


# ---------------------------------------------------------------------------
# radiant compare
# ---------------------------------------------------------------------------


class TestCompareCommand:
    def test_compare_same_config(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [
            "compare", str(EXAMPLE_YAML), str(EXAMPLE_YAML),
        ])
        assert result.exit_code == 0, result.output
        assert "Delta" in result.output
        # Same config → all deltas should be +0.0000
        assert "+0.0000" in result.output

    def test_compare_output_json(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "cmp.json"
        result = runner.invoke(cli, [
            "compare", str(EXAMPLE_YAML), str(EXAMPLE_YAML),
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text())
        assert "metrics" in data


# ---------------------------------------------------------------------------
# radiant schema
# ---------------------------------------------------------------------------


class TestSchemaCommand:
    def test_schema_text(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema"])
        assert result.exit_code == 0, result.output
        assert "Name" in result.output
        assert "optics.aperture_diameter_m" in result.output

    def test_schema_json(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]

    def test_schema_stage_filter(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--stage", "detector"])
        assert result.exit_code == 0, result.output
        assert "detector" in result.output
        # Should not contain optics params
        assert "optics.aperture" not in result.output

    def test_schema_unknown_stage(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--stage", "bogus"])
        assert result.exit_code == 0  # Not an error, just empty
        assert "No parameters found" in result.output


# ---------------------------------------------------------------------------
# radiant template
# ---------------------------------------------------------------------------


class TestTemplateCommand:
    def test_template_list(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "list"])
        assert result.exit_code == 0, result.output
        assert "mwir_leo_pushbroom" in result.output
        assert "vnir_aerial" in result.output
        assert "lwir_geo" in result.output
        assert "swir_leo" in result.output

    def test_template_show(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "show", "mwir_leo_pushbroom"])
        assert result.exit_code == 0, result.output
        assert "aperture_diameter_m" in result.output
        assert "0.3" in result.output

    def test_template_show_unknown(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "show", "nonexistent"])
        assert result.exit_code != 0
        assert "unknown template" in result.output.lower()

    def test_template_create(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "test.yaml"
        result = runner.invoke(cli, [
            "template", "create", "mwir_leo_pushbroom",
            "--output", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text()
        assert "aperture_diameter_m" in content


# ---------------------------------------------------------------------------
# radiant convert
# ---------------------------------------------------------------------------


class TestConvertCommand:
    def test_convert_um_to_m(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "18", "um", "m"])
        assert result.exit_code == 0, result.output
        assert "1.8e-05" in result.output

    def test_convert_deg_to_rad(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "45", "deg", "rad"])
        assert result.exit_code == 0, result.output
        assert "0.785" in result.output

    def test_convert_ms_to_s(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "5", "ms", "s"])
        assert result.exit_code == 0, result.output
        assert "0.005" in result.output

    def test_convert_unknown_unit(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["convert", "1", "parsec", "m"])
        assert result.exit_code != 0
        assert "no conversion" in result.output.lower()


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "RADIANT" in result.output

    def test_run_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_validate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_explain_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["explain", "--help"])
        assert result.exit_code == 0
        assert "param" in result.output.lower()

    def test_sweep_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["sweep", "--help"])
        assert result.exit_code == 0
        assert "--min" in result.output

    def test_tolerance_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["tolerance", "--help"])
        assert result.exit_code == 0
        assert "--trials" in result.output

    def test_compare_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["compare", "--help"])
        assert result.exit_code == 0

    def test_schema_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["schema", "--help"])
        assert result.exit_code == 0
        assert "--stage" in result.output

    def test_template_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["template", "--help"])
        assert result.exit_code == 0

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
