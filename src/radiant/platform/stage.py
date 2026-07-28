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

Smear is ONE relative-motion term (Gap 111): when the user supplies target
kinematics, GeometryStage composes the platform and target velocities into a
single relative LOS angular rate and this stage turns that one rate into the
one smear extent used by *both* Rule-4 paths (the rect PSF kernel and the
``mtf_smear_*`` product terms). Platform-only scenes — every configuration
that predates Gap 111 — keep the velocity/range door in ``smear.py``, which
computes the same rate from ``platform.ground_velocity_m_s`` and the slant
range.

See ``platform/jitter.py``, ``platform/smear.py`` and
``platform/relative_motion_smear.py`` for the underlying models.
"""

from __future__ import annotations

import logging
import math
import warnings

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.core.viewing_triangle import slant_range_from_theta_o_m
from radiant.platform.errors import PlatformValidationError
from radiant.platform.jitter import jitter_kernel_2d, jitter_mtf_1d, jitter_sigma_focal_m
from radiant.platform.kernel_size import odd_kernel_size
from radiant.platform.relative_motion_smear import smear_width_from_los_rate_m
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
            npix_needed = odd_kernel_size(
                int(2 * (4.0 * max_sigma / sample_spacing_m) + 1),
                epsf.data.shape[0],
            )

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

        # --- Smear (relative-motion blur) ---
        # ADR-0006: slant range is derived once by GeometryStage; None for
        # partial fixtures that run PlatformStage without it (CU-096).
        # Gap 111: when a kinematics door was used, GeometryStage also publishes
        # the *relative* LOS angular rate (platform + target), which is the one
        # rate this stage turns into the one smear extent.
        geometry_out = state.stage_outputs.get("geometry", {})
        smear_w_m = self._compute_smear_width(
            params,
            focal_length_m,
            published_slant_m=geometry_out.get("slant_range_m"),
            published_los_rate_rad_s=geometry_out.get("los_angular_rate_rad_s"),
            los_rate_mode=geometry_out.get("los_rate_mode"),
        )
        state = state.with_stage_output("platform", "smear_width_m", smear_w_m)

        if smear_w_m > 0.0:
            sample_spacing_m = epsf.sample_spacing_m

            # Clamping the kernel to the grid is *clipping*, so it owes the caller
            # a UserWarning, not just a log line (Rule 17) — and it must name the
            # consequence, which is a Rule-4 divergence: the PSF path gets a
            # truncated smear while the MTF product keeps the full analytic term,
            # so EE/RER/FWHM understate the blur and the dual-path consistency
            # check will report the disagreement (CU-235).
            psf_extent_m = epsf.data.shape[0] * sample_spacing_m
            if smear_w_m > 0.5 * psf_extent_m:
                warnings.warn(
                    f"PlatformStage: smear width {smear_w_m * 1e6:.1f} µm exceeds "
                    f"half the PSF grid extent ({psf_extent_m * 1e6:.1f} µm), so the "
                    "smear kernel is TRUNCATED to the grid. The PSF path then "
                    "carries less blur than the MTF product's analytic smear term: "
                    "ensquared energy, RER and FWHM are optimistic, and the "
                    "dual-path consistency check will flag the disagreement. "
                    "Reduce spectral_integration.integration_time_s, reduce "
                    "platform.ground_velocity_m_s, or increase the PSF grid "
                    "sampling so the full smear fits.",
                    UserWarning,
                    stacklevel=2,
                )

            # 1-D rect kernel along y (along-track).
            npix_smear = odd_kernel_size(
                int(math.ceil(2.0 * smear_w_m / sample_spacing_m)),
                epsf.data.shape[0],
            )

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
            npix_turb = odd_kernel_size(
                int(math.ceil(8.0 * fwhm_turb_m / sample_spacing_m)),
                epsf.data.shape[0],
            )

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
    def _relative_los_rate_active(los_rate_mode: object) -> bool:
        """True when GeometryStage resolved the LOS rate through a kinematics door.

        Gap 111 gives the rate two user doors (K1 ``geometry.los_angular_rate_rad_s``
        direct, K2 the ``geometry.target_speed_m_s`` triple); with neither set,
        GeometryStage still publishes a rate, but a *platform-only* one — flagged
        by the ``"platform-only"`` prefix of ``los_rate_mode``
        (``radiant.geometry.modes.resolve_los_rate``).

        The distinction is provenance, not physics (ADR-0011 decision 8: nothing
        branches on the scene): both branches compute the same smear from the
        same relative rate, and in the platform-only case the two rates are equal
        by construction (proved in ``tests/integration/test_moving_target_smear.py``
        and ``test_los_rate_zero_drift.py``).  The gate exists so that an existing
        configuration — which never sets a kinematics parameter — keeps running the
        byte-for-byte identical velocity/range door it ran before Gap 111,
        including that door's CU-085 guards, rather than a numerically-equal but
        differently-guarded rewrite (plan §3 principle 3: zero drift).
        """
        return isinstance(los_rate_mode, str) and not los_rate_mode.startswith("platform-only")

    @staticmethod
    def _compute_smear_width(
        params: ParameterSet,
        focal_length_m: float,
        published_slant_m: float | None = None,
        published_los_rate_rad_s: float | None = None,
        los_rate_mode: object = None,
    ) -> float:
        """Determine smear width on the focal plane [m].

        Priority: ``smear_length_um`` > published relative LOS rate (Gap 111,
        only when a kinematics door was used) > ``ground_velocity_m_s`` over
        the slant range > 0 (no smear).
        """
        relative_rate_active = PlatformStage._relative_los_rate_active(los_rate_mode)

        # Direct override.
        smear_direct_m: float = params.get("platform.smear_length_um")
        if smear_direct_m > 0.0:
            if relative_rate_active:
                warnings.warn(
                    "PlatformStage: platform.smear_length_um > 0 overrides the "
                    "relative line-of-sight rate GeometryStage resolved from the "
                    "target-kinematics inputs "
                    f"(los_rate_mode={los_rate_mode!r}), so the target motion does "
                    "not affect the smear. Clear platform.smear_length_um (set it "
                    "to 0) to use the kinematics-derived smear.",
                    UserWarning,
                    stacklevel=2,
                )
            return smear_direct_m

        # Gap 111: one relative-motion smear from the one published rate.
        if relative_rate_active:
            return PlatformStage._smear_from_published_rate(
                params, published_los_rate_rad_s, focal_length_m, los_rate_mode
            )

        # Velocity-based computation — the platform-only door, unchanged.
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
        # published value when available (ADR-0006), else derive it from the
        # canonical target-side path zenith θ_o for partial fixtures. This
        # matches what GeometryStage publishes (CU-096): geometry.path_zenith_rad
        # is θ_o, so it must go through slant_range_from_theta_o_m — NOT the
        # sensor-off-nadir-η helper slant_range_spherical_m.
        if published_slant_m is not None and published_slant_m > 0.0:
            slant_m = float(published_slant_m)
        else:
            try:
                theta_o_rad: float = params.get("geometry.path_zenith_rad")
            except (KeyError, TypeError):
                theta_o_rad = 0.0
            try:
                h_target_m: float = params.get("geometry.target_altitude_m")
            except (KeyError, TypeError):
                h_target_m = 0.0
            slant_m = slant_range_from_theta_o_m(theta_o_rad, altitude_m, h_target_m)
            if slant_m <= 0.0:
                slant_m = altitude_m

        return smear_width_m(velocity, t_int_s, focal_length_m, slant_m)

    @staticmethod
    def _smear_from_published_rate(
        params: ParameterSet,
        published_los_rate_rad_s: float | None,
        focal_length_m: float,
        los_rate_mode: object,
    ) -> float:
        """Gap 111 arm: smear extent from the published relative LOS rate.

        The rate already carries **both** endpoints' motion (``v_rel =
        v_target − v_sensor``, projected perpendicular to the LOS and divided by
        the slant range), so this is the whole relative-motion smear — the
        platform contribution is inside it and must not be added again.
        """
        if published_los_rate_rad_s is None:
            # Unreachable through GeometryStage: the only scene with a None rate
            # is coincident endpoints, which resolves to a "platform-only" mode
            # (and mode K2 raises there). Named rather than silently zeroed
            # (Rule 17) so a future publisher change surfaces here.
            raise PlatformValidationError(
                "PlatformStage: the geometry stage reported LOS-rate mode "
                f"{los_rate_mode!r} — a target-kinematics door — but published "
                "no rate (los_angular_rate_rad_s is None). A kinematics-derived "
                "smear cannot be computed without the rate. Give the scene a "
                "sensor↔target separation, or set platform.smear_length_um "
                "directly."
            )

        try:
            t_int_s: float = params.get("spectral_integration.integration_time_s")
        except (KeyError, TypeError):
            t_int_s = 0.0
        if t_int_s <= 0.0:
            warnings.warn(
                "PlatformStage: a target-kinematics input set the line-of-sight "
                f"rate to {published_los_rate_rad_s:.6g} rad/s, but "
                "spectral_integration.integration_time_s is missing or ≤ 0, so "
                "the relative-motion smear is not computed (returned 0). Set a "
                "positive integration time, or provide platform.smear_length_um "
                "directly (CU-085).",
                UserWarning,
                stacklevel=2,
            )
            return 0.0

        return smear_width_from_los_rate_m(published_los_rate_rad_s, t_int_s, focal_length_m)
