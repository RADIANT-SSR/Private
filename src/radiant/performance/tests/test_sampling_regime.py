"""Level 0 tests for radiant.performance.sampling_regime (Gap 50).

Truth anchors are the Q-thresholds by definition (Rule 18):
Q < 1 → detector-limited (0.0); 1 ≤ Q ≤ 2 → near-critical (1.0);
Q > 2 → diffraction-limited (2.0).
"""

from __future__ import annotations

import pytest

from radiant.performance.sampling_regime import (
    DETECTOR_LIMITED,
    DIFFRACTION_LIMITED,
    NEAR_CRITICAL,
    SamplingRegimeError,
    classify_sampling_regime,
    sampling_regime_label,
)


class TestClassify:
    def test_detector_limited(self) -> None:
        assert classify_sampling_regime(0.5) == DETECTOR_LIMITED

    def test_near_critical_boundaries(self) -> None:
        assert classify_sampling_regime(1.0) == NEAR_CRITICAL
        assert classify_sampling_regime(1.5) == NEAR_CRITICAL
        assert classify_sampling_regime(2.0) == NEAR_CRITICAL

    def test_diffraction_limited(self) -> None:
        assert classify_sampling_regime(2.5) == DIFFRACTION_LIMITED

    def test_just_below_one_is_detector(self) -> None:
        assert classify_sampling_regime(0.999) == DETECTOR_LIMITED

    def test_just_above_two_is_diffraction(self) -> None:
        assert classify_sampling_regime(2.001) == DIFFRACTION_LIMITED


class TestLabel:
    def test_labels(self) -> None:
        assert sampling_regime_label(DETECTOR_LIMITED) == "detector-limited"
        assert sampling_regime_label(NEAR_CRITICAL) == "near-critical"
        assert sampling_regime_label(DIFFRACTION_LIMITED) == "diffraction-limited"

    def test_unknown_code_raises(self) -> None:
        with pytest.raises(SamplingRegimeError, match="code"):
            sampling_regime_label(3.0)


class TestValidation:
    def test_zero_q_raises(self) -> None:
        with pytest.raises(SamplingRegimeError, match="Q"):
            classify_sampling_regime(0.0)
