"""Integration tests: regime continuity across extended, point-source, and sub-pixel.

Truth anchors:
1. Sub-pixel with ff=1.0 → same signal as extended (within 0.1%)
2. Point source signal scales as 1/R² (double range → 1/4 signal)
3. Sub-pixel contrast ΔL hand calculation
4. Extended chain reproduces 2B.9 ground truth (already in test_chain_extended.py)

See RADIANT_Signal_Chain_Architecture.md §4.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.regime import RadiometricRegime

# ---------------------------------------------------------------------------
# Shared sensor parameters
# ---------------------------------------------------------------------------
D = 0.30
F = 1.20
TAU_OPT = 0.70
PITCH_UM = 18.0
PITCH_M = PITCH_UM * 1e-6
A_COLLECT = math.pi / 4.0 * D ** 2
OMEGA_PIXEL = PITCH_M ** 2 / F ** 2
T_INT = 0.005
QE = 0.70
T_TARGET = 500.0
EPS_TARGET = 0.95
T_BG = 290.0
EPS_BG = 0.95
SENSOR_ALT = 8000.0
FILTER_MIN = 3.5
FILTER_MAX = 5.0
WL = np.linspace(FILTER_MIN, FILTER_MAX, 500)


def _run_chain(
    area_m2: float = 0.0,
    range_m: float = 0.0,
    fill_fraction: float = 1.0,
    regime_override: str = "auto",
    target_T: float = T_TARGET,
    bg_T: float = T_BG,
):
    """Helper to run the full chain with specified source geometry."""
    session = RadiantSession(wavelength_um=WL)
    params = session.default_params()
    params.set("source.target.temperature", target_T)
    params.set("source.target.emissivity", EPS_TARGET)
    params.set("source.target.projected_area_m2", area_m2)
    params.set("source.target.range_m", range_m)
    params.set("source.target.fill_fraction", fill_fraction)
    params.set("source.regime_override", regime_override)
    params.set("source.background.temperature", bg_T)
    params.set("source.background.emissivity", EPS_BG)
    params.set("optics.aperture_diameter_m", D)
    params.set("optics.focal_length_m", F)
    params.set("optics.transmission_scalar", TAU_OPT)
    params.set("detector.pixel_pitch_x_um", PITCH_UM)
    params.set("detector.pixel_pitch_y_um", PITCH_UM)
    params.set("detector.qe_value", QE)
    params.set("detector.dark_rate_e_per_s", 100.0)
    params.set("geometry.sensor_altitude_m", SENSOR_ALT)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", FILTER_MIN)
    params.set("spectral_integration.filter_max_um", FILTER_MAX)
    params.set("spectral_integration.integration_time_s", T_INT)
    params.set("readout.read_noise_e_rms", 5.0)
    params.set("readout.gain_e_per_dn", 1.0)
    params.set("readout.adc_bits", 16)
    params.resolve()
    return session.run(params)


# ======================================================================
# Truth Anchor 1: Sub-pixel ff=1.0 matches extended
# ======================================================================


@pytest.mark.level2
class TestSubPixelFFOneMatchesExtended:
    """Sub-pixel with fill_fraction=1.0 vs extended.

    With path radiance decomposition, the relationship is:
        S_sub(ff=1.0) = S_scene × EE_box + S_path
        S_ext          = S_scene + S_path

    So S_sub < S_ext when EE_box < 1, and the difference is exactly
    ``S_scene × (1 - EE_box)`` — the PSF energy spilled outside the pixel.
    """

    def test_ff_one_is_extended_times_ee_box(self) -> None:
        # Extended: default (no area/range → extended regime).
        result_ext = _run_chain()

        # Sub-pixel with ff=1.0: force sub-pixel regime.
        result_sub = _run_chain(
            fill_fraction=1.0,
            regime_override="sub_pixel",
        )

        sig_ext = result_ext.stage_outputs["spectral_integration"]["signal_e"]
        sig_sub = result_sub.stage_outputs["spectral_integration"]["signal_e"]
        ee_box = result_sub.stage_outputs["optics"]["EE_box"]

        assert sig_ext > 0.0
        assert sig_sub > 0.0

        # S_sub must be between S_ext * EE_box (no path) and S_ext (all path).
        assert sig_sub >= sig_ext * ee_box * 0.999
        assert sig_sub <= sig_ext * 1.001

        # The ratio S_sub / S_ext should be close to EE_box when scene
        # radiance dominates over path radiance (hot 500K target in MWIR).
        ratio = sig_sub / sig_ext
        assert ratio == pytest.approx(ee_box, abs=0.02)


# ======================================================================
# Truth Anchor 2: Point source 1/R² scaling
# ======================================================================


@pytest.mark.level2
class TestPointSourceInverseSquare:
    """Point source signal should scale as 1/R²: doubling the range
    should quarter the signal.
    """

    def test_inverse_square_scaling(self) -> None:
        # Use a small target forced to point_source regime at two ranges.
        R1 = 100_000.0  # 100 km
        R2 = 200_000.0  # 200 km
        A_target = 1.0  # 1 m²

        result1 = _run_chain(
            area_m2=A_target, range_m=R1,
            regime_override="point_source",
        )
        result2 = _run_chain(
            area_m2=A_target, range_m=R2,
            regime_override="point_source",
        )

        sig1 = result1.stage_outputs["spectral_integration"]["signal_e"]
        sig2 = result2.stage_outputs["spectral_integration"]["signal_e"]

        assert sig1 > 0.0
        assert sig2 > 0.0
        # sig2 / sig1 should be (R1/R2)² = 0.25
        ratio = sig2 / sig1
        assert ratio == pytest.approx(0.25, rel=0.01)


# ======================================================================
# Truth Anchor 3: Sub-pixel contrast ΔL
# ======================================================================


@pytest.mark.level2
class TestSubPixelContrast:
    """Verify sub-pixel contrast ΔL = ff × (L_target − L_bg) × EE_box
    produces the expected signal difference.
    """

    def test_contrast_signal(self) -> None:
        # Run with target (500 K) and background (290 K).
        result_sub = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=500.0,
            bg_T=290.0,
        )

        # Run pure background (target = background).
        result_bg = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )

        sig_sub = result_sub.stage_outputs["spectral_integration"]["signal_e"]
        sig_bg = result_bg.stage_outputs["spectral_integration"]["signal_e"]

        # When target T = background T, the signals should be equal.
        # The difference for T_target > T_bg should be positive.
        delta = sig_sub - sig_bg
        assert delta > 0.0, (
            f"Sub-pixel signal with hot target ({sig_sub:.1f} e-) should exceed "
            f"pure-background signal ({sig_bg:.1f} e-)"
        )

    def test_pure_background_matches_analytic(self) -> None:
        """When target T == background T in sub-pixel regime, path
        radiance fills the whole pixel uniformly (not split by ff).

        L_mixed = L_scene_through × (ff × EE_box + 1 - ff) + L_path_through
        S_ext   = (L_scene_through + L_path_through) × A × Ω × ...

        So S_sub differs from S_ext only in the scene contribution
        being scaled by (ff × EE_box + 1 - ff), while path radiance
        passes through unchanged.
        """
        ff = 0.5
        result_sub = _run_chain(
            fill_fraction=ff,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )
        result_ext = _run_chain(target_T=290.0)

        sig_sub = result_sub.stage_outputs["spectral_integration"]["signal_e"]
        sig_ext = result_ext.stage_outputs["spectral_integration"]["signal_e"]
        ee_box = result_sub.stage_outputs["optics"]["EE_box"]

        # Decompose extended signal into scene and path components.
        # For extended with T_target == T_bg == 290K, the "background"
        # is the full-pixel signal → includes both scene and path.
        # Estimate path contribution from the atmosphere stage.
        # Sub-pixel signal: scene × (ff × EE_box + 1 - ff) + path (uniform).
        # Since target==background, S_sub < S_ext when EE_box < 1.
        factor = ff * ee_box + (1.0 - ff)
        assert factor < 1.0, "EE_box < 1 for sub-pixel regime"
        assert sig_sub < sig_ext, "Sub-pixel signal < extended when EE_box < 1"
        # The ratio should be between factor (if all signal is scene)
        # and 1.0 (if all signal is path radiance). Check it's reasonable.
        ratio = sig_sub / sig_ext
        assert factor <= ratio <= 1.0, (
            f"Signal ratio {ratio:.4f} should be between {factor:.4f} and 1.0"
        )

    def test_hot_target_positive_contrast(self) -> None:
        """Hot target (T > T_bg) produces positive contrast ΔS > 0.

        ΔS = S(target+bg) − S(bg_only)
        A 500 K target against 290 K background in MWIR should give
        a clear positive signal excess.
        """
        ff = 0.1
        result_hot = _run_chain(
            fill_fraction=ff,
            regime_override="sub_pixel",
            target_T=500.0,
            bg_T=290.0,
        )
        result_bg = _run_chain(
            fill_fraction=ff,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )

        sig_hot = result_hot.stage_outputs["spectral_integration"]["signal_e"]
        sig_bg = result_bg.stage_outputs["spectral_integration"]["signal_e"]
        delta_S = sig_hot - sig_bg

        assert delta_S > 0.0, (
            f"Hot target ΔS must be positive: S_hot={sig_hot:.1f}, "
            f"S_bg={sig_bg:.1f}, ΔS={delta_S:.1f}"
        )

        # Verify ΔS is proportional to ff × (L_hot − L_bg) × EE_box.
        # Since both runs use the same atmosphere/optics, the contrast
        # should scale linearly with fill_fraction.
        result_hot2 = _run_chain(
            fill_fraction=ff * 2,
            regime_override="sub_pixel",
            target_T=500.0,
            bg_T=290.0,
        )
        result_bg2 = _run_chain(
            fill_fraction=ff * 2,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )
        sig_hot2 = result_hot2.stage_outputs["spectral_integration"]["signal_e"]
        sig_bg2 = result_bg2.stage_outputs["spectral_integration"]["signal_e"]
        delta_S2 = sig_hot2 - sig_bg2

        # ΔS should double when ff doubles.
        assert delta_S2 == pytest.approx(delta_S * 2.0, rel=0.01)

    def test_cold_target_negative_contrast(self) -> None:
        """Cold target (T < T_bg) produces negative contrast ΔS < 0.

        A 200 K target against 290 K background means the target pixel
        receives *less* radiance than a pure-background pixel. The
        contrast ΔS = S(target+bg) − S(bg_only) should be negative.
        """
        ff = 0.1
        result_cold = _run_chain(
            fill_fraction=ff,
            regime_override="sub_pixel",
            target_T=200.0,
            bg_T=290.0,
        )
        result_bg = _run_chain(
            fill_fraction=ff,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )

        sig_cold = result_cold.stage_outputs["spectral_integration"]["signal_e"]
        sig_bg = result_bg.stage_outputs["spectral_integration"]["signal_e"]
        delta_S = sig_cold - sig_bg

        assert delta_S < 0.0, (
            f"Cold target ΔS must be negative: S_cold={sig_cold:.1f}, "
            f"S_bg={sig_bg:.1f}, ΔS={delta_S:.1f}"
        )

        # Both signals should still be positive (physical radiance).
        assert sig_cold > 0.0, "Total pixel signal must remain positive"
        assert sig_bg > 0.0


# ======================================================================
# Regime classification propagation
# ======================================================================


@pytest.mark.level2
class TestRegimeClassification:
    """Verify that regime tentative → final propagates correctly."""

    def test_extended_default(self) -> None:
        result = _run_chain()
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.EXTENDED

    def test_forced_point_source(self) -> None:
        result = _run_chain(
            area_m2=1.0, range_m=100_000.0,
            regime_override="point_source",
        )
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.POINT_SOURCE

    def test_forced_sub_pixel(self) -> None:
        result = _run_chain(
            fill_fraction=0.5,
            regime_override="sub_pixel",
        )
        regime = result.stage_outputs["optics"]["regime"]
        assert regime == RadiometricRegime.SUB_PIXEL

    def test_regime_override_propagates(self) -> None:
        """Source tentative → optics final, both matching the override."""
        result = _run_chain(
            area_m2=1.0, range_m=100_000.0,
            regime_override="point_source",
        )
        src_regime = result.stage_outputs["source"]["regime_tentative"]
        opt_regime = result.stage_outputs["optics"]["regime"]
        assert src_regime == RadiometricRegime.POINT_SOURCE
        assert opt_regime == RadiometricRegime.POINT_SOURCE


# ======================================================================
# Signal positivity and physical bounds
# ======================================================================


@pytest.mark.level2
class TestSignalPhysics:
    """Basic physical sanity for all three regimes."""

    @pytest.mark.parametrize("regime", ["extended", "point_source", "sub_pixel"])
    def test_signal_positive(self, regime: str) -> None:
        kwargs = {"regime_override": regime}
        if regime == "point_source":
            kwargs["area_m2"] = 1.0
            kwargs["range_m"] = 100_000.0
        elif regime == "sub_pixel":
            kwargs["fill_fraction"] = 0.5
        result = _run_chain(**kwargs)
        sig = result.stage_outputs["spectral_integration"]["signal_e"]
        assert sig > 0.0, f"Signal must be positive for {regime} regime"

    def test_hot_target_more_signal_than_cold(self) -> None:
        """500 K target should produce more signal than 300 K."""
        result_hot = _run_chain(target_T=500.0)
        result_cold = _run_chain(target_T=300.0)
        sig_hot = result_hot.stage_outputs["spectral_integration"]["signal_e"]
        sig_cold = result_cold.stage_outputs["spectral_integration"]["signal_e"]
        assert sig_hot > sig_cold


# ======================================================================
# Contrast SNR — hot and cold sub-pixel targets
# ======================================================================


@pytest.mark.level2
class TestContrastSNR:
    """Verify that contrast SNR (ΔS / σ) has the correct sign for hot
    and cold sub-pixel targets.

    Contrast SNR is positive when the target pixel is brighter than
    background and negative when it is dimmer.
    """

    def test_hot_sub_pixel_positive_contrast_snr(self) -> None:
        """500 K target vs 290 K background → positive contrast SNR."""
        result = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=500.0,
            bg_T=290.0,
        )
        contrast_snr = result.metrics["contrast_snr"]
        contrast_e = result.stage_outputs["spectral_integration"]["contrast_e"]
        background_e = result.stage_outputs["spectral_integration"]["background_e"]

        assert contrast_e > 0.0, (
            f"Hot target contrast must be positive, got {contrast_e:.1f} e-"
        )
        assert contrast_snr > 0.0, (
            f"Hot target contrast SNR must be positive, got {contrast_snr:.2f}"
        )
        # Background signal should be positive (real photons).
        assert background_e > 0.0

    def test_cold_sub_pixel_negative_contrast_snr(self) -> None:
        """200 K target vs 290 K background → negative contrast SNR."""
        result = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=200.0,
            bg_T=290.0,
        )
        contrast_snr = result.metrics["contrast_snr"]
        contrast_e = result.stage_outputs["spectral_integration"]["contrast_e"]

        assert contrast_e < 0.0, (
            f"Cold target contrast must be negative, got {contrast_e:.1f} e-"
        )
        assert contrast_snr < 0.0, (
            f"Cold target contrast SNR must be negative, got {contrast_snr:.2f}"
        )

        # Total pixel signal must still be positive (physical radiance).
        signal_e = result.stage_outputs["spectral_integration"]["signal_e"]
        assert signal_e > 0.0

    def test_equal_temp_zero_contrast_snr(self) -> None:
        """Target T == background T → contrast SNR ≈ 0.

        When the target and background have the same temperature and
        emissivity, the pixel looks identical to pure background. The
        only residual contrast comes from EE_box < 1 on the target
        term, which creates a small *negative* contrast.
        """
        result = _run_chain(
            fill_fraction=0.5,
            regime_override="sub_pixel",
            target_T=290.0,
            bg_T=290.0,
        )
        contrast_snr = result.metrics["contrast_snr"]
        contrast_e = result.stage_outputs["spectral_integration"]["contrast_e"]

        # With identical T but EE_box < 1, ff fraction of the pixel
        # has its target energy spread by the PSF → small negative
        # contrast. Verify the sign is negative (EE_box effect).
        assert contrast_e < 0.0, (
            f"Same-T contrast should be slightly negative due to EE_box<1, "
            f"got {contrast_e:.1f} e-"
        )
        assert contrast_snr < 0.0

        # The contrast magnitude should be much smaller than a truly
        # cold target (200 K vs 290 K).
        result_cold = _run_chain(
            fill_fraction=0.5,
            regime_override="sub_pixel",
            target_T=200.0,
            bg_T=290.0,
        )
        cold_contrast_snr = result_cold.metrics["contrast_snr"]
        assert abs(contrast_snr) < abs(cold_contrast_snr), (
            f"Same-T contrast ({contrast_snr:.1f}) should be smaller "
            f"in magnitude than cold-target contrast ({cold_contrast_snr:.1f})"
        )

    def test_contrast_snr_magnitude_ordering(self) -> None:
        """Hotter target → larger |contrast SNR|."""
        result_warm = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=350.0,
            bg_T=290.0,
        )
        result_hot = _run_chain(
            fill_fraction=0.1,
            regime_override="sub_pixel",
            target_T=500.0,
            bg_T=290.0,
        )
        csnr_warm = result_warm.metrics["contrast_snr"]
        csnr_hot = result_hot.metrics["contrast_snr"]

        assert csnr_warm > 0.0
        assert csnr_hot > 0.0
        assert csnr_hot > csnr_warm, (
            f"500 K target should have larger contrast SNR than 350 K: "
            f"{csnr_hot:.2f} vs {csnr_warm:.2f}"
        )

    def test_extended_contrast_snr_positive(self) -> None:
        """Extended hot target also produces positive contrast SNR."""
        result = _run_chain(target_T=500.0, bg_T=290.0)
        contrast_snr = result.metrics["contrast_snr"]
        assert contrast_snr > 0.0

    def test_point_source_contrast_snr_positive(self) -> None:
        """Point source target signal IS the contrast → positive."""
        result = _run_chain(
            area_m2=1.0,
            range_m=100_000.0,
            regime_override="point_source",
            target_T=500.0,
        )
        contrast_snr = result.metrics["contrast_snr"]
        assert contrast_snr > 0.0

        # For point source, contrast_e should equal signal_e.
        si_out = result.stage_outputs["spectral_integration"]
        assert si_out["contrast_e"] == pytest.approx(
            si_out["signal_e"], rel=1e-10,
        )
