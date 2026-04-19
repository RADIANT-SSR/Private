"""Integration test: dual-path MTF architecture end-to-end.

Validates that the PSF path and MTF product path are fully wired and
consistent through the complete signal chain.

Uses the reference MWIR LEO config with jitter and smear enabled to
exercise both anisotropic effects.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.performance.consistency_check import DualPathConsistencyResult
from radiant.performance.mtf_budget import MTFBudgetResult

# ---------------------------------------------------------------------------
# Reference case constants
# ---------------------------------------------------------------------------
D = 0.30
F = 1.20
PITCH = 18e-6
TAU_OPT = 0.70
QE = 0.70
T_TARGET = 300.0
EPS_TARGET = 0.95
SENSOR_ALT = 8000.0
FILTER_MIN = 3.5
FILTER_MAX = 5.0
T_INT = 0.005
DARK_RATE = 100.0
READ_NOISE = 5.0
GAIN = 32.0

# Platform effects
JITTER_URAD = 5.0  # isotropic jitter
SMEAR_UM = 5.0     # along-track smear


@pytest.fixture(scope="module")
def result():
    """Run the chain with jitter and smear enabled."""
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", T_TARGET)
    params.set("source.target.emissivity", EPS_TARGET)
    params.set("optics.aperture_diameter_m", D)
    params.set("optics.focal_length_m", F)
    params.set("optics.transmission_scalar", TAU_OPT)
    params.set("detector.pixel_pitch_x_um", PITCH * 1e6)
    params.set("detector.pixel_pitch_y_um", PITCH * 1e6)
    params.set("detector.qe_value", QE)
    params.set("detector.dark_rate_e_per_s", DARK_RATE)
    params.set("geometry.sensor_altitude_m", SENSOR_ALT)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", FILTER_MIN)
    params.set("spectral_integration.filter_max_um", FILTER_MAX)
    params.set("spectral_integration.integration_time_s", T_INT)
    params.set("readout.read_noise_e_rms", READ_NOISE)
    params.set("readout.gain_e_per_dn", GAIN)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 2000000.0)
    params.set("platform.jitter_rms_urad", JITTER_URAD)
    params.set("platform.smear_length_um", SMEAR_UM)
    params.resolve()
    return session.run(params)


# ---------------------------------------------------------------------------
# MTF terms present from all stages
# ---------------------------------------------------------------------------


class TestMTFTermsPresent:
    """All expected MTF terms exist in the chain state."""

    @pytest.mark.parametrize(
        "term",
        [
            "mtf_optics_x", "mtf_optics_y",
            "mtf_jitter_x", "mtf_jitter_y",
            "mtf_smear_x", "mtf_smear_y",
            "mtf_pixel_aperture_x", "mtf_pixel_aperture_y",
            "mtf_ipc_x", "mtf_ipc_y",
        ],
    )
    def test_term_exists(self, result, term: str) -> None:
        assert term in result.state.mtf_terms

    def test_frequency_grid_populated(self, result) -> None:
        freq = result.state.spatial_freq_cycles_per_mrad
        assert freq is not None
        assert len(freq) > 10

    def test_frequency_monotonically_increasing(self, result) -> None:
        freq = result.state.spatial_freq_cycles_per_mrad
        assert np.all(np.diff(freq) > 0)


# ---------------------------------------------------------------------------
# Physical validity
# ---------------------------------------------------------------------------


class TestPhysicalValidity:
    """All MTF terms are physically valid."""

    def test_all_terms_bounded_0_1(self, result) -> None:
        for name, arr in result.state.mtf_terms.items():
            assert np.all(arr >= -1e-10), f"{name} has negative values"
            assert np.all(arr <= 1.0 + 1e-10), f"{name} exceeds 1.0"

    def test_dc_is_unity(self, result) -> None:
        for name, arr in result.state.mtf_terms.items():
            assert arr[0] == pytest.approx(1.0, abs=1e-6), f"{name} DC != 1.0"


# ---------------------------------------------------------------------------
# MTF budget
# ---------------------------------------------------------------------------


class TestMTFBudget:
    """MTF budget is computed and correct."""

    def test_budget_exists(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        assert isinstance(budget, MTFBudgetResult)

    def test_system_mtf_is_product(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        terms = result.state.mtf_terms

        # Compute expected system MTF as product of all _x terms.
        expected_x = np.ones_like(budget.freq_cycles_per_mrad)
        expected_y = np.ones_like(budget.freq_cycles_per_mrad)
        for name, arr in terms.items():
            if name.endswith("_x"):
                expected_x *= arr
            elif name.endswith("_y"):
                expected_y *= arr

        np.testing.assert_allclose(budget.system_mtf_x, expected_x, atol=1e-12)
        np.testing.assert_allclose(budget.system_mtf_y, expected_y, atol=1e-12)

    def test_budget_at_nyquist_bounded(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        assert 0.0 < budget.system_mtf_at_nyquist_x <= 1.0
        assert 0.0 < budget.system_mtf_at_nyquist_y <= 1.0

    def test_per_term_at_nyquist_bounded(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        for name, val in budget.per_term_at_nyquist.items():
            assert 0.0 <= val <= 1.0 + 1e-10, f"{name} at Nyquist out of [0, 1]"

    def test_dominant_contributor_identified(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        assert budget.dominant_contributor_at_nyquist_x in result.state.mtf_terms
        assert budget.dominant_contributor_at_nyquist_y in result.state.mtf_terms


# ---------------------------------------------------------------------------
# Anisotropy from smear
# ---------------------------------------------------------------------------


class TestAnisotropy:
    """Along-track smear makes y MTF worse than x."""

    def test_smear_degrades_y_more(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        # Along-track smear degrades y; x is unity for smear.
        terms = result.state.mtf_terms
        smear_x = terms["mtf_smear_x"]
        smear_y = terms["mtf_smear_y"]
        # At non-zero frequencies, smear_y < smear_x.
        assert np.all(smear_y[1:] <= smear_x[1:] + 1e-10)

    def test_system_y_worse_than_x(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        # System MTF at Nyquist: x should be better than y (less degraded).
        assert budget.system_mtf_at_nyquist_x >= budget.system_mtf_at_nyquist_y


# ---------------------------------------------------------------------------
# Dual-path consistency check
# ---------------------------------------------------------------------------


class TestDualPathConsistency:
    """The dual-path consistency check should pass."""

    def test_consistency_result_exists(self, result) -> None:
        consistency = result.stage_outputs["performance"]["dual_path_consistency"]
        assert isinstance(consistency, DualPathConsistencyResult)

    def test_consistency_passes(self, result) -> None:
        consistency = result.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x, (
            f"X-axis failed: max_err={consistency.max_absolute_error_x:.4f} "
            f"(tol={consistency.tolerance})"
        )
        assert consistency.passed_y, (
            f"Y-axis failed: max_err={consistency.max_absolute_error_y:.4f} "
            f"(tol={consistency.tolerance})"
        )


# ---------------------------------------------------------------------------
# PSF-path metrics still present
# ---------------------------------------------------------------------------


class TestPSFPathMetrics:
    """PSF-path spatial metrics are still computed correctly."""

    def test_mtf_at_nyquist_positive(self, result) -> None:
        assert result.metrics["mtf_at_nyquist"] > 0.0

    def test_rer_bounded(self, result) -> None:
        assert 0.0 < result.metrics["rer"] < 1.0

    def test_fwhm_positive(self, result) -> None:
        assert result.metrics["fwhm_x_m"] > 0.0
        assert result.metrics["fwhm_y_m"] > 0.0

    def test_snr_positive(self, result) -> None:
        assert result.metrics["snr"] > 0.0
