"""Level 0 tests for the scalar-RMS → low-order Zernike expansion (CU-355).

Key equations under test (written before the implementation, Rule 18):

1. Noll orthonormality: for a coefficient set {c_j} of Noll-normalized
   Zernikes on the unobscured unit disk, the piston-removed pupil RMS is
   sqrt(sum c_j^2). Equal budget over 8 terms → c_j = rms / sqrt(8).
2. Obscuration renormalization: on an annular pupil the standard Zernikes
   are no longer orthonormal, so the coefficients are rescaled to make the
   realized piston-removed RMS over the transmitting annulus equal the
   requested budget exactly.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.optics.errors import OpticsValidationError
from radiant.optics.scalar_rms import SCALAR_RMS_NOLL_TERMS, scalar_rms_zernike_coeffs
from radiant.optics.zernike_opd import evaluate_zernike_opd


def _pupil_rms_waves(coeffs: dict[int, float], npix: int, obscuration_ratio: float) -> float:
    """Piston-removed RMS of the realized OPD over the transmitting pupil."""
    opd = evaluate_zernike_opd(coeffs, npix, obscuration_ratio)
    # The canonical pupil mask, via the piston polynomial (1 inside, 0 outside).
    mask = evaluate_zernike_opd({1: 1.0}, npix, obscuration_ratio) > 0.5
    return float(np.std(opd[mask]))


class TestTermSet:
    @pytest.mark.level0
    def test_terms_are_low_order_image_degrading(self) -> None:
        """Z4–Z11 only: piston/tip/tilt (Z1–Z3) do not degrade the image."""
        assert SCALAR_RMS_NOLL_TERMS == (4, 5, 6, 7, 8, 9, 10, 11)

    @pytest.mark.level0
    def test_equal_budget_per_term_unobscured(self) -> None:
        """Truth anchor (hand calculation): c_j = rms / sqrt(8) on the disk.

        Noll normalization makes each term unit-RMS on the unit disk, so an
        equal split of the variance budget gives every coefficient the same
        magnitude rms/sqrt(8). The discrete-grid renormalization may shift
        this by the sampling error only (< 1 %).
        """
        rms = 0.08
        coeffs = scalar_rms_zernike_coeffs(rms, obscuration_ratio=0.0)
        expected = rms / math.sqrt(8.0)
        assert set(coeffs) == set(SCALAR_RMS_NOLL_TERMS)
        for c in coeffs.values():
            assert c == pytest.approx(expected, rel=0.01)


class TestRealizedRms:
    @pytest.mark.level0
    def test_realized_pupil_rms_matches_budget_unobscured(self) -> None:
        rms = 0.10
        coeffs = scalar_rms_zernike_coeffs(rms, obscuration_ratio=0.0)
        realized = _pupil_rms_waves(coeffs, npix=512, obscuration_ratio=0.0)
        assert realized == pytest.approx(rms, rel=1e-3)

    @pytest.mark.level0
    def test_realized_pupil_rms_matches_budget_obscured(self) -> None:
        """On the annulus the coefficients rescale so the RMS still hits budget."""
        rms = 0.10
        eps = 0.30
        coeffs = scalar_rms_zernike_coeffs(rms, obscuration_ratio=eps)
        realized = _pupil_rms_waves(coeffs, npix=512, obscuration_ratio=eps)
        assert realized == pytest.approx(rms, rel=1e-3)

    @pytest.mark.level0
    def test_rms_scales_linearly(self) -> None:
        c1 = scalar_rms_zernike_coeffs(0.05, obscuration_ratio=0.0)
        c2 = scalar_rms_zernike_coeffs(0.10, obscuration_ratio=0.0)
        for j in SCALAR_RMS_NOLL_TERMS:
            assert c2[j] == pytest.approx(2.0 * c1[j], rel=1e-12)


class TestDeterminismAndEdges:
    @pytest.mark.level0
    def test_deterministic_no_rng(self) -> None:
        """Bit-identical output on repeated calls — a fixed constant set."""
        a = scalar_rms_zernike_coeffs(0.07, obscuration_ratio=0.2)
        b = scalar_rms_zernike_coeffs(0.07, obscuration_ratio=0.2)
        assert a == b

    @pytest.mark.level0
    def test_zero_rms_returns_empty(self) -> None:
        assert scalar_rms_zernike_coeffs(0.0, obscuration_ratio=0.0) == {}

    @pytest.mark.level0
    def test_negative_rms_rejected(self) -> None:
        with pytest.raises(OpticsValidationError, match="rms_waves"):
            scalar_rms_zernike_coeffs(-0.05, obscuration_ratio=0.0)

    @pytest.mark.level0
    def test_high_obscuration_warns_via_zernike_path(self) -> None:
        """ε > 0.30 still surfaces the annular-orthogonality warning downstream."""
        coeffs = scalar_rms_zernike_coeffs(0.05, obscuration_ratio=0.35)
        with pytest.warns(UserWarning, match="NOT orthogonal"):
            evaluate_zernike_opd(coeffs, 128, 0.35)

    @pytest.mark.level0
    def test_normalization_does_not_emit_duplicate_warning(self) -> None:
        """The internal normalization pass is silent; the warning belongs to
        the actual pupil evaluation, not the coefficient construction."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            scalar_rms_zernike_coeffs(0.05, obscuration_ratio=0.35)
