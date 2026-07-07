"""Tests for radiant.performance.giqe_sensitivity (Gap 20).

Category C truth anchors:
  1. Hand calculation: d(NIIRS)/d(RER) = 3.32/(0.5·ln10) = 2.88434 at RER=0.5.
  2. Gap-registry example: d(NIIRS)/d(RER) = 3.32/(RER·ln(10)) — same formula
     the registry quotes for the steep-near-baseline behavior.
  3. Central finite difference of compute_giqe5 itself (independent path
     through the implementation).
"""

from __future__ import annotations

import math

import pytest

from radiant.performance.giqe import compute_giqe5
from radiant.performance.giqe_sensitivity import (
    GIQESensitivityError,
    giqe5_sensitivity,
)

GSD = 0.3  # m
RER = 0.5
SNR = 50.0


class TestAnalyticAnchors:
    @pytest.mark.level0
    def test_hand_calc_rer(self) -> None:
        """Anchor 1: 3.32 / (0.5 · ln 10) = 2.883715."""
        s = giqe5_sensitivity(GSD, RER, SNR)
        assert s.dniirs_drer == pytest.approx(2.883715, rel=1e-6)

    @pytest.mark.level0
    def test_hand_calc_gsd(self) -> None:
        """Anchor 1b: -3.32 / (0.3 · ln 10) = -4.806192 per meter."""
        s = giqe5_sensitivity(GSD, RER, SNR)
        assert s.dniirs_dgsd_per_m == pytest.approx(-4.806192, rel=1e-6)

    @pytest.mark.level0
    def test_registry_formula(self) -> None:
        """Anchor 2: matches the gap registry's quoted formula at any RER."""
        for rer in (0.2, 0.5, 0.9):
            s = giqe5_sensitivity(GSD, rer, SNR)
            assert s.dniirs_drer == pytest.approx(3.32 / (rer * math.log(10)), rel=1e-12)


class TestFiniteDifference:
    """Anchor 3: analytic partials agree with central differences of
    compute_giqe5 (independent code path)."""

    def _niirs(self, gsd: float, rer: float, snr: float, h: float = 1.0, g: float = 1.0) -> float:
        return compute_giqe5(gsd, gsd, rer, rer, snr, h, g).niirs

    @pytest.mark.level0
    def test_fd_all_inputs(self) -> None:
        s = giqe5_sensitivity(GSD, RER, SNR)
        eps = 1e-6
        fd_gsd = (self._niirs(GSD + eps, RER, SNR) - self._niirs(GSD - eps, RER, SNR)) / (2 * eps)
        fd_rer = (self._niirs(GSD, RER + eps, SNR) - self._niirs(GSD, RER - eps, SNR)) / (2 * eps)
        fd_snr = (self._niirs(GSD, RER, SNR + eps) - self._niirs(GSD, RER, SNR - eps)) / (2 * eps)
        fd_h = (self._niirs(GSD, RER, SNR, h=1 + eps) - self._niirs(GSD, RER, SNR, h=1 - eps)) / (
            2 * eps
        )
        fd_g = (self._niirs(GSD, RER, SNR, g=1 + eps) - self._niirs(GSD, RER, SNR, g=1 - eps)) / (
            2 * eps
        )
        assert s.dniirs_dgsd_per_m == pytest.approx(fd_gsd, rel=1e-5)
        assert s.dniirs_drer == pytest.approx(fd_rer, rel=1e-5)
        assert s.dniirs_dsnr == pytest.approx(fd_snr, rel=1e-5)
        assert s.dniirs_dh == pytest.approx(fd_h, rel=1e-5)
        assert s.dniirs_dg == pytest.approx(fd_g, rel=1e-5)

    @pytest.mark.level0
    def test_per_percent_exact(self) -> None:
        """per_percent entries reproduce the exact NIIRS delta for +1%."""
        s = giqe5_sensitivity(GSD, RER, SNR)
        exact_rer = self._niirs(GSD, RER * 1.01, SNR) - self._niirs(GSD, RER, SNR)
        exact_gsd = self._niirs(GSD * 1.01, RER, SNR) - self._niirs(GSD, RER, SNR)
        assert s.per_percent["rer"] == pytest.approx(exact_rer, rel=1e-9)
        assert s.per_percent["gsd"] == pytest.approx(exact_gsd, rel=1e-9)


class TestFailureModes:
    def test_zero_gsd_raises(self) -> None:
        with pytest.raises(GIQESensitivityError, match="gsd_m"):
            giqe5_sensitivity(0.0, RER, SNR)

    def test_negative_rer_raises(self) -> None:
        with pytest.raises(GIQESensitivityError, match="rer"):
            giqe5_sensitivity(GSD, -0.1, SNR)

    def test_zero_snr_raises(self) -> None:
        with pytest.raises(GIQESensitivityError, match="snr"):
            giqe5_sensitivity(GSD, RER, 0.0)

    def test_signs(self) -> None:
        """GSD hurts, RER and SNR help — sign sanity."""
        s = giqe5_sensitivity(GSD, RER, SNR)
        assert s.dniirs_dgsd_per_m < 0.0
        assert s.dniirs_drer > 0.0
        assert s.dniirs_dsnr > 0.0
