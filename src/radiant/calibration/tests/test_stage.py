"""CalibrationStage Phase 0 behavior (Gap 120).

The scheme=none no-op contract (the plan §16 regression guarantee at stage
grain), evaluate-time validation of active schemes (Rule 16), and the
Phase 1 phase-gate error.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration._schema import ALL_PARAMETERS
from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
    is_calibration_config_incomplete,
)
from radiant.calibration.stage import CalibrationStage
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet


def _params(**overrides: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS))
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _state() -> ChainState:
    return ChainState(wavelength_um=np.linspace(8.0, 12.0, 5))


class TestSchemeNone:
    """scheme=none is a recorded no-op — the bit-identical guarantee."""

    def test_no_noise_terms_added(self) -> None:
        out = CalibrationStage().run(_state(), _params())
        assert out.noise_terms == ()

    def test_no_bias_terms_added(self) -> None:
        out = CalibrationStage().run(_state(), _params())
        assert out.bias_terms == ()

    def test_stage_output_records_model_off(self) -> None:
        out = CalibrationStage().run(_state(), _params())
        assert out.stage_outputs["calibration"]["scheme"] == "none"
        assert out.stage_outputs["calibration"]["enabled"] is False

    def test_input_state_not_mutated(self) -> None:
        state = _state()
        CalibrationStage().run(state, _params())
        assert state.stage_outputs == {}
        assert state.noise_terms == ()

    def test_frames_and_metrics_pass_through(self) -> None:
        state = _state()
        out = CalibrationStage().run(state, _params())
        assert out.frames == state.frames
        assert out.metrics == state.metrics
        assert out.mtf_terms == state.mtf_terms


class TestActiveSchemeValidation:
    """Rule 16: broken active configs are reported as themselves."""

    def test_one_point_without_cal_temp_is_incomplete(self) -> None:
        with pytest.raises(CalibrationConfigIncompleteError, match="cal_temp_low_K is unset"):
            CalibrationStage().run(_state(), _params(calibration__scheme="one_point"))

    def test_two_point_without_high_temp_is_incomplete(self) -> None:
        with pytest.raises(CalibrationConfigIncompleteError, match="cal_temp_high_K is unset"):
            CalibrationStage().run(
                _state(),
                _params(calibration__scheme="two_point", calibration__cal_temp_low_K=290.0),
            )

    def test_inverted_cal_temps_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="must exceed"):
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="two_point",
                    calibration__cal_temp_low_K=310.0,
                    calibration__cal_temp_high_K=290.0,
                ),
            )

    def test_equal_cal_temps_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="must exceed"):
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="two_point",
                    calibration__cal_temp_low_K=300.0,
                    calibration__cal_temp_high_K=300.0,
                ),
            )

    def test_incomplete_predicate_routes_structurally(self) -> None:
        try:
            CalibrationStage().run(_state(), _params(calibration__scheme="one_point"))
        except CalibrationValidationError as exc:
            assert is_calibration_config_incomplete(exc)
        else:  # pragma: no cover - the raise is the test
            pytest.fail("expected CalibrationConfigIncompleteError")

    def test_inverted_temps_are_not_routed_as_incomplete(self) -> None:
        try:
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="two_point",
                    calibration__cal_temp_low_K=310.0,
                    calibration__cal_temp_high_K=290.0,
                ),
            )
        except CalibrationValidationError as exc:
            assert not is_calibration_config_incomplete(exc)
        else:  # pragma: no cover - the raise is the test
            pytest.fail("expected CalibrationValidationError")


class TestPhaseGate:
    """A valid active config raises the actionable Phase 1 gate (Phase 0 only)."""

    def test_valid_two_point_raises_phase_gate(self) -> None:
        with pytest.raises(CalibrationConfigIncompleteError, match="Phase 1"):
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="two_point",
                    calibration__cal_temp_low_K=290.0,
                    calibration__cal_temp_high_K=310.0,
                ),
            )

    def test_valid_one_point_raises_phase_gate(self) -> None:
        with pytest.raises(CalibrationConfigIncompleteError, match="scheme = 'none'"):
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="one_point",
                    calibration__cal_temp_low_K=300.0,
                ),
            )
