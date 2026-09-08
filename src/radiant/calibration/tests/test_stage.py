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

    def test_four_noise_terms_emitted(self) -> None:
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        names = [t.name for t in out.noise_terms]
        assert names == ["nuc_residual", "cal_source_uniformity", "gain_drift", "offset_drift"]
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


class TestReflectiveSceneGuard:
    """CU-346 (owner-ratified 2026-09-07): a pure-reflective scene under an
    active scheme runs, but loudly — the Planck cal-point anchor describes
    none of a solar-reflective signal, so the stage warns and publishes a
    note instead of silently emitting stand-in residuals."""

    @staticmethod
    def _t2_target() -> object:
        import warnings as _w

        from radiant.core.descriptors import T2Reflective
        from radiant.core.reflectance import ScalarLambertianReflectance
        from radiant.core.spectral import SpectralData

        rho = ScalarLambertianReflectance(
            reflectance=SpectralData(
                wavelength_um=np.linspace(0.5, 0.85, 5),
                values=np.full(5, 0.3),
                name="rho",
                unit="",
                source="test",
            )
        )
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)  # MWIR-overlap best-effort check
            return T2Reflective(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                rho=rho,
            )

    def _reflective_state(self) -> ChainState:
        return _evaluated_state().with_stage_output("source", "target", self._t2_target())

    def test_active_scheme_on_t2_warns_and_publishes_note(self) -> None:
        state = self._reflective_state()
        with pytest.warns(UserWarning, match="CU-346"):
            out = CalibrationStage().run(
                state, _params(calibration__scheme="one_point", calibration__cal_temp_low_K=290.0)
            )
        note = out.stage_outputs["calibration"]["reflective_scene_cal_note"]
        assert "stand-in" in note and "Gap 122" in note
        # The run still completes: the residual terms are emitted as before.
        assert out.stage_outputs["calibration"]["enabled"] is not False

    def test_scheme_none_on_t2_stays_silent(self) -> None:
        state = self._reflective_state()
        with warnings_none():
            out = CalibrationStage().run(state, _params())
        assert "reflective_scene_cal_note" not in out.stage_outputs["calibration"]

    def test_thermal_descriptor_on_a_solar_band_warns_too(self) -> None:
        """The scenario-1.4 door: T1Thermal at 300 K on a VNIR band — the
        declared temperature emits ~1e-22 of its photons in-band, so the
        guard fires on the band-thermal-fraction test, no descriptor check
        needed (the harness state carries no descriptor at all)."""
        with pytest.warns(UserWarning, match="CU-346"):
            out = CalibrationStage().run(
                _evaluated_state(),
                _params(
                    calibration__scheme="one_point",
                    calibration__cal_temp_low_K=290.0,
                    spectral_integration__filter_min_um=0.5,
                    spectral_integration__filter_max_um=0.85,
                ),
            )
        assert "reflective_scene_cal_note" in out.stage_outputs["calibration"]

    def test_thermal_scene_stays_silent(self) -> None:
        # The synthetic harness state carries no source descriptor at all —
        # the guard must not fire on absence, and not on thermal scenes.
        with warnings_none():
            out = CalibrationStage().run(
                _evaluated_state(),
                _params(calibration__scheme="one_point", calibration__cal_temp_low_K=290.0),
            )
        assert "reflective_scene_cal_note" not in out.stage_outputs["calibration"]


class warnings_none:
    """Context asserting no UserWarning escapes the block."""

    def __enter__(self) -> warnings_none:
        import warnings as _w

        self._cm = _w.catch_warnings(record=True)
        self._records = self._cm.__enter__()
        import warnings as _w2

        _w2.simplefilter("always")
        return self

    def __exit__(self, *exc: object) -> None:
        self._cm.__exit__(*exc)
        user = [r for r in self._records if issubclass(r.category, UserWarning)]
        assert not user, f"unexpected UserWarning(s): {[str(r.message) for r in user]}"


