"""Tests for radiant.optics.wavefront.

Category C validation for WavefrontError:
- Marechal Strehl at lambda/14 WFE
- Perfect optics Strehl = 1.0
- Zernike RMS from single coefficient
- OPD map RMS from numpy std
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.wavefront import WavefrontError, WfeMode

# ---------------------------------------------------------------------------
# Level 0 — Marechal Strehl
# ---------------------------------------------------------------------------


class TestMarechalStrehl:
    """Verify the Marechal approximation S = exp(-(2*pi*sigma/lambda)^2)."""

    def test_lambda_over_14(self) -> None:
        """Truth anchor 1: lambda/14 WFE -> S = exp(-(2*pi*1/14)^2) = 0.818.

        Reference: Mahajan, "Optical Imaging and Aberrations", Table 2.1.
        """
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=1.0 / 14.0,
            reference_wavelength_um=0.633,
        )
        s = wfe.strehl_marechal(0.633)
        expected = math.exp(-(2.0 * math.pi / 14.0) ** 2)
        assert s == pytest.approx(expected, rel=1e-10)
        assert s == pytest.approx(0.8176, abs=1e-3)

    def test_perfect_optics(self) -> None:
        """Truth anchor 2: zero WFE -> Strehl = 1.0 exactly."""
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.0,
            reference_wavelength_um=0.633,
        )
        assert wfe.strehl_marechal(0.633) == pytest.approx(1.0, abs=1e-15)

    def test_large_wfe(self) -> None:
        """Truth anchor 3: 0.5 waves -> S = exp(-pi^2) ≈ 5.17e-5."""
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.5,
            reference_wavelength_um=0.633,
        )
        s = wfe.strehl_marechal(0.633)
        expected = math.exp(-(math.pi) ** 2)
        assert s == pytest.approx(expected, rel=1e-10)

    def test_different_operating_wavelength(self) -> None:
        """WFE at 0.633 um, operating at 4.0 um -> much higher Strehl.

        sigma_OPD = 0.1 * 0.633e-6 m
        phase_var = (2*pi * sigma_OPD / 4.0e-6)^2
        """
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.1,
            reference_wavelength_um=0.633,
        )
        sigma_m = 0.1 * 0.633e-6
        phase_var = (2.0 * math.pi * sigma_m / 4.0e-6) ** 2
        expected = math.exp(-phase_var)
        assert wfe.strehl_marechal(4.0) == pytest.approx(expected, rel=1e-10)


# ---------------------------------------------------------------------------
# RMS OPD
# ---------------------------------------------------------------------------


class TestRmsOpd:
    """Verify rms_opd_m for each mode."""

    def test_scalar_rms(self) -> None:
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.07,
            reference_wavelength_um=0.633,
        )
        expected_m = 0.07 * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    def test_zernike_single_term(self) -> None:
        """Single Zernike coefficient: RMS = |c|."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.1},
            reference_wavelength_um=0.633,
        )
        expected_m = 0.1 * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    def test_zernike_two_terms(self) -> None:
        """Two Zernike coefficients: RMS = sqrt(c1^2 + c2^2)."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.06, 11: 0.08},
            reference_wavelength_um=0.633,
        )
        rms_waves = math.sqrt(0.06**2 + 0.08**2)
        expected_m = rms_waves * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    def test_opd_map(self) -> None:
        """OPD map: RMS = std(map) * lambda_ref."""
        rng = np.random.default_rng(42)
        opd = rng.normal(0.0, 0.05, (64, 64))
        wfe = WavefrontError(
            mode=WfeMode.OPD_MAP,
            opd_map=opd,
            reference_wavelength_um=0.633,
        )
        expected_m = float(np.std(opd)) * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-6)

    def test_field_dependent_raises(self) -> None:
        from radiant.optics.wavefront import FieldWfeSample

        sample = FieldWfeSample(0.0, 0.0, WfeMode.SCALAR_RMS, rms_waves=0.05)
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=(sample,),
        )
        with pytest.raises(NotImplementedError, match="field_dependent"):
            wfe.rms_opd_m()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Input validation for WavefrontError."""

    def test_scalar_missing_rms(self) -> None:
        with pytest.raises(ValueError, match="rms_waves"):
            WavefrontError(mode=WfeMode.SCALAR_RMS)

    def test_negative_rms(self) -> None:
        with pytest.raises(ValueError, match="rms_waves"):
            WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=-0.1)

    def test_zernike_empty(self) -> None:
        with pytest.raises(ValueError, match="zernike_coeffs"):
            WavefrontError(mode=WfeMode.ZERNIKE, zernike_coeffs={})

    def test_opd_map_not_2d(self) -> None:
        with pytest.raises(ValueError, match="2-D"):
            WavefrontError(mode=WfeMode.OPD_MAP, opd_map=np.zeros(10))

    def test_opd_map_missing(self) -> None:
        with pytest.raises(ValueError, match="opd_map"):
            WavefrontError(mode=WfeMode.OPD_MAP)

    def test_field_table_empty(self) -> None:
        with pytest.raises(ValueError, match="field_table"):
            WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=())

    def test_negative_ref_wavelength(self) -> None:
        with pytest.raises(ValueError, match="reference_wavelength_um"):
            WavefrontError(
                mode=WfeMode.SCALAR_RMS,
                rms_waves=0.1,
                reference_wavelength_um=-1.0,
            )

    def test_negative_operating_wavelength(self) -> None:
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.1)
        with pytest.raises(ValueError, match="wavelength_um"):
            wfe.strehl_marechal(-1.0)
