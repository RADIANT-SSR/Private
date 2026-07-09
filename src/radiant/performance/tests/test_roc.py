"""Level 0 tests for radiant.performance.roc (scenario 6.4).

Truth anchors from Gaussian signal-detection theory (Rule 18):

- SNR = 0 → the ROC is the chance diagonal (P_d = P_fa), AUC = 0.5.
- AUC = Φ(SNR/√2): SNR=1 → Φ(0.707) ≈ 0.760; SNR→∞ → 1.
- P_d increases with SNR at fixed P_fa; P_d ≥ P_fa for SNR ≥ 0.
- P_d(P_fa=0.5) = Φ(SNR/... ) ; at Q⁻¹(0.5)=0 → P_d = Q(−SNR) = Φ(SNR).
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from radiant.performance.roc import RocError, detection_probability, roc_auc, roc_curve


class TestAUC:
    def test_chance_at_zero_snr(self) -> None:
        assert roc_auc(0.0) == pytest.approx(0.5, rel=1e-12)

    def test_snr_one_anchor(self) -> None:
        assert roc_auc(1.0) == pytest.approx(float(norm.cdf(1.0 / np.sqrt(2))), rel=1e-12)
        assert roc_auc(1.0) == pytest.approx(0.7602, abs=1e-3)

    def test_increases_with_snr(self) -> None:
        assert roc_auc(3.0) > roc_auc(1.0) > roc_auc(0.5)

    def test_approaches_one(self) -> None:
        assert roc_auc(8.0) == pytest.approx(1.0, abs=1e-6)


class TestDetectionProbability:
    def test_pd_at_half_pfa_is_phi_snr(self) -> None:
        # Q⁻¹(0.5) = 0 → P_d = Q(−SNR) = Φ(SNR)
        assert detection_probability(2.0, 0.5) == pytest.approx(float(norm.cdf(2.0)), rel=1e-9)

    def test_zero_snr_pd_equals_pfa(self) -> None:
        for pfa in (0.01, 0.1, 0.5):
            assert detection_probability(0.0, pfa) == pytest.approx(pfa, rel=1e-9)

    def test_pd_increases_with_snr(self) -> None:
        assert detection_probability(4.0, 0.01) > detection_probability(2.0, 0.01)


class TestRocCurve:
    def test_shape_and_monotone(self) -> None:
        pfa, pd = roc_curve(3.0, n_points=100)
        assert pfa.shape == pd.shape == (100,)
        assert np.all(np.diff(pd) >= -1e-9)  # non-decreasing with pfa
        assert np.all(pd >= pfa - 1e-9)  # above the chance diagonal

    def test_diagonal_at_zero_snr(self) -> None:
        pfa, pd = roc_curve(0.0, n_points=50)
        assert np.allclose(pd, pfa, atol=1e-9)


class TestValidation:
    def test_negative_snr_raises(self) -> None:
        with pytest.raises(RocError, match="snr"):
            roc_curve(-1.0)

    def test_bad_pfa_raises(self) -> None:
        with pytest.raises(RocError, match="p_fa"):
            detection_probability(2.0, 1.5)
