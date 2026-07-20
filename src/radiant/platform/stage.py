"""PlatformStage — applies jitter and smear blur to the EffectivePSF.

Reads the EffectivePSF produced by OpticsStage, generates jitter,
smear, and turbulence kernels from the platform parameters, and
convolves them into the PSF. The updated EffectivePSF is stored in
``stage_outputs["platform"]["effective_psf"]`` for PerformanceStage
to read.

This stage also computes ``EE_box`` (ensquared energy in a 1×1 pixel)
from the fully degraded PSF and stores it in
``stage_outputs["platform"]["EE_box"]``. The chain position — after
OpticsStage and before SpectralIntegrationStage — exists precisely so
that the EE_box applied to point-source and sub-pixel radiometry
(applied once, in SpectralIntegrationStage, per Rule 9) includes
jitter, smear, and turbulence blur. For extended scenes EE_box = 1.0
(Rule 9: never applied in the extended regime).

Beyond the EE_box coupling, jitter and smear do NOT affect signal or
noise — they degrade spatial quality (MTF, RER, NIIRS).

See ``platform/jitter.py`` and ``platform/smear.py`` for the
underlying models.
"""

from __future__ import annotations

import logging
import math
import warnings

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.geometry import slant_range_spherical_m
from radiant.core.parameters import ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.platform.jitter import jitter_kernel_2d, jitter_mtf_1d, jitter_sigma_focal_m
from radiant.platform.smear import smear_kernel_1d, smear_mtf_1d, smear_width_m
from radiant.platform.turbulence_kernel import kolmogorov_kernel_2d

logger = logging.getLogger(__name__)


def _compute_ee_box(regime: RadiometricRegime | str | None, epsf: object) -> float:
    """EE_box for the finalized regime, from the degraded EffectivePSF.

    Extended regime → 1.0 (EE_box not applied, Rule 9).
    Point/sub-pixel → ensquared energy in 1×1 pixel from the PSF as
    degraded by all kernels applied so far (pixel aperture, diffusion,
    defocus, jitter, smear, turbulence).
    If no EffectivePSF or no regime is available, defaults to 1.0.

    Note: the EE computation itself lives on ``EffectivePSF`` (duck-typed
    here — Rule 11 forbids importing ``radiant.optics`` from this stage).
    """
    if regime is None or epsf is None:
        return 1.0
    if isinstance(regime, str):
        regime = RadiometricRegime(regime)
    if regime == RadiometricRegime.EXTENDED:
        return 1.0
    return float(epsf.ensquared_energy_nxn(1))  # type: ignore[attr-defined]


# Canonical display units for this stage's scalar ``stage_outputs`` (CU-118) —
# declared next to the ``with_stage_output(...)`` emission sites and aggregated by
# ``radiant.api.stage_output_units``. "" marks a dimensionless numeric (bare number).
OUTPUT_UNITS: dict[str, str] = {
    "jitter_sigma_x_m": "m",
    "jitter_sigma_y_m": "m",
    "smear_width_m": "m",
    "EE_box": "",
}


