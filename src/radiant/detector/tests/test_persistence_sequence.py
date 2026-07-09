"""Level 0 tests for radiant.detector.persistence_sequence (scenario 2.4).

Truth anchors from the exponential-decay model (Rule 18):

- residual(1) = prior · f (frame 1 is the full first-frame residual).
- residual(n) = residual(1) · exp(−(n−1)·Δt/τ).
- prior 150000 e-, f = 0.015 → residual(1) = 2250 e-.
- frames_to_clear: residual(n) < threshold.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.detector.persistence_sequence import (
    PersistenceSequenceError,
    frames_to_clear,
    persistence_residual_e,
    persistence_residual_sequence_e,
)

PRIOR = 150_000.0
FRAC = 0.015
TAU = 0.050
DT = 1.0 / 60.0  # 60 Hz


class TestResidual:
    def test_first_frame_anchor(self) -> None:
        assert persistence_residual_e(PRIOR, FRAC, TAU, DT, 1) == pytest.approx(2250.0, rel=1e-12)

    def test_decay_between_frames(self) -> None:
        r1 = persistence_residual_e(PRIOR, FRAC, TAU, DT, 1)
        r2 = persistence_residual_e(PRIOR, FRAC, TAU, DT, 2)
        assert r2 == pytest.approx(r1 * math.exp(-DT / TAU), rel=1e-12)

    def test_monotone_decreasing(self) -> None:
        seq = persistence_residual_sequence_e(PRIOR, FRAC, TAU, DT, 20)
        assert seq.shape == (20,)
        assert np.all(np.diff(seq) < 0.0)
        assert seq[0] == pytest.approx(2250.0, rel=1e-12)

    def test_zero_fraction_zero_residual(self) -> None:
        assert persistence_residual_e(PRIOR, 0.0, TAU, DT, 5) == 0.0


class TestFramesToClear:
    def test_clear_below_one_lsb(self) -> None:
        # 1 LSB = gain 100 e-/DN. residual(n) < 100.
        n = frames_to_clear(PRIOR, FRAC, TAU, DT, threshold_e=100.0)
        assert persistence_residual_e(PRIOR, FRAC, TAU, DT, n) < 100.0
        assert persistence_residual_e(PRIOR, FRAC, TAU, DT, n - 1) >= 100.0

    def test_already_clear_returns_one(self) -> None:
        assert frames_to_clear(PRIOR, FRAC, TAU, DT, threshold_e=1e9) == 1


class TestValidation:
    def test_bad_fraction_raises(self) -> None:
        with pytest.raises(PersistenceSequenceError, match="persistence_fraction"):
            persistence_residual_e(PRIOR, 1.5, TAU, DT, 1)

    def test_zero_tau_raises(self) -> None:
        with pytest.raises(PersistenceSequenceError, match="tau"):
            persistence_residual_e(PRIOR, FRAC, 0.0, DT, 1)

    def test_frame_zero_raises(self) -> None:
        with pytest.raises(PersistenceSequenceError, match="frame_number"):
            persistence_residual_e(PRIOR, FRAC, TAU, DT, 0)
