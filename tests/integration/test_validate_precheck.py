"""`validate` must reject what `evaluate` rejects (CU-383).

The reported defect: ``radiant validate`` printed *"Study OK — 3
configuration(s), 0 failed"* for a study in which two configurations could not
run, because ``ReadoutStage``'s architecture over-specification check lived
inside ``run()``. These tests reconstruct that case and pin both halves — the
rejection, and the absence of a false rejection on a legal config.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from radiant import RadiantError, Sensor
from radiant.api.precheck import precheck_parameters, stage_validator_names
from radiant.cli.main import cli

_LEGAL = Path("examples/mwir_leo_minimal.yaml")


def _counting_sensor() -> Sensor:
    """The example switched to digital counting, legally.

    The example sets ``full_well_capacity_e`` explicitly, which is legitimate
    over-specification under ``digital_counting`` (the effective well is
    2^counter_bits x count_packet_e), so it has to be released first. That the
    precheck catches it when it is not released is the validator working.
    """
    sensor = Sensor.from_yaml(str(_LEGAL))
    sensor.reset("readout.full_well_capacity_e")
    sensor.set("readout.architecture", "digital_counting")
    sensor.set("readout.count_packet_e", 8000.0)
    return sensor


class TestPrecheckAgreesWithEvaluate:
    """The property that was violated: validate and evaluate must not disagree."""

    def test_updown_params_under_mode_up_are_rejected(self) -> None:
        """The reviewer's exact case."""
        sensor = _counting_sensor()
        sensor.set("readout.counting_mode", "up")
        sensor.set("readout.reference_integration_s", 1.0e-3)
        sensor.set("readout.reference_source", "internal")

        # evaluate rejects it ...
        with pytest.raises(RadiantError) as from_evaluate:
            sensor.evaluate()
        # ... and so must the pre-chain check, which is the whole point.
        with pytest.raises(RadiantError) as from_precheck:
            precheck_parameters(sensor._params)
        assert "reference" in str(from_precheck.value)
        assert type(from_precheck.value) is type(from_evaluate.value)

    def test_counting_params_under_analog_well_are_rejected(self) -> None:
        sensor = Sensor.from_yaml(str(_LEGAL))
        sensor.set("readout.architecture", "analog_well")
        sensor.set("readout.count_packet_e", 8000.0)
        with pytest.raises(RadiantError):
            precheck_parameters(sensor._params)

    def test_a_legal_config_passes(self) -> None:
        """No false positives: the shipped example must precheck clean."""
        sensor = Sensor.from_yaml(str(_LEGAL))
        sensor.get("detector.qe_value")  # force resolution
        precheck_parameters(sensor._params)  # must not raise

    def test_a_legal_counting_config_passes(self) -> None:
        sensor = _counting_sensor()
        sensor.get("detector.qe_value")
        precheck_parameters(sensor._params)

    def test_an_explicit_analog_well_under_counting_is_rejected(self) -> None:
        """The example's own full_well_capacity_e over-specifies a counting readout."""
        sensor = Sensor.from_yaml(str(_LEGAL))
        sensor.set("readout.architecture", "digital_counting")
        sensor.set("readout.count_packet_e", 8000.0)
        with pytest.raises(RadiantError, match="full_well_capacity_e"):
            precheck_parameters(sensor._params)


class TestCliValidateRejects:
    """End to end through the command that reported the false pass."""

    def test_validate_fails_on_an_overspecified_config(self, tmp_path: Path) -> None:
        # Start from the shipped example so every required parameter is set,
        # then add only the over-specification under test.
        config = tmp_path / "bad.yaml"
        config.write_text(
            _LEGAL.read_text(encoding="utf-8") + "\nreadout:\n"
            "  architecture: digital_counting\n"
            "  count_packet_e: 8000.0\n"
            "  counting_mode: up\n"
            "  reference_integration_s: 0.001\n",
            encoding="utf-8",
        )
        result = CliRunner().invoke(cli, ["validate", str(config)])
        assert result.exit_code == 1, result.output
        assert "Validation failed" in result.output
        assert "reference" in result.output

    def test_validate_passes_the_shipped_example(self) -> None:
        result = CliRunner().invoke(cli, ["validate", str(_LEGAL)])
        assert result.exit_code == 0, result.output
        assert "Config OK" in result.output


class TestPrecheckCoverage:
    """Which stages are covered is a fact the audit recorded; pin it."""

    def test_covers_readout_and_calibration(self) -> None:
        assert set(stage_validator_names()) == {"readout", "calibration"}

    def test_optics_psf_check_is_deliberately_absent(self) -> None:
        """It compares against the computed PSF, so it cannot run pre-chain.

        Pinned so that a future reader finds the reason rather than assuming an
        oversight — and so that adding a params-only optics check updates this.
        """
        assert "optics" not in stage_validator_names()
