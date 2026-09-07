"""Gap 120 D2 handoff (ratified 2026-09-06) — no double counting.

Under an active calibration scheme the detector emits its pre-correction
PRNU/DSNU dispersions as stage outputs instead of noise-budget terms; under
``scheme = "none"`` (or a ParameterSet with no calibration namespace at
all — every pre-Gap-120 unit fixture) the budget is exactly today's.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration._schema import ALL_PARAMETERS as CAL_PARAMS
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.detector.stage import DetectorStage
from radiant.readout._schema import ALL_PARAMETERS as RO_PARAMS
from radiant.spectral_integration._schema import ALL_PARAMETERS as SI_PARAMS

_SIGNAL_E = 10000.0


def _state() -> ChainState:
    wl = np.linspace(8.0, 12.0, 5)
    state = ChainState(wavelength_um=wl)
    state = state.with_frame(
        RadiometricFrame(
            name="photoelectrons", wavelength_um=wl, in_band_value=_SIGNAL_E, in_band_unit="e-"
        )
    )
    return state.with_stage_output("spectral_integration", "signal_e", _SIGNAL_E)


def _params(*, with_cal_namespace: bool = True, **overrides: object) -> ParameterSet:
    schema = list(DET_PARAMS) + list(SI_PARAMS) + list(RO_PARAMS)
    if with_cal_namespace:
        schema += list(CAL_PARAMS)
    ps = ParameterSet(schema)
    ps.set("detector.qe_value", 0.7)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.dark_rate_e_per_s", 100.0)
    ps.set("spectral_integration.integration_time_s", 0.005)
    ps.set("spectral_integration.filter_min_um", 8.0)
    ps.set("spectral_integration.filter_max_um", 12.0)
    ps.set("detector.prnu_pct", 2.0)
    ps.set("detector.dsnu_e_rms", 30.0)
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


def _budget_terms(params: ParameterSet) -> tuple[dict[str, float], ChainState]:
    out = DetectorStage().run(_state(), params)
    return dict(out.stage_outputs["detector"]["noise_budget_raw"].terms), out


class TestSchemeNoneKeepsTodaysBudget:
    def test_prnu_dsnu_live_in_budget(self) -> None:
        terms, out = _budget_terms(_params())
        assert terms["prnu"] == pytest.approx(0.02 * _SIGNAL_E, rel=1e-9)  # 200 e-
        assert terms["dsnu"] == pytest.approx(30.0, rel=1e-9)
        assert "precal_prnu_pct" not in out.stage_outputs["detector"]

    def test_no_calibration_namespace_means_none(self) -> None:
        """Every pre-Gap-120 fixture (no calibration params) is untouched."""
        terms, out = _budget_terms(_params(with_cal_namespace=False))
        assert terms["prnu"] == pytest.approx(0.02 * _SIGNAL_E, rel=1e-9)
        assert "precal_prnu_pct" not in out.stage_outputs["detector"]


class TestActiveSchemeHandsOff:
    def test_two_point_suppresses_and_stashes(self) -> None:
        terms, out = _budget_terms(
            _params(
                calibration__scheme="two_point",
                calibration__cal_temp_low_K=290.0,
                calibration__cal_temp_high_K=310.0,
            )
        )
        assert terms["prnu"] == 0.0
        assert terms["dsnu"] == 0.0
        det = out.stage_outputs["detector"]
        assert det["precal_prnu_pct"] == pytest.approx(2.0, rel=1e-9)
        assert det["precal_dsnu_e_rms"] == pytest.approx(30.0, rel=1e-9)

    def test_one_point_suppresses_too(self) -> None:
        terms, out = _budget_terms(
            _params(calibration__scheme="one_point", calibration__cal_temp_low_K=300.0)
        )
        assert terms["prnu"] == 0.0
        assert terms["dsnu"] == 0.0
        assert out.stage_outputs["detector"]["precal_prnu_pct"] == pytest.approx(2.0, rel=1e-9)

    def test_rest_of_budget_unchanged_by_scheme(self) -> None:
        """Suppression touches exactly prnu/dsnu — every other term identical."""
        base, _ = _budget_terms(_params())
        active, _ = _budget_terms(
            _params(
                calibration__scheme="two_point",
                calibration__cal_temp_low_K=290.0,
                calibration__cal_temp_high_K=310.0,
            )
        )
        for name in base:
            if name in ("prnu", "dsnu"):
                continue
            assert active[name] == pytest.approx(base[name], rel=1e-12), name
