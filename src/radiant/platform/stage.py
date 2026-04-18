"""PlatformStage — applies jitter and smear blur to the EffectivePSF.

Reads the EffectivePSF produced by OpticsStage, generates jitter and
smear kernels from the platform parameters, and convolves them into the
PSF. The updated EffectivePSF is stored in
``stage_outputs["platform"]["effective_psf"]`` for PerformanceStage
to read.

Jitter and smear do NOT affect signal or noise — they only degrade
spatial quality (MTF, RER, NIIRS). The chain position is after
OpticsStage and before SpectralIntegrationStage so that EE_box
(computed in SpectralIntegrationStage) reflects the degraded PSF.

See ``platform/jitter.py`` and ``platform/smear.py`` for the
underlying models.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.geometry import slant_range_spherical_m
from radiant.core.parameters import ParameterSet
from radiant.platform.jitter import jitter_kernel_2d, jitter_sigma_focal_m
from radiant.platform.smear import smear_kernel_1d, smear_width_m

logger = logging.getLogger(__name__)


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
            return state

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
                "Jitter applied: σ_x=%.2f µm (%.3f pix), σ_y=%.2f µm (%.3f pix), "
                "kernel %dx%d",
                sigma_x_m * 1e6,
                sigma_x_m / epsf.pixel_pitch_m,
                sigma_y_m * 1e6,
                sigma_y_m / epsf.pixel_pitch_m,
                npix_needed,
                npix_needed,
            )

        # --- Smear (along-track motion blur) ---
        smear_w_m = self._compute_smear_width(params, focal_length_m)
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

        return state.with_stage_output("platform", "effective_psf", epsf)

    @staticmethod
    def _compute_smear_width(
        params: ParameterSet,
        focal_length_m: float,
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

        # Need altitude and integration time.
        try:
            altitude_m: float = params.get("geometry.sensor_altitude_m")
        except (KeyError, TypeError):
            logger.debug(
                "Smear: ground_velocity set but no altitude; skipping."
            )
            return 0.0

        if altitude_m <= 0.0:
            return 0.0

        try:
            t_int_s: float = params.get("spectral_integration.integration_time_s")
        except (KeyError, TypeError):
            logger.debug(
                "Smear: ground_velocity set but no integration_time; skipping."
            )
            return 0.0

        if t_int_s <= 0.0:
            return 0.0

        # Use slant range for off-nadir consistency.
        try:
            zenith_rad: float = params.get("geometry.path_zenith_rad")
        except (KeyError, TypeError):
            zenith_rad = 0.0

        slant_m = slant_range_spherical_m(altitude_m, zenith_rad)
        if slant_m <= 0.0:
            slant_m = altitude_m

        return smear_width_m(velocity, t_int_s, focal_length_m, slant_m)
