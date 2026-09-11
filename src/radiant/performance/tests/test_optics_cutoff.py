"""Level 0 tests for the optical diffraction cutoff (performance/optics_cutoff.py).

Truth values are hand calculations from ``f_cutoff = 1 / (λ · F#)`` [cycles/m]
and its angular form ``D / (λ · 1e3)`` [cycles/mrad] — never values produced by
other RADIANT code.
"""

from __future__ import annotations

import pytest

from radiant.core.exceptions import RadiantError
from radiant.performance.optics_cutoff import (
    optics_cutoff_freq,
    optics_cutoff_freq_cycles_per_mrad,
)
from radiant.performance.system_mtf import nyquist_freq


@pytest.mark.level0
class TestOpticsCutoffFocalPlane:
    """f_cutoff = 1 / (λ · F#) [cycles/m]."""

    def test_lwir_f2_hand_calculation(self) -> None:
        # λ = 10 µm = 1e-5 m, F# = 2 → 1 / (1e-5 · 2) = 50 000 cycles/m (= 50 cy/mm).
        assert optics_cutoff_freq(10e-6, 2.0) == pytest.approx(5.0e4, rel=1e-12)

    def test_visible_f4_hand_calculation(self) -> None:
        # λ = 0.5 µm = 5e-7 m, F# = 4 → 1 / (5e-7 · 4) = 500 000 cycles/m (= 500 cy/mm).
        assert optics_cutoff_freq(0.5e-6, 4.0) == pytest.approx(5.0e5, rel=1e-12)

    def test_inverse_scaling_in_wavelength_and_f_number(self) -> None:
        base = optics_cutoff_freq(4e-6, 3.0)
        assert optics_cutoff_freq(8e-6, 3.0) == pytest.approx(base / 2.0, rel=1e-12)
        assert optics_cutoff_freq(4e-6, 6.0) == pytest.approx(base / 2.0, rel=1e-12)


@pytest.mark.level0
class TestOpticsCutoffAngular:
    """f_cutoff [cycles/mrad] = focal / (λ · F# · 1e3) = D / (λ · 1e3)."""

    def test_matches_aperture_over_wavelength(self) -> None:
        # D = 0.3 m, λ = 10 µm → D/λ = 30 000 cycles/rad = 30 cycles/mrad.
        # F# = focal / D = 1.2 / 0.3 = 4.
        got = optics_cutoff_freq_cycles_per_mrad(10e-6, 4.0, 1.2)
        assert got == pytest.approx(30.0, rel=1e-12)

    def test_angular_cutoff_is_focal_plane_cutoff_times_focal_over_1e3(self) -> None:
        # Same rad → mrad convention PerformanceStage applies to the Nyquist output.
        focal_m, f_num, lam_m = 0.9, 5.6, 4.0e-6
        expected = optics_cutoff_freq(lam_m, f_num) * focal_m / 1e3
        assert optics_cutoff_freq_cycles_per_mrad(lam_m, f_num, focal_m) == pytest.approx(
            expected, rel=1e-12
        )

    def test_same_angular_convention_as_nyquist_output(self) -> None:
        # The Nyquist stage output is f_ny [cy/m] · focal / 1e3; the cutoff must share
        # that convention, else the two cannot be compared on one axis. Q = λ·F#/pitch,
        # so at Q = 2 the cutoff sits exactly at Nyquist.
        pitch_m, f_num, focal_m = 18e-6, 4.0, 1.2
        lam_m = 2.0 * pitch_m / f_num  # Q = 2 → λ = 2·pitch/F#  = 9 µm
        ny_mrad = nyquist_freq(pitch_m) * focal_m / 1e3
        cutoff_mrad = optics_cutoff_freq_cycles_per_mrad(lam_m, f_num, focal_m)
        assert cutoff_mrad == pytest.approx(ny_mrad, rel=1e-12)


@pytest.mark.level0
class TestOpticsCutoffFailureModes:
    @pytest.mark.parametrize("lam_m", [0.0, -1e-6])
    def test_non_positive_wavelength_raises(self, lam_m: float) -> None:
        with pytest.raises(RadiantError, match="wavelength_m must be positive"):
            optics_cutoff_freq(lam_m, 4.0)

    @pytest.mark.parametrize("f_num", [0.0, -2.0])
    def test_non_positive_f_number_raises(self, f_num: float) -> None:
        with pytest.raises(RadiantError, match="f_number must be positive"):
            optics_cutoff_freq(4e-6, f_num)

    @pytest.mark.parametrize("focal_m", [0.0, -1.0])
    def test_non_positive_focal_length_raises(self, focal_m: float) -> None:
        with pytest.raises(RadiantError, match="focal_length_m must be positive"):
            optics_cutoff_freq_cycles_per_mrad(4e-6, 4.0, focal_m)
