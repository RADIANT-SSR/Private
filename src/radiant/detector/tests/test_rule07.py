"""Level 0 tests for the Rule 07 empirical dark-current law (Gap 123).

Anchor values are hand-computed from the published formula
(Tennant et al., J. Electron. Mater. 37, 1406 (2008)) with CODATA
q/k_B = 11604.518 K/eV — independent of the module under test. The
published coefficients themselves are cross-checked against two
independent open quotations of the law (Materials 17, 4522 (2024)
eqs. (1)-(2); Sensors 23, 7564 (2023) refs).
"""

from __future__ import annotations

import math

import pytest

from radiant.detector.errors import DetectorValidationError
from radiant.detector.rule07 import (
    rule07_dark_current_density_a_per_cm2,
    rule07_effective_cutoff_um,
    rule07_fit_range_note,
)

pytestmark = pytest.mark.level0


class TestRule07Anchors:
    """Hand-computed truth anchors for the published law."""

    def test_lwir_77k(self) -> None:
        # λc = 10 µm, T = 77 K (λe·T = 770 µm·K, mid fit range):
        # J = 8367·exp(−1.162972237·1.24·11604.518/770) = 3.047050e-6 A/cm²
        j = rule07_dark_current_density_a_per_cm2(10.0, 77.0)
        assert j == pytest.approx(3.047050e-6, rel=1e-4)

    def test_mwir_110k(self) -> None:
        # λc = 5 µm, T = 110 K (λe·T = 550 µm·K):
        j = rule07_dark_current_density_a_per_cm2(5.0, 110.0)
        assert j == pytest.approx(5.109796e-10, rel=1e-4)

    def test_short_cutoff_effective_wavelength(self) -> None:
        # λc = 3 µm < λ_threshold: λe = 3/(1 − (λs/3 − λs/λth)^0.544071282)
        # = 3.4494418 µm — the correction lengthens the effective cutoff.
        lam_e = rule07_effective_cutoff_um(3.0)
        assert lam_e == pytest.approx(3.4494418, rel=1e-6)
        # And the resulting density at T = 150 K:
        j = rule07_dark_current_density_a_per_cm2(3.0, 150.0)
        assert j == pytest.approx(7.520659e-11, rel=1e-4)

    def test_no_correction_at_long_cutoff(self) -> None:
        assert rule07_effective_cutoff_um(10.0) == pytest.approx(10.0, rel=1e-12)

    def test_continuity_at_threshold(self) -> None:
        # The λe correction vanishes smoothly at λ_threshold = 4.635136423 µm.
        below = rule07_dark_current_density_a_per_cm2(4.635136423 - 1e-9, 100.0)
        above = rule07_dark_current_density_a_per_cm2(4.635136423 + 1e-9, 100.0)
        assert below == pytest.approx(above, rel=1e-4)

    def test_monotonic_in_temperature_and_cutoff(self) -> None:
        j_cold = rule07_dark_current_density_a_per_cm2(10.0, 70.0)
        j_warm = rule07_dark_current_density_a_per_cm2(10.0, 90.0)
        assert j_warm > j_cold
        j_short = rule07_dark_current_density_a_per_cm2(8.0, 80.0)
        j_long = rule07_dark_current_density_a_per_cm2(12.0, 80.0)
        assert j_long > j_short


class TestRule07FitRange:
    """Published validity: λe·T ∈ [400, 1700] µm·K and T > 77 K."""

    def test_inside_range_no_note(self) -> None:
        assert rule07_fit_range_note(10.0, 78.0) == ""

    def test_low_product_notes(self) -> None:
        # λe·T = 300 µm·K < 400 µm·K.
        assert "400" in rule07_fit_range_note(5.0, 60.0)

    def test_high_product_notes(self) -> None:
        # λe·T = 2040 µm·K > 1700 µm·K.
        assert "1700" in rule07_fit_range_note(17.0, 120.0)

    def test_low_temperature_notes(self) -> None:
        # λe·T = 770 µm·K is fine but T = 70 K < 77 K.
        assert "77" in rule07_fit_range_note(11.0, 70.0)


class TestRule07Errors:
    def test_nonpositive_cutoff_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(0.0, 80.0)
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(-5.0, 80.0)

    def test_nonpositive_temperature_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(10.0, 0.0)

    def test_nan_raises(self) -> None:
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(math.nan, 80.0)
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(10.0, math.inf)

    def test_cutoff_below_correction_domain_raises(self) -> None:
        # For λc ≲ 0.1926 µm the λe denominator goes non-positive: the
        # published correction is undefined and the law must refuse, not
        # return a negative effective wavelength (Rule 16).
        with pytest.raises(DetectorValidationError):
            rule07_dark_current_density_a_per_cm2(0.15, 80.0)

    def test_never_nan_or_inf(self) -> None:
        # Deep-cryo extrapolation underflows toward 0.0, never NaN/inf.
        j = rule07_dark_current_density_a_per_cm2(2.0, 20.0)
        assert math.isfinite(j)
        assert j >= 0.0
