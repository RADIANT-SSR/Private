"""Tests for radiant.optics.wavefront.

Category C validation for WavefrontError:
- Marechal Strehl at lambda/14 WFE
- Perfect optics Strehl = 1.0
- Zernike RMS from single coefficient
- OPD map RMS from numpy std
- Field-dependent WFE: at_field, at_field_nearest, chromatic Zernikes
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.optics.element import ElementTransferMode
from radiant.optics.wavefront import FieldWfeSample, WavefrontError, WfeMode

# ---------------------------------------------------------------------------
# Level 0 — Marechal Strehl
# ---------------------------------------------------------------------------


class TestMarechalStrehl:
    """Verify the Marechal approximation S = exp(-(2*pi*sigma/lambda)^2)."""

    @pytest.mark.level0
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

    @pytest.mark.level0
    def test_perfect_optics(self) -> None:
        """Truth anchor 2: zero WFE -> Strehl = 1.0 exactly."""
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.0,
            reference_wavelength_um=0.633,
        )
        assert wfe.strehl_marechal(0.633) == pytest.approx(1.0, abs=1e-15)

    @pytest.mark.level0
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

    @pytest.mark.level0
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

    @pytest.mark.level0
    def test_scalar_rms(self) -> None:
        wfe = WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=0.07,
            reference_wavelength_um=0.633,
        )
        expected_m = 0.07 * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    @pytest.mark.level0
    def test_zernike_single_term(self) -> None:
        """Single Zernike coefficient: RMS = |c|."""
        wfe = WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: 0.1},
            reference_wavelength_um=0.633,
        )
        expected_m = 0.1 * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    @pytest.mark.level0
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

    @pytest.mark.level0
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

    @pytest.mark.level0
    def test_field_dependent_on_axis(self) -> None:
        """field_dependent rms_opd_m returns on-axis RMS."""
        sample_on = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.06, 11: 0.08})
        sample_off = FieldWfeSample(0.5, 0.0, zernike_coeffs={4: 0.2})
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=(sample_on, sample_off),
            reference_wavelength_um=0.633,
        )
        rms_waves = math.sqrt(0.06**2 + 0.08**2)
        expected_m = rms_waves * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)

    @pytest.mark.level0
    def test_field_dependent_no_on_axis_uses_first(self) -> None:
        """If no on-axis point, rms_opd_m uses first sample."""
        sample = FieldWfeSample(0.3, 0.3, zernike_coeffs={4: 0.1})
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=(sample,),
            reference_wavelength_um=0.633,
        )
        expected_m = 0.1 * 0.633e-6
        assert wfe.rms_opd_m() == pytest.approx(expected_m, rel=1e-10)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Input validation for WavefrontError."""

    @pytest.mark.level0
    def test_scalar_missing_rms(self) -> None:
        with pytest.raises(ValueError, match="rms_waves"):
            WavefrontError(mode=WfeMode.SCALAR_RMS)

    @pytest.mark.level0
    def test_negative_rms(self) -> None:
        with pytest.raises(ValueError, match="rms_waves"):
            WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=-0.1)

    @pytest.mark.level0
    def test_zernike_empty(self) -> None:
        with pytest.raises(ValueError, match="zernike_coeffs"):
            WavefrontError(mode=WfeMode.ZERNIKE, zernike_coeffs={})

    @pytest.mark.level0
    def test_opd_map_not_2d(self) -> None:
        with pytest.raises(ValueError, match="2-D"):
            WavefrontError(mode=WfeMode.OPD_MAP, opd_map=np.zeros(10))

    @pytest.mark.level0
    def test_opd_map_missing(self) -> None:
        with pytest.raises(ValueError, match="opd_map"):
            WavefrontError(mode=WfeMode.OPD_MAP)

    @pytest.mark.level0
    def test_field_table_empty(self) -> None:
        with pytest.raises(ValueError, match="field_table"):
            WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=())

    @pytest.mark.level0
    def test_field_table_duplicate_positions(self) -> None:
        s1 = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.1})
        s2 = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.2})
        with pytest.raises(ValueError, match="duplicate"):
            WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=(s1, s2))

    @pytest.mark.level0
    def test_refractive_missing_chromatic_raises(self) -> None:
        sample = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.1})
        with pytest.raises(ValueError, match="REFRACTIVE"):
            WavefrontError(
                mode=WfeMode.FIELD_DEPENDENT,
                field_table=(sample,),
                optical_type=ElementTransferMode.REFRACTIVE,
            )

    @pytest.mark.level0
    def test_refractive_single_wavelength_warns(self) -> None:
        sample = FieldWfeSample(
            0.0, 0.0,
            zernike_coeffs={4: 0.1},
            chromatic_zernikes={0.633: {4: 0.1}},
        )
        with pytest.warns(UserWarning, match="only 1 wavelength"):
            WavefrontError(
                mode=WfeMode.FIELD_DEPENDENT,
                field_table=(sample,),
                optical_type=ElementTransferMode.REFRACTIVE,
            )

    @pytest.mark.level0
    def test_negative_ref_wavelength(self) -> None:
        with pytest.raises(ValueError, match="reference_wavelength_um"):
            WavefrontError(
                mode=WfeMode.SCALAR_RMS,
                rms_waves=0.1,
                reference_wavelength_um=-1.0,
            )

    @pytest.mark.level0
    def test_negative_operating_wavelength(self) -> None:
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.1)
        with pytest.raises(ValueError, match="wavelength_um"):
            wfe.strehl_marechal(-1.0)


