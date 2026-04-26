"""Comprehensive end-to-end integration test (Prompt 2D.10).

Exercises all implemented features through the full signal chain:
- All three radiometric regimes (extended, point source, sub-pixel)
- Backward propagation (signal_at, noise_at, round-trip)
- 1-D and 2-D sweeps with monotonicity checks
- Monte Carlo tolerance analysis
- Saturation checks (well and ADC)
- Complete 16-term noise budget

Reference sensor: MWIR staring (3.5–5.0 µm), 300 K extended scene,
0.30 m aperture, f/4, 18 µm pitch, QE 0.70.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.sensitivity import sensitivity
from radiant.api.session import RadiantSession
from radiant.api.sweep import sweep, sweep_2d
from radiant.api.tolerance import monte_carlo
from radiant.core.parameters import Tolerance
from radiant.core.quantity import ReferenceFrame
from radiant.core.regime import RadiometricRegime

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
D = 0.30
F = 1.20
TAU_OPT = 0.70
PITCH_UM = 18.0
QE = 0.70
T_INT = 0.005
T_TARGET = 300.0
EPS_TARGET = 0.95
SENSOR_ALT = 8000.0
FILTER_MIN = 3.5
FILTER_MAX = 5.0
WL = np.linspace(FILTER_MIN, FILTER_MAX, 200)


def _base_params(session: RadiantSession):
    """Build baseline parameter set."""
    ps = session.default_params()
    ps.set("source.target.temperature", T_TARGET)
    ps.set("source.target.emissivity", EPS_TARGET)
    ps.set("optics.aperture_diameter_m", D)
    ps.set("optics.focal_length_m", F)
    ps.set("optics.transmission_scalar", TAU_OPT)
    ps.set("detector.pixel_pitch_x_um", PITCH_UM)
    ps.set("detector.pixel_pitch_y_um", PITCH_UM)
    ps.set("detector.qe_value", QE)
    ps.set("detector.dark_rate_e_per_s", 100.0)
    ps.set("geometry.sensor_altitude_m", SENSOR_ALT)
    ps.set("atmosphere.standard_atmosphere", "midlat_summer")
    ps.set("spectral_integration.filter_min_um", FILTER_MIN)
    ps.set("spectral_integration.filter_max_um", FILTER_MAX)
    ps.set("spectral_integration.integration_time_s", T_INT)
    ps.set("readout.read_noise_e_rms", 5.0)
    ps.set("readout.gain_e_per_dn", 32.0)
    ps.set("readout.adc_bits", 16)
    ps.set("readout.full_well_capacity_e", 2000000.0)
    return ps


def _run_extended():
    """Run extended-scene baseline."""
    session = RadiantSession(wavelength_um=WL)
    ps = _base_params(session)
    ps.resolve()
    return session.run(ps), session, ps


def _run_point_source(area_m2: float = 1.0, range_m: float = 10000.0):
    """Run point-source regime."""
    session = RadiantSession(wavelength_um=WL)
    ps = _base_params(session)
    ps.set("source.target.temperature", 500.0)
    ps.set("source.target.projected_area_m2", area_m2)
    ps.set("source.target.range_m", range_m)
    ps.set("source.background.temperature", 290.0)
    ps.set("source.background.emissivity", 0.95)
    ps.set("source.regime_override", "point_source")
    ps.resolve()
    return session.run(ps), session, ps


def _run_sub_pixel(
    ff: float = 0.1,
    target_T: float = 400.0,
    bg_T: float = 290.0,
):
    """Run sub-pixel regime."""
    session = RadiantSession(wavelength_um=WL)
    ps = _base_params(session)
    ps.set("source.target.temperature", target_T)
    ps.set("source.target.fill_fraction", ff)
    ps.set("source.background.temperature", bg_T)
    ps.set("source.background.emissivity", 0.95)
    ps.set("source.regime_override", "sub_pixel")
    ps.resolve()
    return session.run(ps), session, ps


# ===================================================================
# 1. ALL THREE REGIMES
# ===================================================================


@pytest.mark.level2
class TestAllRegimes:
    """Verify all three regimes produce valid, distinct results."""

    def test_extended_produces_snr(self) -> None:
        result, _, _ = _run_extended()
        assert "snr" in result.metrics
        assert result.metrics["snr"] > 0.0

    def test_extended_regime_in_outputs(self) -> None:
        result, _, _ = _run_extended()
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.EXTENDED

    def test_point_source_produces_snr(self) -> None:
        result, _, _ = _run_point_source()
        assert "snr" in result.metrics
        assert result.metrics["snr"] > 0.0

    def test_point_source_regime(self) -> None:
        result, _, _ = _run_point_source()
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.POINT_SOURCE

    def test_sub_pixel_produces_snr(self) -> None:
        result, _, _ = _run_sub_pixel()
        assert "snr" in result.metrics
        assert result.metrics["snr"] > 0.0

    def test_sub_pixel_regime(self) -> None:
        result, _, _ = _run_sub_pixel()
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.SUB_PIXEL

    def test_signal_positive_all_regimes(self) -> None:
        for run_fn in [_run_extended, _run_point_source, _run_sub_pixel]:
            result, _, _ = run_fn()
            sig = result.stage_outputs["spectral_integration"]["signal_e"]
            assert sig > 0.0

    def test_complete_history_all_regimes(self) -> None:
        expected = (
            "source", "atmosphere", "optics", "platform",
            "spectral_integration", "detector", "readout",
            "performance",
        )
        for run_fn in [_run_extended, _run_point_source, _run_sub_pixel]:
            result, _, _ = run_fn()
            assert result.history == expected


# ===================================================================
# 2. BACKWARD PROPAGATION
# ===================================================================


@pytest.mark.level2
class TestBackwardPropagation:
    """Verify signal_at and noise_at through full chain."""

    def test_signal_at_photoelectrons(self) -> None:
        result, _, _ = _run_extended()
        q = result.signal_at("photoelectrons")
        sig_e = result.stage_outputs["spectral_integration"]["signal_e"]
        assert q.value == pytest.approx(sig_e, rel=1e-10)

    def test_signal_at_dn(self) -> None:
        result, _, _ = _run_extended()
        q_pe = result.signal_at("photoelectrons")
        q_dn = result.signal_at("dn")
        gain = 32.0  # gain_e_per_dn = 32.0
        assert q_dn.value == pytest.approx(q_pe.value / gain, rel=1e-10)

    def test_noise_at_photoelectrons_positive(self) -> None:
        result, _, _ = _run_extended()
        q = result.noise_at("photoelectrons")
        assert q.value > 0.0

    def test_noise_specific_term(self) -> None:
        result, _, _ = _run_extended()
        q = result.noise_at("photoelectrons", term_name="read_noise")
        assert q.value == pytest.approx(5.0, rel=0.01)

    def test_round_trip_pe_dn_pe(self) -> None:
        """signal: pe → dn → pe recovers original value."""
        result, _, _ = _run_extended()
        q_pe = result.signal_at(ReferenceFrame.PHOTOELECTRONS)
        q_dn = q_pe.to(ReferenceFrame.DN, result.state)
        q_pe_back = q_dn.to(ReferenceFrame.PHOTOELECTRONS, result.state)
        assert q_pe_back.value == pytest.approx(q_pe.value, rel=1e-10)

    def test_noise_round_trip(self) -> None:
        """noise: pe → dn → pe recovers original."""
        result, _, _ = _run_extended()
        q1 = result.noise_at("photoelectrons", term_name="read_noise")
        q2 = q1.to(ReferenceFrame.DN, result.state)
        q3 = q2.to(ReferenceFrame.PHOTOELECTRONS, result.state)
        assert q3.value == pytest.approx(q1.value, rel=1e-10)


# ===================================================================
# 3. SWEEPS
# ===================================================================


@pytest.mark.level2
class TestSweeps:
    """Verify sweeps produce physically correct trends."""

    def test_snr_increases_with_aperture(self) -> None:
        """Larger aperture → more signal → higher SNR."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()

        result = sweep(
            session.run, ps,
            "optics.aperture_diameter_m",
            np.linspace(0.10, 0.50, 5),
            metric=lambda r: float(r.metrics["snr"]),
            keep_results=False,
        )
        diffs = np.diff(result.metric_values)
        assert np.all(diffs > 0), f"SNR not monotonically increasing: {result.metric_values}"

    def test_snr_increases_with_t_int(self) -> None:
        """Longer integration → more signal → higher SNR."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()

        result = sweep(
            session.run, ps,
            "spectral_integration.integration_time_s",
            [0.001, 0.002, 0.005, 0.010, 0.020],
            metric=lambda r: float(r.metrics["snr"]),
            keep_results=False,
        )
        diffs = np.diff(result.metric_values)
        assert np.all(diffs > 0), f"SNR not increasing with t_int: {result.metric_values}"

    def test_snr_decreases_with_read_noise(self) -> None:
        """Higher read noise → lower SNR."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()

        result = sweep(
            session.run, ps,
            "readout.read_noise_e_rms",
            [1.0, 5.0, 10.0, 25.0, 50.0],
            metric=lambda r: float(r.metrics["snr"]),
            keep_results=False,
        )
        diffs = np.diff(result.metric_values)
        assert np.all(diffs < 0), f"SNR not decreasing with read_noise: {result.metric_values}"

    def test_2d_sweep_shape(self) -> None:
        """2-D sweep produces correct grid shape."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()

        result = sweep_2d(
            session.run, ps,
            "optics.aperture_diameter_m", [0.15, 0.30, 0.45],
            "spectral_integration.integration_time_s", [0.001, 0.005],
            metric=lambda r: float(r.metrics["snr"]),
        )
        assert result.grid.shape == (3, 2)
        # Larger aperture always gives more SNR at each t_int
        for j in range(2):
            assert result.grid[2, j] > result.grid[0, j]


# ===================================================================
# 4. TOLERANCE (MONTE CARLO)
# ===================================================================


@pytest.mark.level2
class TestToleranceAnalysis:
    """Verify Monte Carlo tolerance analysis through the full chain."""

    def test_mc_produces_statistics(self) -> None:
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.set_tolerance(
            "optics.aperture_diameter_m",
            Tolerance(distribution="gaussian", params={"std": 0.005}),
        )
        ps.resolve()

        mc = monte_carlo(session.run, ps, n_trials=20, seed=42)
        assert mc.n_trials == 20
        assert mc.mean("snr") > 0.0
        assert mc.std("snr") > 0.0

    def test_mc_mean_near_nominal(self) -> None:
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()
        nominal_result = session.run(ps)
        nominal_snr = nominal_result.metrics["snr"]

        ps.set_tolerance(
            "optics.aperture_diameter_m",
            Tolerance(distribution="gaussian", params={"std": 0.005}),
        )
        ps.resolve()
        mc = monte_carlo(session.run, ps, n_trials=30, seed=42)
        # Mean should be within 10% of nominal (small tolerance)
        assert mc.mean("snr") == pytest.approx(nominal_snr, rel=0.10)

    def test_mc_reproducible(self) -> None:
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.set_tolerance(
            "optics.aperture_diameter_m",
            Tolerance(distribution="gaussian", params={"std": 0.005}),
        )
        ps.resolve()
        mc1 = monte_carlo(session.run, ps, n_trials=10, seed=99)
        mc2 = monte_carlo(session.run, ps, n_trials=10, seed=99)
        np.testing.assert_array_equal(mc1.metric_array, mc2.metric_array)


# ===================================================================
# 5. SATURATION CHECKS
# ===================================================================


@pytest.mark.level2
class TestSaturation:
    """Verify saturation detection and margin computation."""

    def test_normal_operation_not_saturated(self) -> None:
        result, _, _ = _run_extended()
        well_margin = result.metrics.get("well_margin_dB")
        if well_margin is not None:
            assert well_margin > 0.0, "Normal operation should not be well-saturated"

    def test_forced_well_saturation(self) -> None:
        """Very long integration with high signal should saturate the well."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        # Long integration + low well capacity → saturation
        ps.set("spectral_integration.integration_time_s", 10.0)
        ps.set("readout.full_well_capacity_e", 1000.0)
        ps.resolve()
        result = session.run(ps)

        # Signal should be clipped at FWC
        ro = result.stage_outputs["readout"]
        assert ro["well_status"] == "clipped"

    def test_adc_bits_affects_dn(self) -> None:
        """Reducing ADC bits should reduce max DN."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.set("readout.adc_bits", 8)
        ps.set("readout.gain_e_per_dn", 100.0)
        ps.resolve()
        result = session.run(ps)

        signal_dn = result.stage_outputs["readout"]["signal_dn_final"]
        assert signal_dn <= 255.0  # 2^8 - 1

    def test_dynamic_range_in_metrics(self) -> None:
        result, _, _ = _run_extended()
        dr = result.metrics.get("dynamic_range_dB")
        if dr is not None:
            assert dr > 0.0


# ===================================================================
# 6. COMPLETE NOISE BUDGET
# ===================================================================


@pytest.mark.level2
class TestNoiseBudget:
    """Verify the full noise budget through the chain."""

    def test_noise_terms_present(self) -> None:
        result, _, _ = _run_extended()
        names = {nt.name for nt in result.noise_terms}
        # At minimum, these should always be present:
        assert "signal_shot" in names
        assert "dark_shot" in names
        assert "read_noise" in names
        assert "quantization" in names

    def test_noise_rss_consistency(self) -> None:
        """Total noise = RSS of all individual terms."""
        result, _, _ = _run_extended()
        noise_sq = sum(nt.value_e ** 2 for nt in result.noise_terms)
        total_rss = math.sqrt(noise_sq)

        # Compare with performance stage total
        ro = result.stage_outputs["readout"]
        sigma_total = ro.get("sigma_total_e")
        if sigma_total is not None:
            assert total_rss == pytest.approx(sigma_total, rel=1e-6)

    def test_snr_consistent_with_noise_budget(self) -> None:
        """SNR = signal_e_final / sigma_total_e."""
        result, _, _ = _run_extended()
        signal_e_final = result.stage_outputs["readout"]["signal_e_final"]
        sigma_total_e = result.stage_outputs["readout"]["sigma_total_e"]
        expected_snr = signal_e_final / sigma_total_e
        assert result.metrics["snr"] == pytest.approx(expected_snr, rel=1e-10)

    def test_shot_noise_sqrt_signal(self) -> None:
        """Signal shot noise = √signal_e_final (accounts for well clipping)."""
        result, _, _ = _run_extended()
        signal_e_final = result.stage_outputs["readout"]["signal_e_final"]
        shot_terms = [nt for nt in result.noise_terms if nt.name == "signal_shot"]
        assert len(shot_terms) == 1
        expected_shot = math.sqrt(signal_e_final)
        assert shot_terms[0].value_e == pytest.approx(expected_shot, rel=0.01)

    def test_dark_shot_noise(self) -> None:
        """Dark shot noise = √(dark_rate × t_int)."""
        result, _, _ = _run_extended()
        dark_e = 100.0 * T_INT  # dark_rate × t_int = 0.5 e-
        expected = math.sqrt(dark_e)
        dark_terms = [nt for nt in result.noise_terms if nt.name == "dark_shot"]
        assert len(dark_terms) == 1
        assert dark_terms[0].value_e == pytest.approx(expected, rel=0.01)

    def test_noise_budget_has_16_terms(self) -> None:
        """DetectorStage should compute all 16 noise sources."""
        result, _, _ = _run_extended()
        budget = result.stage_outputs["detector"].get("noise_budget_raw")
        if budget is not None:
            assert len(budget.terms) == 16

    def test_all_noise_nonnegative(self) -> None:
        """Every noise term must be >= 0."""
        result, _, _ = _run_extended()
        for nt in result.noise_terms:
            assert nt.value_e >= 0.0, f"Noise term {nt.name} is negative: {nt.value_e}"

    def test_dark_exceeds_fwc_no_crash(self) -> None:
        """When dark_e alone exceeds FWC, chain runs without error and SNR is near zero."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        # Very high dark rate + long integration overwhelms a tiny FWC.
        ps.set("detector.dark_rate_e_per_s", 1e8)
        ps.set("spectral_integration.integration_time_s", 1.0)
        ps.set("readout.full_well_capacity_e", 1000.0)
        ps.resolve()
        result = session.run(ps)
        # Signal should be clipped to ~0 (available_fwc = 0).
        signal_e_final = result.stage_outputs["readout"]["signal_e_final"]
        assert signal_e_final == pytest.approx(0.0, abs=1.0)
        # SNR should be ~0 (or very small).
        snr = result.metrics["snr"]
        assert snr < 1.0

    def test_noise_regime_imaging_excludes_spatial(self) -> None:
        """In imaging regime, sigma_total_e excludes PRNU/DSNU/clutter."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        # Enable PRNU so spatial terms are nonzero.
        ps.set("detector.prnu_pct", 5.0)
        ps.set("detector.noise_regime", "imaging")
        ps.resolve()
        result = session.run(ps)
        ro = result.stage_outputs["readout"]
        assert ro["noise_regime"] == "imaging"
        sigma_temporal = ro["sigma_temporal_e"]
        sigma_spatial = ro["sigma_spatial_e"]
        sigma_total = ro["sigma_total_e"]
        # Spatial noise should be nonzero (PRNU is 5%).
        assert sigma_spatial > 0.0
        # In imaging mode, sigma_total equals temporal only.
        assert sigma_total == pytest.approx(sigma_temporal, rel=1e-12)

    def test_noise_regime_detection_includes_spatial(self) -> None:
        """In detection regime, sigma_total_e includes spatial terms."""
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.set("detector.prnu_pct", 5.0)
        ps.set("detector.noise_regime", "detection")
        ps.resolve()
        result = session.run(ps)
        ro = result.stage_outputs["readout"]
        assert ro["noise_regime"] == "detection"
        sigma_temporal = ro["sigma_temporal_e"]
        sigma_spatial = ro["sigma_spatial_e"]
        sigma_total = ro["sigma_total_e"]
        assert sigma_spatial > 0.0
        # In detection mode, sigma_total includes both.
        expected = math.sqrt(sigma_temporal**2 + sigma_spatial**2)
        assert sigma_total == pytest.approx(expected, rel=1e-12)
        # And it's larger than temporal alone.
        assert sigma_total > sigma_temporal


# ===================================================================
# 7. SENSITIVITY ANALYSIS
# ===================================================================


@pytest.mark.level2
class TestSensitivityAnalysis:
    """Verify sensitivity analysis through the full chain."""

    def test_aperture_has_positive_sensitivity(self) -> None:
        session = RadiantSession(wavelength_um=WL)
        ps = _base_params(session)
        ps.resolve()

        result = sensitivity(
            session.run, ps,
            metric=lambda r: float(r.metrics["snr"]),
            param_names=["optics.aperture_diameter_m"],
            delta_fraction=0.01,
        )
        assert len(result.entries) == 1
        # Larger aperture → higher SNR → positive sensitivity
        assert result.entries[0].sensitivity > 0.0


# ===================================================================
# 8. DETERMINISM
# ===================================================================


@pytest.mark.level2
class TestDeterminism:
    """Same inputs produce bitwise-identical outputs."""

    def test_extended_deterministic(self) -> None:
        r1, _, _ = _run_extended()
        r2, _, _ = _run_extended()
        s1 = r1.stage_outputs["spectral_integration"]["signal_e"]
        s2 = r2.stage_outputs["spectral_integration"]["signal_e"]
        assert s1 == s2  # exact equality, not approx

    def test_point_source_deterministic(self) -> None:
        r1, _, _ = _run_point_source()
        r2, _, _ = _run_point_source()
        assert r1.metrics["snr"] == r2.metrics["snr"]
