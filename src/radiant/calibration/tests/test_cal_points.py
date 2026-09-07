"""Level 0 — cal-temperature → cal-signal mapping (plan §3.1).

The mapping under test: ``S(T_cal) = S_scene · Bq(T_cal) / Bq(T_scene)``
where ``Bq(T)`` is the band-integrated PHOTON radiance (signal electrons
count photons, not energy). The reference values here are computed with
literal CODATA constants and an independent trapezoid integral — never with
RADIANT code (Rule 18).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration.cal_points import cal_point_signal_e
from radiant.calibration.errors import CalibrationValidationError

# Literal constants (CODATA 2018) — deliberately NOT radiant.core.constants.
_H = 6.62607015e-34  # J s
_C = 2.99792458e8  # m/s
_KB = 1.380649e-23  # J/K


def _band_photon_radiance_ref(t_K: float, lam_lo_um: float, lam_hi_um: float) -> float:
    """Independent reference: ∫ B(λ,T)/E_photon dλ, trapezoid, 4001 points."""
    lam_um = np.linspace(lam_lo_um, lam_hi_um, 4001)
    lam_m = lam_um * 1e-6
    x = _H * _C / (lam_m * _KB * t_K)
    b = (2.0 * _H * _C**2 / lam_m**5) / np.expm1(x) * 1e-6  # W/m²/sr/µm
    e_photon = _H * _C / lam_m  # J
    return float(np.trapezoid(b / e_photon, lam_um))


class TestCalPointSignal:
    def test_identity_at_scene_temperature(self) -> None:
        s = cal_point_signal_e(
            t_cal_K=300.0,
            scene_temp_K=300.0,
            scene_signal_e=5.0e4,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert s == pytest.approx(5.0e4, rel=1e-9)

    def test_lwir_ratio_matches_independent_integral(self) -> None:
        """Truth anchor: 310 K vs 300 K over 8–12 µm, photon-weighted."""
        ratio_ref = _band_photon_radiance_ref(310.0, 8.0, 12.0) / _band_photon_radiance_ref(
            300.0, 8.0, 12.0
        )
        s = cal_point_signal_e(
            t_cal_K=310.0,
            scene_temp_K=300.0,
            scene_signal_e=1.0e4,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert s == pytest.approx(1.0e4 * ratio_ref, rel=1e-3)

    def test_mwir_ratio_matches_independent_integral(self) -> None:
        """MWIR is far steeper in T than LWIR — the ratio is regime-sensitive."""
        ratio_ref = _band_photon_radiance_ref(320.0, 3.5, 5.0) / _band_photon_radiance_ref(
            300.0, 3.5, 5.0
        )
        s = cal_point_signal_e(
            t_cal_K=320.0,
            scene_temp_K=300.0,
            scene_signal_e=1.0e4,
            lam_min_um=3.5,
            lam_max_um=5.0,
        )
        assert s == pytest.approx(1.0e4 * ratio_ref, rel=1e-3)
        assert ratio_ref > 1.5  # MWIR: +20 K far more than doubles nothing — steep band

    def test_hotter_cal_point_gives_more_signal(self) -> None:
        lo = cal_point_signal_e(
            t_cal_K=290.0,
            scene_temp_K=300.0,
            scene_signal_e=1.0e4,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        hi = cal_point_signal_e(
            t_cal_K=310.0,
            scene_temp_K=300.0,
            scene_signal_e=1.0e4,
            lam_min_um=8.0,
            lam_max_um=12.0,
        )
        assert lo < 1.0e4 < hi

    def test_nonpositive_temperature_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="temperature"):
            cal_point_signal_e(
                t_cal_K=0.0,
                scene_temp_K=300.0,
                scene_signal_e=1.0e4,
                lam_min_um=8.0,
                lam_max_um=12.0,
            )

    def test_inverted_band_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="band"):
            cal_point_signal_e(
                t_cal_K=310.0,
                scene_temp_K=300.0,
                scene_signal_e=1.0e4,
                lam_min_um=12.0,
                lam_max_um=8.0,
            )

    def test_nonpositive_scene_signal_rejected(self) -> None:
        with pytest.raises(CalibrationValidationError, match="scene_signal_e"):
            cal_point_signal_e(
                t_cal_K=310.0,
                scene_temp_K=300.0,
                scene_signal_e=0.0,
                lam_min_um=8.0,
                lam_max_um=12.0,
            )