# ---------------------------------------------------------------------------
# Field-dependent WFE
# ---------------------------------------------------------------------------


def _make_4point_field_table() -> tuple[FieldWfeSample, ...]:
    """4-point field table mimicking scenario 5.1 (Tom's optical design)."""
    return (
        FieldWfeSample(
            field_x_deg=0.0, field_y_deg=0.0,
            zernike_coeffs={4: 0.05, 5: 0.02, 6: 0.01},
        ),
        FieldWfeSample(
            field_x_deg=0.5, field_y_deg=0.0,
            zernike_coeffs={4: 0.10, 5: 0.06, 7: 0.04},
        ),
        FieldWfeSample(
            field_x_deg=0.0, field_y_deg=0.5,
            zernike_coeffs={4: 0.09, 6: 0.07, 8: 0.03},
        ),
        FieldWfeSample(
            field_x_deg=0.5, field_y_deg=0.5,
            zernike_coeffs={4: 0.15, 5: 0.10, 7: 0.08, 11: 0.05},
        ),
    )


class TestAtField:
    """Tests for WavefrontError.at_field() — exact field lookup."""

    @pytest.mark.level0
    def test_exact_match(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        sample = wfe.at_field(0.5, 0.0)
        assert sample.field_x_deg == 0.5
        assert sample.field_y_deg == 0.0
        assert sample.zernike_coeffs == {4: 0.10, 5: 0.06, 7: 0.04}

    @pytest.mark.level0
    def test_on_axis(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        sample = wfe.at_field(0.0, 0.0)
        assert sample.zernike_coeffs[4] == pytest.approx(0.05, rel=1e-10)

    @pytest.mark.level0
    def test_not_found_raises(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        with pytest.raises(ValueError, match="No field sample"):
            wfe.at_field(0.25, 0.25)

    @pytest.mark.level0
    def test_not_found_lists_available(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        with pytest.raises(ValueError, match=r"\(0\.5, 0\.0\)"):
            wfe.at_field(0.25, 0.25)

    @pytest.mark.level0
    def test_wrong_mode_raises(self) -> None:
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.1)
        with pytest.raises(ValueError, match="FIELD_DEPENDENT"):
            wfe.at_field(0.0, 0.0)

    @pytest.mark.level0
    def test_single_field_point(self) -> None:
        """Single field point is valid (on-axis-only design)."""
        sample = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.05})
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=(sample,))
        result = wfe.at_field(0.0, 0.0)
        assert result is sample


