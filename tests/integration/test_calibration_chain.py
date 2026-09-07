"""Full-chain contract tests for the calibration error model (Gap 120).

The two structural guarantees of ADR-0012, asserted on real chain runs:

1. **sqrt(N) exemption** — calibration residuals are appended after
   readout's TDI scaling, so their signal-relative size is invariant in
   TDI stage count while temporal noise averages down.
2. **Bias isolation** — bias terms change the radiometric-accuracy metric
   and nothing else: SNR and NEDT are bit-identical with the bias model
   on or off.

Plus the plan §16 regression contract (scheme=none is bit-identical) and
wiring identities against the Level-0 modules.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.io.config import load_config

YAML_PATH = Path(__file__).parents[2] / "examples" / "mwir_leo_minimal.yaml"

_CAL_INPUTS: dict[str, object] = {
    "calibration.scheme": "two_point",
    "calibration.cal_temp_low_K": 290.0,
    "calibration.cal_temp_high_K": 310.0,
    "calibration.nonlinearity_pct": 1.0,
    "calibration.time_since_cal_s": 24.0,  # hours (input unit)
    "calibration.gain_drift_frac_per_s": 0.05,  # %/hour (input unit)
    "calibration.offset_drift_e_per_s": 360.0,  # e-/hour (input unit)
    "detector.prnu_pct": 2.0,
}

_BIAS_INPUTS: dict[str, object] = {
    "calibration.source_temp_uncertainty_K": 0.5,
    "calibration.source_emissivity_uncertainty": 0.005,
    "calibration.source_emissivity": 0.98,
    "calibration.gain_uncertainty_pct": 1.0,
}


def _run(overrides: dict[str, object] | None = None):
    wl = np.linspace(3.5, 5.0, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(YAML_PATH, params)
    for name, value in (overrides or {}).items():
        params.set(name, value)
    params.resolve()
    return session.run(params)


@pytest.mark.level2
class TestSchemeNoneRegression:
    def test_explicit_none_is_bit_identical_to_default(self) -> None:
        base = _run()
        explicit = _run({"calibration.scheme": "none"})
        assert base.metrics == explicit.metrics  # exact — the plan §16 contract


@pytest.mark.level2
class TestActiveSchemeEndToEnd:
    def test_calibration_terms_in_final_budget(self) -> None:
        result = _run(_CAL_INPUTS)
        names = {t.name for t in result.noise_terms}
        assert {"nuc_residual", "gain_drift", "offset_drift"} <= names

    def test_snr_prefers_post_calibration_total(self) -> None:
        result = _run(_CAL_INPUTS)
        snr_result = result.stage_outputs["performance"]["snr_result"]
        cal_total = result.stage_outputs["calibration"]["sigma_total_e"]
        assert snr_result.noise_e == pytest.approx(cal_total, rel=1e-12)

    def test_calibration_floor_lowers_snr(self) -> None:
        base = _run()
        cal = _run(_CAL_INPUTS)
        assert cal.metrics["snr"] < base.metrics["snr"]

    def test_residuals_enter_imaging_regime(self) -> None:
        """detector.noise_regime='imaging' excludes pre-cal FPN as
        'calibrated out'; the residual is exactly what survives, so the
        calibration floor must be visible in the imaging-regime SNR."""
        base = _run({"detector.noise_regime": "imaging"})
        cal = _run({**_CAL_INPUTS, "detector.noise_regime": "imaging"})
        assert cal.metrics["snr"] < base.metrics["snr"]


@pytest.mark.level2
class TestSqrtNExemption:
    """ADR-0012 structural guarantee 1, on a real chain."""

    def test_calibration_ratio_invariant_temporal_ratio_drops(self) -> None:
        # Short integration keeps 16 TDI stages inside the well — the
        # exemption must be measured on an unsaturated chain.
        headroom = {"spectral_integration.integration_time_s": 0.0002}
        lo = _run({**_CAL_INPUTS, **headroom, "readout.n_tdi": 1})
        hi = _run({**_CAL_INPUTS, **headroom, "readout.n_tdi": 16})

        def _ratios(result) -> tuple[float, float]:
            signal = result.stage_outputs["readout"]["signal_e_final"]
            cal = result.stage_outputs["calibration"]["nuc_residual_e"]
            temporal = result.stage_outputs["readout"]["sigma_temporal_e"]
            return cal / signal, temporal / signal

        cal_lo, temp_lo = _ratios(lo)
        cal_hi, temp_hi = _ratios(hi)
        # Correlated: the calibration floor's signal-relative size does not
        # move with TDI stage count.
        assert cal_hi == pytest.approx(cal_lo, rel=1e-9)
        # Uncorrelated: the temporal ratio averages down (sqrt(16) = 4 for
        # pure shot; other terms scale differently, so assert a floor).
        assert temp_hi < temp_lo / 2.0


@pytest.mark.level2
class TestBiasIsolation:
    """ADR-0012 structural guarantee 2, on a real chain."""

    def test_bias_changes_accuracy_and_nothing_else(self) -> None:
        without = _run(_CAL_INPUTS)
        with_bias = _run({**_CAL_INPUTS, **_BIAS_INPUTS})

        assert with_bias.metrics["snr"] == without.metrics["snr"]  # exact
        if "nedt_K" in without.metrics:
            assert with_bias.metrics["nedt_K"] == without.metrics["nedt_K"]

        assert "radiometric_accuracy_pct" in with_bias.metrics
        assert "radiometric_accuracy_pct" not in without.metrics
        assert with_bias.metrics["radiometric_accuracy_pct"] > 0.0

    def test_accuracy_is_rss_of_sources(self) -> None:
        result = _run({**_CAL_INPUTS, **_BIAS_INPUTS})
        acc = result.stage_outputs["performance"]["radiometric_accuracy_result"]
        rss = math.sqrt(sum(f**2 for f in acc.per_source_frac.values()))
        assert acc.bias_frac == pytest.approx(rss, rel=1e-12)
        assert result.metrics["radiometric_accuracy_pct"] == pytest.approx(rss * 100.0, rel=1e-12)
        assert set(acc.per_source_frac) == {"source_temp", "source_emissivity", "gain"}

    def test_accuracy_in_kelvin_uses_thermal_derivative(self) -> None:
        result = _run({**_CAL_INPUTS, **_BIAS_INPUTS})
        acc = result.stage_outputs["performance"]["radiometric_accuracy_result"]
        signal = result.stage_outputs["readout"]["signal_e_final"]
        ds_dt = result.stage_outputs["spectral_integration"]["ds_dt_e_per_K"]
        assert acc.bias_K == pytest.approx(acc.bias_frac * signal / ds_dt, rel=1e-9)
        assert result.metrics["radiometric_accuracy_K"] == pytest.approx(acc.bias_K, rel=1e-12)


@pytest.mark.level2
class TestNoDoubleCounting:
    def test_precal_prnu_leaves_detector_budget(self) -> None:
        result = _run(_CAL_INPUTS)
        raw = result.stage_outputs["detector"]["noise_budget_raw"]
        assert raw.terms["prnu"] == 0.0
        assert raw.terms["dsnu"] == 0.0
        assert result.stage_outputs["detector"]["precal_prnu_pct"] == pytest.approx(2.0, rel=1e-9)