class PlatformStage:
    """Chain stage for platform-induced spatial degradation (jitter + smear)."""

    @property
    def name(self) -> str:
        return "platform"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # --- Determine jitter sigma in x and y (canonical: rad) ---
        axes_mode: str = params.get("platform.jitter_axes")

        if axes_mode == "anisotropic":
            jitter_x_rad: float = params.get("platform.jitter_rms_x_urad")
            jitter_y_rad: float = params.get("platform.jitter_rms_y_urad")
        else:
            jitter_iso_rad: float = params.get("platform.jitter_rms_urad")
            jitter_x_rad = jitter_iso_rad
            jitter_y_rad = jitter_iso_rad

        # --- Convert angular jitter to focal-plane sigma [m] ---
        focal_length_m: float = params.get("optics.focal_length_m")

        sigma_x_m = jitter_sigma_focal_m(jitter_x_rad, focal_length_m)
        sigma_y_m = jitter_sigma_focal_m(jitter_y_rad, focal_length_m)

        state = state.with_stage_output("platform", "jitter_sigma_x_m", sigma_x_m)
        state = state.with_stage_output("platform", "jitter_sigma_y_m", sigma_y_m)

        # --- Apply jitter kernel to EffectivePSF ---
        epsf = state.stage_outputs.get("optics", {}).get("effective_psf")

        if epsf is None:
            logger.debug("No EffectivePSF from optics stage; skipping platform kernels.")
            return state.with_stage_output("platform", "EE_box", 1.0)

        if sigma_x_m != 0.0 or sigma_y_m != 0.0:
            # Kernel size: cover ±4σ, at the PSF sample spacing, capped to PSF grid.
            sample_spacing_m = epsf.sample_spacing_m
            max_sigma = max(sigma_x_m, sigma_y_m)
            npix_needed = int(2 * (4.0 * max_sigma / sample_spacing_m) + 1)
            # Ensure odd.
            if npix_needed % 2 == 0:
                npix_needed += 1
            # Cap to PSF grid size.
            npix_needed = min(npix_needed, epsf.data.shape[0])
            # Ensure at least 3.
            npix_needed = max(npix_needed, 3)

            kernel = jitter_kernel_2d(npix_needed, sample_spacing_m, sigma_x_m, sigma_y_m)
            epsf = epsf.with_kernel("jitter", kernel)

            logger.info(
                "Jitter applied: σ_x=%.2f µm (%.3f pix), σ_y=%.2f µm (%.3f pix), kernel %dx%d",
                sigma_x_m * 1e6,
                sigma_x_m / epsf.pixel_pitch_m,
                sigma_y_m * 1e6,
                sigma_y_m / epsf.pixel_pitch_m,
                npix_needed,
                npix_needed,
            )

        # --- Smear (along-track motion blur) ---
        # ADR-0006: slant range is derived once by GeometryStage; None for
        # partial fixtures that run PlatformStage without it (CU-096).
        published_slant = state.stage_outputs.get("geometry", {}).get("slant_range_m")
        smear_w_m = self._compute_smear_width(
            params, focal_length_m, published_slant_m=published_slant
        )
        state = state.with_stage_output("platform", "smear_width_m", smear_w_m)

        if smear_w_m > 0.0:
            sample_spacing_m = epsf.sample_spacing_m

            # Warn if smear is very large relative to PSF grid.
            psf_extent_m = epsf.data.shape[0] * sample_spacing_m
            if smear_w_m > 0.5 * psf_extent_m:
                logger.warning(
                    "Smear width (%.1f µm) exceeds half the PSF grid extent "
                    "(%.1f µm). Kernel will be clamped to grid size.",
                    smear_w_m * 1e6,
                    psf_extent_m * 1e6,
                )

            # 1-D rect kernel along y (along-track).
            npix_smear = int(math.ceil(2.0 * smear_w_m / sample_spacing_m)) | 1
            npix_smear = min(npix_smear, epsf.data.shape[0])
            npix_smear = max(npix_smear, 3)

            kern_1d = smear_kernel_1d(npix_smear, sample_spacing_m, smear_w_m)

            # Extend to 2-D: delta_x ⊗ rect_y.
            # kern_1d is along y; delta along x is a single-pixel Kronecker.
            kernel_2d = np.zeros((npix_smear, npix_smear), dtype=np.float64)
            c = npix_smear // 2
            kernel_2d[:, c] = kern_1d  # y-axis smear, x-axis delta
            # Normalize (should already sum to 1, but ensure).
            total = kernel_2d.sum()
            if total > 0.0:
                kernel_2d /= total

            epsf = epsf.with_kernel("smear", kernel_2d)

            logger.info(
                "Smear applied: width=%.2f µm (%.3f pix), kernel %dx%d",
                smear_w_m * 1e6,
                smear_w_m / epsf.pixel_pitch_m,
                npix_smear,
                npix_smear,
            )

        # --- Turbulence kernel (Kolmogorov long-exposure) ---
        atm_out = state.stage_outputs.get("atmosphere", {})
        r0_m = atm_out.get("r0_m")
        if r0_m is not None and r0_m > 0.0:
            sample_spacing_m = epsf.sample_spacing_m
            wavelength_m = epsf.wavelength_um * 1e-6

            # Kernel size: estimate FWHM ≈ 0.98 λ/r0 on focal plane,
            # cover ±4 FWHM, ensure odd and capped to PSF grid.
            fwhm_turb_m = 0.98 * wavelength_m * focal_length_m / r0_m
            npix_turb = int(math.ceil(8.0 * fwhm_turb_m / sample_spacing_m)) | 1
            npix_turb = min(npix_turb, epsf.data.shape[0])
            npix_turb = max(npix_turb, 3)

            k_turb = kolmogorov_kernel_2d(
                npix_turb, sample_spacing_m, wavelength_m, r0_m, focal_length_m
            )
            epsf = epsf.with_kernel("turbulence", k_turb)

            logger.info(
                "Turbulence applied: r0=%.3f m, FWHM_turb=%.2f µm, kernel %dx%d",
                r0_m,
                fwhm_turb_m * 1e6,
                npix_turb,
                npix_turb,
            )

        # --- MTF product path: jitter and smear analytic MTFs ---
        freq_mrad = state.spatial_freq_cycles_per_mrad
        if freq_mrad is not None:
            # Convert cycles/mrad → cycles/m on the focal plane.
            # f_focal [cycles/m] = f_angular [cycles/mrad] / (focal_length_m * 1e-3)
            freq_m = freq_mrad / (focal_length_m * 1e-3)

            # Jitter MTF (anisotropic: different sigma per axis).
            if sigma_x_m > 0.0 or sigma_y_m > 0.0:
                mtf_jitter_x = (
                    jitter_mtf_1d(freq_m, sigma_x_m) if sigma_x_m > 0.0 else np.ones_like(freq_m)
                )
                mtf_jitter_y = (
                    jitter_mtf_1d(freq_m, sigma_y_m) if sigma_y_m > 0.0 else np.ones_like(freq_m)
                )
            else:
                mtf_jitter_x = np.ones_like(freq_m)
                mtf_jitter_y = np.ones_like(freq_m)
            state = state.with_mtf("mtf_jitter_x", mtf_jitter_x)
            state = state.with_mtf("mtf_jitter_y", mtf_jitter_y)

            # Smear MTF (along-track = y-axis degradation).
            if smear_w_m > 0.0:
                mtf_smear_y = smear_mtf_1d(freq_m, smear_w_m)
                mtf_smear_x = np.ones_like(freq_m)
            else:
                mtf_smear_x = np.ones_like(freq_m)
                mtf_smear_y = np.ones_like(freq_m)
            state = state.with_mtf("mtf_smear_x", mtf_smear_x)
            state = state.with_mtf("mtf_smear_y", mtf_smear_y)

        # --- EE_box from the fully degraded PSF (Rule 9 coupling) ---
        regime = state.stage_outputs.get("optics", {}).get("regime")
        ee_box = _compute_ee_box(regime, epsf)
        state = state.with_stage_output("platform", "EE_box", ee_box)

        return state.with_stage_output("platform", "effective_psf", epsf)

    @staticmethod
    def _compute_smear_width(
        params: ParameterSet,
        focal_length_m: float,
        published_slant_m: float | None = None,
    ) -> float:
        """Determine smear width on the focal plane [m].

        Priority: smear_length_um > ground_velocity_m_s > 0 (no smear).
        """
        # Direct override.
        smear_direct_m: float = params.get("platform.smear_length_um")
        if smear_direct_m > 0.0:
            return smear_direct_m

        # Velocity-based computation.
        velocity: float = params.get("platform.ground_velocity_m_s")
        if velocity <= 0.0:
            return 0.0

        # Need altitude and integration time. CU-085: the user explicitly set
        # a ground velocity, so a missing/zero altitude or integration time
        # means the requested velocity smear is silently dropped — warn rather
        # than return 0 quietly.
        try:
            altitude_m: float = params.get("geometry.sensor_altitude_m")
        except (KeyError, TypeError):
            altitude_m = 0.0
        if altitude_m <= 0.0:
            warnings.warn(
                "PlatformStage: platform.ground_velocity_m_s > 0 but "
                "geometry.sensor_altitude_m is missing or ≤ 0, so the velocity "
                "smear is not computed (returned 0). Set a positive altitude, "
                "or provide platform.smear_length_um directly (CU-085).",
                UserWarning,
                stacklevel=2,
            )
            return 0.0

        try:
            t_int_s: float = params.get("spectral_integration.integration_time_s")
        except (KeyError, TypeError):
            t_int_s = 0.0
        if t_int_s <= 0.0:
            warnings.warn(
                "PlatformStage: platform.ground_velocity_m_s > 0 but "
                "spectral_integration.integration_time_s is missing or ≤ 0, so "
                "the velocity smear is not computed (returned 0). Set a positive "
                "integration time, or provide platform.smear_length_um "
                "directly (CU-085).",
                UserWarning,
                stacklevel=2,
            )
            return 0.0

        # Use slant range for off-nadir consistency — the GeometryStage
        # published value when available (ADR-0006), else the legacy
        # derivation for partial fixtures (CU-096).
        if published_slant_m is not None and published_slant_m > 0.0:
            slant_m = float(published_slant_m)
        else:
            try:
                zenith_rad: float = params.get("geometry.path_zenith_rad")
            except (KeyError, TypeError):
                zenith_rad = 0.0
            slant_m = slant_range_spherical_m(altitude_m, zenith_rad)
            if slant_m <= 0.0:
                slant_m = altitude_m

        return smear_width_m(velocity, t_int_s, focal_length_m, slant_m)
