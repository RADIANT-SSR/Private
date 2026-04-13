"""Tests for the RADIANT CLI.

Uses Click's CliRunner for isolated invocation without subprocesses.
"""

from __future__ import annotations

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
        # Larger aperture → higher SNR.
        snr1 = _extract_snr(r1.output)
        snr2 = _extract_snr(r2.output)
        assert snr2 > snr1

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
        # Error may say "required parameter" or "could not be resolved" depending
        # on which unset parameter is hit first.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_snr(output: str) -> float:
    """Extract the SNR value from CLI output."""
    for line in output.splitlines():
        if line.strip().startswith("SNR:"):
            return float(line.split(":")[1].strip())
    raise ValueError(f"SNR not found in output:\n{output}")
