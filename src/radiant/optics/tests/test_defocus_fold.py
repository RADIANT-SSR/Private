"""Level 0: the detector-plane defocus → Noll Z4 fold (CU-379).

A detector-plane displacement δ at working f-number N puts a quadratic
wavefront on the pupil whose edge OPD is the marginal-ray sag
δ(1 − cos u), u = arctan(1/(2N)) — paraxially δ/(8N²). That is the
peak-to-valley of the defocus term, and the textbook depth-of-focus rule
(λ/4 P-V at δ = 2λN²). Noll's Z4 carries P-V = 2√3·a₄, so

    a₄ = δ / (16√3 λ N²)   [waves RMS].

Every number below is a hand calculation, not a value read back from the
implementation.
"""

from __future__ import annotations

import math

import pytest

from radiant.optics.stage import _add_defocus_to_wfe
from radiant.optics.wavefront import WavefrontError, WfeMode

LAM_UM = 4.0
N = 4.0


def _a4(defocus_um: float, f_number: float = N, wavelength_um: float = LAM_UM) -> float:
    wfe = _add_defocus_to_wfe(None, defocus_um, f_number, wavelength_um * 1e-6)
    assert wfe is not None and wfe.zernike_coeffs is not None
    return wfe.zernike_coeffs[4]


class TestDefocusToZ4:
    def test_quarter_wave_pv_at_twice_lambda_n_squared(self) -> None:
        """δ = 2λN² is the classic λ/4 depth of focus: a₄ = (1/4)/(2√3) waves."""
        delta_um = 2.0 * LAM_UM * N**2  # 128 µm
        assert _a4(delta_um) == pytest.approx(0.25 / (2.0 * math.sqrt(3.0)), rel=1e-12)
        assert _a4(delta_um) == pytest.approx(0.0721687836, abs=1e-9)

    def test_peak_to_valley_is_the_paraxial_sag(self) -> None:
        """P-V = 2√3·a₄ must equal δ/(8N²) in waves for any δ."""
        for delta_um in (5.0, 37.0, 128.0, 300.0):
            pv_waves = 2.0 * math.sqrt(3.0) * _a4(delta_um)
            expected = (delta_um / (8.0 * N**2)) / LAM_UM
            assert pv_waves == pytest.approx(expected, rel=1e-12)

    def test_agrees_with_the_exact_marginal_ray_sag(self) -> None:
        """Independent derivation: δ(1 − cos u), u = arctan(1/2N) — paraxial to ~1 %."""
        delta_um = 128.0
        u = math.atan(1.0 / (2.0 * N))
        exact_pv_waves = delta_um * (1.0 - math.cos(u)) / LAM_UM  # 0.24710 waves
        pv_waves = 2.0 * math.sqrt(3.0) * _a4(delta_um)  # 0.25 waves (paraxial)
        assert pv_waves == pytest.approx(exact_pv_waves, rel=0.015)

    def test_marechal_strehl_at_quarter_wave_is_the_classic_0_81(self) -> None:
        """exp[−(2π a₄)²] = 0.8141 at λ/4 P-V defocus (Rayleigh's ≈0.8 criterion)."""
        a4 = _a4(2.0 * LAM_UM * N**2)
        assert math.exp(-((2.0 * math.pi * a4) ** 2)) == pytest.approx(0.81414, abs=2e-5)

    def test_pre_cu379_coefficient_is_excluded(self) -> None:
        """The old δ/(8√3 λ N²) made a configured δ act as 2δ; it is gone, not tolerated."""
        delta_um = 128.0
        old = delta_um * 1e-6 / (8.0 * math.sqrt(3.0) * LAM_UM * 1e-6 * N**2)
        assert _a4(delta_um) == pytest.approx(old / 2.0, rel=1e-12)
        assert _a4(delta_um) != pytest.approx(old, rel=1e-3)

    def test_scales_as_delta_over_n_squared_and_inverse_wavelength(self) -> None:
        base = _a4(64.0, 4.0, 4.0)
        assert _a4(128.0, 4.0, 4.0) == pytest.approx(2.0 * base, rel=1e-12)
        assert _a4(64.0, 8.0, 4.0) == pytest.approx(base / 4.0, rel=1e-12)
        assert _a4(64.0, 4.0, 8.0) == pytest.approx(base / 2.0, rel=1e-12)

    def test_adds_to_an_existing_z4_at_the_wfe_reference_wavelength(self) -> None:
        """Folding onto a Zernike WFE adds the OPD-preserving rescaled Z4."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE, zernike_coeffs={4: 0.05}, reference_wavelength_um=0.633
        )
        out = _add_defocus_to_wfe(wfe, 128.0, N, LAM_UM * 1e-6)
        assert out is not None and out.zernike_coeffs is not None
        # 0.0721688 waves at 4 µm is the same OPD as 0.0721688 × (4/0.633) waves at 0.633 µm.
        assert out.zernike_coeffs[4] == pytest.approx(0.05 + 0.0721687836 * (4.0 / 0.633), rel=1e-9)