class TestSourceUniformityDispatch:
    """Gap 122 item 1: the uniformity term through the stage."""

    _CAL = {
        "calibration__scheme": "two_point",
        "calibration__cal_temp_low_K": 290.0,
        "calibration__cal_temp_high_K": 310.0,
        "calibration__source_uniformity_K": 0.05,
    }

    def test_wiring_matches_module_composition(self) -> None:
        from radiant.calibration.cal_points import cal_point_ds_dt_e_per_K
        from radiant.calibration.source_uniformity import two_point_uniformity_residual_e

        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        kw = {
            "scene_temp_K": 300.0,
            "scene_signal_e": 30000.0,
            "lam_min_um": 8.0,
            "lam_max_um": 12.0,
        }
        expected = two_point_uniformity_residual_e(
            signal_e=30000.0,
            s1_e=cal["s1_e"],
            s2_e=cal["s2_e"],
            delta_t_unif_K=0.05,
            ds_dt_cal1_e_per_K=cal_point_ds_dt_e_per_K(t_cal_K=290.0, **kw),
            ds_dt_cal2_e_per_K=cal_point_ds_dt_e_per_K(t_cal_K=310.0, **kw),
        )
        assert cal["cal_source_uniformity_e"] == pytest.approx(expected, rel=1e-12)
        assert expected > 0.0

    def test_nonzero_at_the_cal_point(self) -> None:
        """The item-1 claim: at S = S1 the NUC parabola vanishes but the
        uniformity imprint does not — the residual floor at the cal point."""
        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        s1 = cal["s1_e"]
        out_at_s1 = CalibrationStage().run(_evaluated_state(signal_e=s1), _params(**self._CAL))
        cal_at_s1 = out_at_s1.stage_outputs["calibration"]
        assert cal_at_s1["nuc_residual_e"] == pytest.approx(0.0, abs=1e-9)
        assert cal_at_s1["cal_source_uniformity_e"] > 0.0

    def test_default_zero_is_bit_identical_off(self) -> None:
        base = {k: v for k, v in self._CAL.items() if "uniformity" not in k}
        out = CalibrationStage().run(_evaluated_state(), _params(**base))
        cal = out.stage_outputs["calibration"]
        assert cal["cal_source_uniformity_e"] == 0.0
        term = next(t for t in out.noise_terms if t.name == "cal_source_uniformity")
        assert term.value_e == 0.0

    def test_enters_the_calibration_total(self) -> None:
        base = {k: v for k, v in self._CAL.items() if "uniformity" not in k}
        off = CalibrationStage().run(_evaluated_state(), _params(**base))
        on = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        assert (
            on.stage_outputs["calibration"]["sigma_calibration_e"]
            > off.stage_outputs["calibration"]["sigma_calibration_e"]
        )


class TestThreePointDispatch:
    """Gap 122 item 2: the three_point scheme through the stage."""

    _CAL = {
        "calibration__scheme": "three_point",
        "calibration__cal_temp_low_K": 285.0,
        "calibration__cal_temp_mid_K": 300.0,
        "calibration__cal_temp_high_K": 315.0,
        "calibration__nonlinearity_pct": 1.0,
    }

    def test_wiring_matches_module_composition(self) -> None:
        from radiant.calibration.nuc_residual import three_point_residual_e

        out = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        cal = out.stage_outputs["calibration"]
        expected = three_point_residual_e(
            signal_e=30000.0,
            s1_e=cal["s1_e"],
            s2_e=cal["s2_e"],
            s3_e=cal["s3_e"],
            nonlinearity_frac=0.01,
            full_well_e=1.0e5,
        )
        assert cal["nuc_residual_e"] == pytest.approx(expected, rel=1e-12)

    def test_shrinks_the_two_point_residual_on_the_same_span(self) -> None:
        three = CalibrationStage().run(_evaluated_state(), _params(**self._CAL))
        two = CalibrationStage().run(
            _evaluated_state(),
            _params(
                calibration__scheme="two_point",
                calibration__cal_temp_low_K=285.0,
                calibration__cal_temp_high_K=315.0,
                calibration__nonlinearity_pct=1.0,
            ),
        )
        assert (
            three.stage_outputs["calibration"]["nuc_residual_e"]
            < two.stage_outputs["calibration"]["nuc_residual_e"]
        )

    def test_missing_mid_is_incomplete(self) -> None:
        cfg = {k: v for k, v in self._CAL.items() if "mid" not in k}
        with pytest.raises(CalibrationConfigIncompleteError, match="cal_temp_mid_K is unset"):
            CalibrationStage().run(_evaluated_state(), _params(**cfg))

    def test_unordered_mid_rejected(self) -> None:
        cfg = {**self._CAL, "calibration__cal_temp_mid_K": 320.0}
        with pytest.raises(CalibrationValidationError, match="strictly increasing"):
            CalibrationStage().run(_evaluated_state(), _params(**cfg))

    def test_uniformity_composes_piecewise(self) -> None:
        out = CalibrationStage().run(
            _evaluated_state(),
            _params(**self._CAL, calibration__source_uniformity_K=0.05),
        )
        cal = out.stage_outputs["calibration"]
        assert cal["cal_source_uniformity_e"] > 0.0
