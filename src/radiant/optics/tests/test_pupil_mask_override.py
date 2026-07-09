"""Level 0 tests for arbitrary pupil-mask injection (Gap 54).

Truth anchors are mask-identity properties (Rule 18):

- ``mask_override=None`` reproduces the parametric pupil byte-identically
  (regression guard for all existing optics goldens).
- A supplied mask replaces the parametric geometry exactly.
- Shape mismatch and out-of-range amplitudes raise.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.pupil_amplitude import SpiderVaneSpec, make_pupil_amplitude


class TestNoOverrideRegression:
    def test_none_matches_parametric(self) -> None:
        a = make_pupil_amplitude(128, 0.3, SpiderVaneSpec(4, 0.03))
        b = make_pupil_amplitude(128, 0.3, SpiderVaneSpec(4, 0.03), None)
        assert np.array_equal(a, b)


class TestOverrideReplaces:
    def test_override_returned_verbatim(self) -> None:
        custom = np.zeros((64, 64), dtype=np.float64)
        custom[16:48, 16:48] = 1.0  # a square aperture — non-circular
        out = make_pupil_amplitude(64, 0.3, None, custom)
        assert np.array_equal(out, custom)

    def test_override_supersedes_obscuration_and_vanes(self) -> None:
        custom = np.ones((32, 32), dtype=np.float64)
        out = make_pupil_amplitude(32, 0.5, SpiderVaneSpec(4, 0.1), custom)
        # Fully open despite obscuration + vanes being set.
        assert out.sum() == pytest.approx(32 * 32, rel=1e-12)

    def test_returns_copy(self) -> None:
        custom = np.ones((16, 16), dtype=np.float64)
        out = make_pupil_amplitude(16, 0.0, None, custom)
        out[0, 0] = 0.0
        assert custom[0, 0] == 1.0  # source not mutated


class TestValidation:
    def test_shape_mismatch_raises(self) -> None:
        bad = np.ones((64, 64), dtype=np.float64)
        with pytest.raises(ValueError, match="shape"):
            make_pupil_amplitude(128, 0.0, None, bad)

    def test_out_of_range_raises(self) -> None:
        bad = np.full((32, 32), 2.0, dtype=np.float64)
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            make_pupil_amplitude(32, 0.0, None, bad)
