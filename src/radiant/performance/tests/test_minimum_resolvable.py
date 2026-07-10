"""Level 0 tests for radiant.performance.minimum_resolvable (Gap 53).

Truth anchors from the MRT/MRC definitions (Rule 18):
MRT(f) = k·NETD/MTF; MRC(f) = k·NEΔρ/MTF, k = 2.25 default.

- NETD 50 mK, MTF 1.0, k 2.25 → MRT = 112.5 mK.
- MTF 0.5 → MRT doubles to 225 mK.
- NEΔρ 0.01, MTF 1.0 → MRC = 0.0225.
"""

from __future__ import annotations

import pytest

from radiant.performance.minimum_resolvable import (
    DEFAULT_SNR_THRESHOLD,
    MinimumResolvableError,
    minimum_resolvable_contrast,
    minimum_resolvable_temperature_K,
)


class TestMRT:
    def test_flat_field_anchor(self) -> None:
        # MTF = 1 → MRT = k·NETD
        assert minimum_resolvable_temperature_K(0.050, 1.0) == pytest.approx(
            2.25 * 0.050, rel=1e-12
        )

    def test_diverges_as_mtf_drops(self) -> None:
        assert minimum_resolvable_temperature_K(0.050, 0.5) == pytest.approx(
            2.0 * minimum_resolvable_temperature_K(0.050, 1.0), rel=1e-12
        )

    def test_custom_threshold(self) -> None:
        assert minimum_resolvable_temperature_K(0.050, 1.0, threshold_snr=4.0) == pytest.approx(
            0.2, rel=1e-12
        )

    def test_default_threshold_value(self) -> None:
        assert pytest.approx(2.25) == DEFAULT_SNR_THRESHOLD


class TestMRC:
    def test_anchor(self) -> None:
        assert minimum_resolvable_contrast(0.01, 1.0) == pytest.approx(0.0225, rel=1e-12)

    def test_symmetric_with_mrt_form(self) -> None:
        # Same formula: MRC/NEDR == MRT/NETD at equal MTF & threshold.
        mrc = minimum_resolvable_contrast(0.02, 0.7)
        mrt = minimum_resolvable_temperature_K(0.02, 0.7)
        assert mrc == pytest.approx(mrt, rel=1e-12)


class TestValidation:
    def test_zero_mtf_raises(self) -> None:
        with pytest.raises(MinimumResolvableError, match="mtf_value"):
            minimum_resolvable_temperature_K(0.05, 0.0)

    def test_mtf_above_one_raises(self) -> None:
        with pytest.raises(MinimumResolvableError, match="mtf_value"):
            minimum_resolvable_temperature_K(0.05, 1.5)

    def test_negative_netd_raises(self) -> None:
        with pytest.raises(MinimumResolvableError, match="netd_K"):
            minimum_resolvable_temperature_K(-0.05, 1.0)

    def test_zero_threshold_raises(self) -> None:
        with pytest.raises(MinimumResolvableError, match="threshold_snr"):
            minimum_resolvable_temperature_K(0.05, 1.0, threshold_snr=0.0)
