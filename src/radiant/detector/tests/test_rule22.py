"""Level 0 tests for the Rule 22 empirical dark-current law (Gap 123).

Anchor values are hand-computed from the published three-term formula
(M. Zandian, J. Electron. Mater. 52, 7095 (2023), as quoted in
Materials 17, 4522 (2024) eq. (3)) with CODATA q/k_B = 11604.518 K/eV —
independent of the module under test.
"""

from __future__ import annotations

import math

import pytest

from radiant.detector.errors import DetectorValidationError
from radiant.detector.rule22 import (
    rule22_dark_current_density_a_per_cm2,
    rule22_fit_range_note,
)

pytestmark = pytest.mark.level0


class TestRule22Anchors:
    """Hand-computed truth anchors for the published law."""

    def test_lwir_80k_diffusion_regime(self) -> None:
        # λc = 10 µm, T = 80 K (1/λT = 0.00125 < 0.0025 — diffusion term
        # dominates): J = (1e7·10^−6.2 + 70·10^1.08)·exp(−1.04·0.124·11604.518/80)
        # = 6.371174e-6 A/cm².
        j = rule22_dark_current_density_a_per_cm2(10.0, 80.0)
        assert j == pytest.approx(6.371174e-6, rel=1e-4)

    def test_lwir_room_temperature(self) -> None:
        # λc = 10 µm, T = 300 K: diffusion-dominated, J = 5.779753 A/cm².
        j = rule22_dark_current_density_a_per_cm2(10.0, 300.0)
        assert j == pytest.approx(5.779753, rel=1e-4)

    def test_background_flux_floor_regime(self) -> None:
        # λc = 4 µm, T = 40 K (1/λT = 0.00625 > 0.005): the 1.5e-21·λ²·T
        # background-flux floor dominates → J ≈ 1.5e-21·16·40 = 9.6e-19 A/cm².
        j = rule22_dark_current_density_a_per_cm2(4.0, 40.0)
        assert j == pytest.approx(9.6e-19, rel=1e-4)

    def test_swir_end_of_range(self) -> None:
        # λc = 1.6 µm, T = 300 K: J = 1.564391e-8 A/cm².
        j = rule22_dark_current_density_a_per_cm2(1.6, 300.0)
        assert j == pytest.approx(1.564391e-8, rel=1e-4)

    def test_monotonic_in_temperature(self) -> None:
        j_cold = rule22_dark_current_density_a_per_cm2(10.0, 70.0)
        j_warm = rule22_dark_current_density_a_per_cm2(10.0, 90.0)
        assert j_warm > j_cold

    def test_agrees_with_rule07_in_diffusion_regime(self) -> None:
        # Cross-model consistency: in the shared diffusion-limited regime
        # (1/λT < 0.0025) the two published laws describe the same device
        # class and agree to well within a factor of 2 (hand-checked:
        # ratio 1.08 at (10 µm, 80 K), 1.58 at (12 µm, 90 K)).
        from radiant.detector.rule07 import rule07_dark_current_density_a_per_cm2

        for lam_um, temp_k in [(10.0, 80.0), (12.0, 90.0), (5.0, 150.0)]:
            j07 = rule07_dark_current_density_a_per_cm2(lam_um, temp_k)
            j22 = rule22_dark_current_density_a_per_cm2(lam_um, temp_k)
            assert abs(math.log10(j07 / j22)) < math.log10(2.0)


class TestRule22FitRange:
    """Published validity: λc ∈ [1.6, 17] µm, T ∈ [20, 330] K."""

    def test_inside_range_no_note(self) -> None:
        assert rule22_fit_range_note(10.0, 80.0) == ""

    def test_cutoff_outside_range_notes(self) -> None:
        assert "1.6" in rule22_fit_range_note(1.0, 300.0)
        assert "17" in rule22_fit_range_note(19.0, 60.0)

    def test_temperature_outside_range_notes(self) -> None:
        assert "20" in rule22_fit_range_note(10.0, 15.0)
        assert "330" in rule22_fit_range_note(10.0, 350.0)


class TestRule22Errors:
    def test_nonpositive_cutoff_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule22_dark_current_density_a_per_cm2(0.0, 80.0)
        with pytest.raises(DetectorValidationError):
            rule22_dark_current_density_a_per_cm2(-1.0, 80.0)

    def test_nonpositive_temperature_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule22_dark_current_density_a_per_cm2(10.0, 0.0)

    def test_nan_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule22_dark_current_density_a_per_cm2(math.nan, 80.0)
        with pytest.raises(DetectorValidationError):
            rule22_dark_current_density_a_per_cm2(10.0, math.nan)

    def test_never_nan_or_inf(self) -> None:
        # Extreme but positive inputs stay finite (flux floor keeps J > 0).
        j = rule22_dark_current_density_a_per_cm2(17.0, 20.0)
        assert math.isfinite(j)
        assert j > 0.0