class TestAtFieldNearest:
    """Tests for WavefrontError.at_field_nearest() — nearest lookup."""

    @pytest.mark.level0
    def test_exact_match_no_warning(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sample = wfe.at_field_nearest(0.5, 0.0)
        assert sample.field_x_deg == 0.5

    @pytest.mark.level0
    def test_near_point_no_warning(self) -> None:
        """Within 0.01 deg tolerance — no warning."""
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sample = wfe.at_field_nearest(0.005, 0.005)
        assert sample.field_x_deg == 0.0
        assert sample.field_y_deg == 0.0

    @pytest.mark.level0
    def test_far_point_warns(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        with pytest.warns(UserWarning, match="not be representative"):
            wfe.at_field_nearest(0.25, 0.25)

    @pytest.mark.level0
    def test_returns_nearest(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        # (0.45, 0.05) is closest to (0.5, 0.0)
        sample = wfe.at_field_nearest(0.45, 0.05)
        assert sample.field_x_deg == 0.5
        assert sample.field_y_deg == 0.0

    @pytest.mark.level0
    def test_wrong_mode_raises(self) -> None:
        wfe = WavefrontError(mode=WfeMode.SCALAR_RMS, rms_waves=0.1)
        with pytest.raises(ValueError, match="FIELD_DEPENDENT"):
            wfe.at_field_nearest(0.0, 0.0)


class TestFieldDependentReflective:
    """Reflective systems: single Zernike set across all wavelengths."""

    @pytest.mark.level0
    def test_reflective_is_default(self) -> None:
        table = _make_4point_field_table()
        wfe = WavefrontError(mode=WfeMode.FIELD_DEPENDENT, field_table=table)
        assert wfe.optical_type == ElementTransferMode.REFLECTIVE

    @pytest.mark.level0
    def test_reflective_no_chromatic_ok(self) -> None:
        """Reflective systems don't need chromatic_zernikes."""
        sample = FieldWfeSample(0.0, 0.0, zernike_coeffs={4: 0.1})
        assert sample.chromatic_zernikes is None
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=(sample,),
            optical_type=ElementTransferMode.REFLECTIVE,
        )
        assert wfe.optical_type == ElementTransferMode.REFLECTIVE


class TestFieldDependentRefractive:
    """Refractive systems: wavelength-dependent Zernike coefficients."""

    @pytest.mark.level0
    def test_refractive_with_chromatic(self) -> None:
        """Valid refractive system with multi-wavelength Zernikes."""
        sample = FieldWfeSample(
            0.0, 0.0,
            zernike_coeffs={4: 0.1},
            chromatic_zernikes={
                0.5: {4: 0.12, 5: 0.02},
                0.6: {4: 0.10, 5: 0.01},
                0.8: {4: 0.08},
            },
        )
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=(sample,),
            optical_type=ElementTransferMode.REFRACTIVE,
        )
        assert wfe.optical_type == ElementTransferMode.REFRACTIVE
        assert sample.chromatic_zernikes is not None
        assert len(sample.chromatic_zernikes) == 3

    @pytest.mark.level0
    def test_chromatic_different_coeffs_at_different_wavelengths(self) -> None:
        sample = FieldWfeSample(
            0.0, 0.0,
            zernike_coeffs={4: 0.1},
            chromatic_zernikes={
                0.5: {4: 0.15},
                0.8: {4: 0.05},
            },
        )
        assert sample.chromatic_zernikes is not None
        assert sample.chromatic_zernikes[0.5][4] != sample.chromatic_zernikes[0.8][4]

    @pytest.mark.level0
    def test_4point_refractive_field_table(self) -> None:
        """Scenario 5.1: 4 field points, each with chromatic Zernikes."""
        samples = []
        for fx, fy in [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]:
            samples.append(FieldWfeSample(
                field_x_deg=fx,
                field_y_deg=fy,
                zernike_coeffs={4: 0.1 * (1 + fx + fy)},
                chromatic_zernikes={
                    3.5: {4: 0.12 * (1 + fx + fy)},
                    4.25: {4: 0.10 * (1 + fx + fy)},
                    5.0: {4: 0.08 * (1 + fx + fy)},
                },
            ))
        wfe = WavefrontError(
            mode=WfeMode.FIELD_DEPENDENT,
            field_table=tuple(samples),
            optical_type=ElementTransferMode.REFRACTIVE,
        )
        assert len(wfe.field_table) == 4  # type: ignore[arg-type]
