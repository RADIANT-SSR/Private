"""CalibrationStage Phase 0 behavior (Gap 120).

The scheme=none no-op contract (the plan §16 regression guarantee at stage
grain), evaluate-time validation of active schemes (Rule 16), and the
Phase 1 phase-gate error.
"""

from __future__ import annotations

import numpy as np
import pytest
import pytest as _pytest

from radiant.calibration._schema import ALL_PARAMETERS
from radiant.calibration.cal_points import cal_point_signal_e
from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
    is_calibration_config_incomplete,
)
from radiant.calibration.stage import CalibrationStage
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.source._schema import ALL_PARAMETERS as SRC_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS


def _params(**overrides: object) -> ParameterSet:
    ps = ParameterSet(list(ALL_PARAMETERS) + list(SRC_PARAMS) + list(SI_PARAMS) + list(RO_PARAMS))
    ps.set("readout.full_well_capacity_e", 1.0e5)
    ps.set("spectral_integration.filter_min_um", 8.0)
    ps.set("spectral_integration.filter_max_um", 12.0)
    ps.set("spectral_integration.integration_time_s", 0.005)
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _evaluated_state(
    *,
    signal_e: float = 30000.0,
    ro_sigma: float = 100.0,
    well_e: float = 1.0e5,
    prnu_pct: float = 2.0,
    ds_dt: float = 500.0,
) -> ChainState:
    """Synthetic post-readout state: what the chain hands CalibrationStage."""
    s = _state()
    s = s.with_stage_output("readout", "signal_e_final", signal_e)
    s = s.with_stage_output("readout", "sigma_total_e", ro_sigma)
    s = s.with_stage_output("readout", "total_well_e", well_e)
    s = s.with_stage_output("detector", "signal_e", signal_e)
    s = s.with_stage_output("detector", "precal_prnu_pct", prnu_pct)
    s = s.with_stage_output("detector", "precal_dsnu_e_rms", 30.0)
    return s.with_stage_output("spectral_integration", "ds_dt_e_per_K", ds_dt)


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


class TestActiveDispatch:
    """Phase 2: a valid active scheme emits terms, biases, and totals."""

    _CAL = {
        "calibration__scheme": "two_point",
        "calibration__cal_temp_low_K": 290.0,
        "calibration__cal_temp_high_K": 310.0,
        "calibration__nonlinearity_pct": 1.0,
        "calibration__time_since_cal_s": 24.0,  # input unit: hour
        "calibration__gain_drift_frac_per_s": 0.1,  # input unit: %/hour
        "calibration__offset_drift_e_per_s": 3600.0,  # input unit: e-/hour
        "calibration__source_temp_uncertainty_K": 0.5,
        "calibration__source_emissivity_uncertainty": 0.005,
        "calibration__source_emissivity": 0.98,
        "calibration__gain_uncertainty_pct": 1.0,
    }

    def test_three_noise_terms_emitted(self) -> None:
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        names = [t.name for t in out.noise_terms]
        assert names == ["nuc_residual", "gain_drift", "offset_drift"]
        for term in out.noise_terms:
            assert term.contributes_to == ("spatial", "total")

    def test_nuc_matches_module_composition(self) -> None:
        """Wiring identity: the emitted term equals the Level-0 module chain."""
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        s1_expected = cal_point_signal_e(
            t_cal_K=290.0,
            scene_temp_K=300.0,
            scene_signal_e=30000.0,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert cal["s1_e"] == _pytest.approx(s1_expected, rel=1e-12)
        expected_nuc = 0.01 * abs((30000.0 - cal["s1_e"]) * (30000.0 - cal["s2_e"])) / 1.0e5
        assert cal["nuc_residual_e"] == _pytest.approx(expected_nuc, rel=1e-9)

    def test_drift_hand_values(self) -> None:
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        # 0.1 %/hour over 24 h on 30 000 e-: (0.001/3600)·86400·3e4 = 720 e-.
        assert cal["gain_drift_e"] == _pytest.approx(720.0, rel=1e-9)
        # 3600 e-/hour = 1 e-/s over 86 400 s = 86 400 e-.
        assert cal["offset_drift_e"] == _pytest.approx(86400.0, rel=1e-9)

    def test_published_total_is_rss_with_readout(self) -> None:
        import math as _math

        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        sigma_cal = _math.sqrt(
            cal["nuc_residual_e"] ** 2 + cal["gain_drift_e"] ** 2 + cal["offset_drift_e"] ** 2
        )
        assert cal["sigma_calibration_e"] == _pytest.approx(sigma_cal, rel=1e-12)
        assert cal["sigma_total_e"] == _pytest.approx(
            _math.sqrt(100.0**2 + sigma_cal**2), rel=1e-12
        )

    def test_bias_terms_emitted_and_rssed(self) -> None:
        import math as _math

        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        names = [t.name for t in out.bias_terms]
        assert names == ["source_temp", "source_emissivity", "gain"]
        rss = _math.sqrt(sum(t.value_frac**2 for t in out.bias_terms))
        assert out.stage_outputs["calibration"]["bias_total_frac"] == _pytest.approx(rss, rel=1e-12)

    def test_nedt_equivalent_published(self) -> None:
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        assert cal["calibration_nedt_K"] == _pytest.approx(
            cal["sigma_calibration_e"] / 500.0, rel=1e-12
        )

    def test_one_point_uses_gain_departure(self) -> None:
        overrides = {
            "calibration__scheme": "one_point",
            "calibration__cal_temp_low_K": 300.0,
        }
        out = CalibrationStage().run(_evaluated_state(), _params(**overrides))
        cal = out.stage_outputs["calibration"]
        # Cal point at the scene temperature: S1 == S, residual is exactly 0.
        assert cal["s1_e"] == _pytest.approx(30000.0, rel=1e-9)
        assert cal["nuc_residual_e"] == _pytest.approx(0.0, abs=1e-6)

    def test_missing_chain_signal_is_actionable(self) -> None:
        with pytest.raises(CalibrationValidationError, match="signal"):
            CalibrationStage().run(
                _state(),
                _params(
                    calibration__scheme="two_point",
                    calibration__cal_temp_low_K=290.0,
                    calibration__cal_temp_high_K=310.0,
                ),
            )

    def test_zero_config_active_scheme_emits_zero_terms(self) -> None:
        """Scheme on, every dispersion zero: terms exist with value 0 — the
        model is on but quiet, and sigma_total equals readout's."""
        overrides = {
            "calibration__scheme": "two_point",
            "calibration__cal_temp_low_K": 290.0,
            "calibration__cal_temp_high_K": 310.0,
        }
        out = CalibrationStage().run(_evaluated_state(prnu_pct=0.0), _params(**overrides))
        cal = out.stage_outputs["calibration"]
        assert cal["sigma_calibration_e"] == 0.0
        assert cal["sigma_total_e"] == _pytest.approx(100.0, rel=1e-12)
        assert out.bias_terms == ()
