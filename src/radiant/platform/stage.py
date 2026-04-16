"""PlatformStage — applies jitter blur to the EffectivePSF.

Reads the EffectivePSF produced by OpticsStage, generates a jitter
kernel from the platform jitter parameters, and convolves it into the
PSF. The updated EffectivePSF is stored in
``stage_outputs["platform"]["effective_psf"]`` for PerformanceStage
to read.

Jitter does NOT affect signal or noise — it only degrades spatial
quality (MTF, RER, NIIRS). The chain position is after OpticsStage
and before SpectralIntegrationStage so that EE_box (computed in
SpectralIntegrationStage) reflects the jitter-degraded PSF.

See ``platform/jitter.py`` for the underlying Gaussian jitter model.
"""

from __future__ import annotations

import logging

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.platform.jitter import jitter_kernel_2d, jitter_sigma_focal_m

logger = logging.getLogger(__name__)


class PlatformStage:
    """Chain stage for platform-induced spatial degradation (jitter)."""

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
            logger.debug("No EffectivePSF from optics stage; skipping jitter convolution.")
            return state

        if sigma_x_m == 0.0 and sigma_y_m == 0.0:
            logger.debug("Zero jitter; passing through EffectivePSF unchanged.")
            return state.with_stage_output("platform", "effective_psf", epsf)

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
        epsf_jittered = epsf.with_kernel("jitter", kernel)

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

        return state.with_stage_output("platform", "effective_psf", epsf_jittered)
