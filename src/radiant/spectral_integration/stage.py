"""SpectralIntegrationStage — collapses spectral radiance to in-band photoelectrons.

This is the single point in the chain where spectral arrays become
per-pixel scalars (CLAUDE.md Rule 8). It is also the single point
where ``EE_box`` enters the radiometric calculation (Rule 9) — but
only for point-source and sub-pixel regimes.

Signal equations by regime:

Extended:
    photon_rate(λ) = L_post_optics(λ) · A_collect · Ω_pixel · (λ / hc)
    signal_e = ∫ photon_rate(λ) · QE(λ) dλ · t_int

Point source:
    photon_rate(λ) = L_post_optics(λ) · A_collect · (A_target / R²) · (λ / hc)
    signal_e = ∫ photon_rate(λ) · QE(λ) dλ · t_int · EE_box

Sub-pixel:
    L_mixed(λ) = ff · L_target_post(λ) · EE_box + (1 − ff) · L_bg_post(λ)
    photon_rate(λ) = L_mixed(λ) · A_collect · Ω_pixel · (λ / hc)
    signal_e = ∫ photon_rate(λ) · QE(λ) dλ · t_int

Produces
--------
Frame ``"photoelectrons"`` with ``in_band_value`` = total
photoelectrons per pixel per integration [e⁻].
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance, planck_spectral_radiance_dT
from radiant.core.chain import ChainState
from radiant.core.constants import hc
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime

logger = logging.getLogger(__name__)


class SpectralIntegrationStage:
    """Chain stage for spectral-to-scalar integration."""

    @property
    def name(self) -> str:
        return "spectral_integration"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # Read optics stage outputs.
        optics_out = state.stage_outputs["optics"]
        A_collect: float = optics_out["A_collect"]
        Omega_pixel: float = optics_out["Omega_pixel"]
        regime = optics_out["regime"]

        # EE_box comes from PlatformStage (computed from the fully
        # degraded PSF: jitter, smear, turbulence included). Fall back to
        # an optics-level EE_box for partial-chain states that skip
        # PlatformStage.
        platform_out = state.stage_outputs.get("platform", {})
        EE_box_maybe = platform_out.get("EE_box", optics_out.get("EE_box"))

        # Normalise regime to enum (handle legacy string values).
        if isinstance(regime, str):
            regime = RadiometricRegime(regime)

        if EE_box_maybe is None:
            if regime == RadiometricRegime.EXTENDED:
                EE_box_maybe = 1.0  # never applied in extended regime (Rule 9)
            else:
                raise RuntimeError(
                    "SpectralIntegrationStage: no EE_box found in "
                    "stage_outputs['platform'] or stage_outputs['optics'] "
                    f"but regime is '{regime.value}', which requires EE_box "
                    "coupling (Rule 9). Run PlatformStage before "
                    "SpectralIntegrationStage, or inject an EE_box stage "
                    "output for partial-chain tests."
                )
        EE_box: float = EE_box_maybe

        # Guard: EE_box != 1.0 in extended regime is a programming error.
        if regime == RadiometricRegime.EXTENDED and EE_box != 1.0:
            raise RuntimeError(
                "SpectralIntegrationStage: EE_box != 1.0 but regime is "
                f"'extended' (EE_box={EE_box}). In extended-scene mode, "
                "EE_box must not be applied (Rule 9). This is a programming "
                "error in PlatformStage."
            )

        # Read post-optics spectral radiance.
        post_optics = state.frames["post_optics"]
        L = post_optics.spectral_radiance
        if L is None:
            raise ValueError(
                "SpectralIntegrationStage: 'post_optics' frame has no spectral_radiance."
            )

        if np.any(np.isnan(L)):
            raise ValueError(
                "SpectralIntegrationStage: 'post_optics' spectral_radiance "
                "contains NaN values. Check upstream stages for invalid inputs."
            )

        wl = state.wavelength_um
        lam_m = wl * 1.0e-6  # µm → m

        # Filter bandpass (top-hat).
        lam_min: float = params.get("spectral_integration.filter_min_um")
        lam_max: float = params.get("spectral_integration.filter_max_um")
        t_int: float = params.get("spectral_integration.integration_time_s")

        # QE: check if the API layer pre-evaluated a spectral QE curve
        # and passed it via stage_outputs (for tabulated QE). Otherwise
        # fall back to the scalar qe_value parameter.
        pre_qe = state.stage_outputs.get("spectral_integration", {}).get("qe_curve")
        if pre_qe is not None:
            qe_curve = np.asarray(pre_qe, dtype=np.float64)
            qe_value = float(np.mean(qe_curve))
        else:
            qe_value: float = params.get("detector.qe_value")
            qe_curve = np.full_like(wl, qe_value)

        # --- Compute photon rate based on regime ---

        if regime == RadiometricRegime.EXTENDED:
            # Extended: L · A_collect · Ω_pixel · (λ / hc)
            photon_rate = L * A_collect * Omega_pixel * (lam_m / hc)

        elif regime == RadiometricRegime.POINT_SOURCE:
            # Point source: target contribution only (no path radiance).
            # S = L_target_only · τ_opt · A_collect · (A_target/R²) · (λ/hc)
            # The at_aperture_target frame bundles L_target · τ_up + L_path_up;
            # isolate the target-only term by subtracting L_path_up.
            source_out = state.stage_outputs["source"]
            A_target: float = source_out["projected_area_m2"]
            R: float = source_out["range_m"]
            if A_target is None or R is None or R <= 0.0:
                raise ValueError(
                    "SpectralIntegrationStage: point_source regime requires "
                    "projected_area_m2 and range_m from SourceStage. "
                    f"Got A_target={A_target}, R={R}."
                )

            L_aperture_target = state.frames["at_aperture_target"].spectral_radiance
            if L_aperture_target is None:
                raise ValueError(
                    "SpectralIntegrationStage: 'at_aperture_target' frame has no spectral_radiance."
                )
            atm_out = state.stage_outputs["atmosphere"]
            L_path_up = atm_out["L_path"]
            tau_opt: float = optics_out["tau_opt"]

            # Target-only at aperture (strip the path-radiance contribution),
            # then transmit through the optics.
            L_target_only_at_aperture = L_aperture_target - L_path_up
            L_target_post = L_target_only_at_aperture * tau_opt

            Omega_target = A_target / (R * R)
            photon_rate = L_target_post * A_collect * Omega_target * (lam_m / hc)

        elif regime == RadiometricRegime.SUB_PIXEL:
            # Sub-pixel: mix target and background radiances.
            # Path radiance fills the whole pixel uniformly and must NOT
            # be split by fill_fraction or subjected to EE_box.
            #
            # New-frame decomposition (Stage 4):
            #   at_aperture_target    = L_target · τ_up + L_path_up
            #   at_aperture_background = L_bg · τ_full_up + L_path_full + …
            #
            # Pure target contribution = at_aperture_target − L_path_up
            # Pure background contribution = at_aperture_background − L_path_full
            # Path radiance is added back once, unweighted by ff.
            source_out = state.stage_outputs["source"]
            fill_fraction: float = source_out["fill_fraction"]

            atm_out = state.stage_outputs["atmosphere"]
            atm_q = atm_out["atm_quantities"]
            L_path_up = atm_out["L_path"]
            L_path_full = np.asarray(atm_q.L_path_full)
            tau_opt: float = optics_out["tau_opt"]

            L_aperture_target = state.frames["at_aperture_target"].spectral_radiance
            if L_aperture_target is None:
                raise ValueError(
                    "SpectralIntegrationStage: 'at_aperture_target' frame has no spectral_radiance."
                )

            bg_frame = state.frames.get("at_aperture_background")
            if bg_frame is not None and bg_frame.spectral_radiance is not None:
                L_aperture_bg = bg_frame.spectral_radiance
                L_bg_only_at_aperture = L_aperture_bg - L_path_full
            else:
                # No BackgroundDescriptor — matrix Decision #13.  The
                # sub-pixel regime still needs a (1 − ff) term; fall back
                # to zero background radiance.
                L_bg_only_at_aperture = np.zeros_like(L_aperture_target)

            L_target_only_at_aperture = L_aperture_target - L_path_up

            L_target_through = L_target_only_at_aperture * tau_opt
            L_bg_through = L_bg_only_at_aperture * tau_opt
            L_path_through = L_path_up * tau_opt

            # L_mixed = ff·L_target·EE_box + (1-ff)·L_bg + L_path
            # EE_box applies to target contribution only (Rule 9).
            # Path radiance is uniform across the pixel (not fill-fraction weighted).
            L_mixed = (
                fill_fraction * L_target_through * EE_box
                + (1.0 - fill_fraction) * L_bg_through
                + L_path_through
            )

            photon_rate = L_mixed * A_collect * Omega_pixel * (lam_m / hc)

        else:
            raise ValueError(f"SpectralIntegrationStage: unknown regime {regime!r}.")

        # electron rate: × QE
        e_rate = photon_rate * qe_curve  # [e-/s/pixel/µm]

        # Apply filter bandpass mask and integrate.
        mask = (wl >= lam_min) & (wl <= lam_max)
        wl_band = wl[mask]
        e_rate_band = e_rate[mask]

        if wl_band.size < 2:
            raise ValueError(
                f"SpectralIntegrationStage: filter [{lam_min}, {lam_max}] µm "
                f"contains fewer than 2 wavelength samples in the grid. "
                "Increase grid density or widen the filter."
            )
        if wl_band.size < 10:
            warnings.warn(
                f"SpectralIntegrationStage: filter [{lam_min}, {lam_max}] µm "
                f"has only {wl_band.size} wavelength samples. Integration "
                "accuracy may be poor. Consider increasing grid density.",
                UserWarning,
                stacklevel=2,
            )

        e_per_s = float(np.trapezoid(e_rate_band, wl_band))  # e-/s/pixel

        # For point source, EE_box is a post-integration multiplicative factor.
        if regime == RadiometricRegime.POINT_SOURCE:
            signal_e = e_per_s * t_int * EE_box
        else:
            # Extended: no EE_box. Sub-pixel: already mixed into L_mixed.
            signal_e = e_per_s * t_int

        # --- Exact NEDT support (Gap 43): dS/dT of the in-band signal ---
        # The temperature sensitivity of the signal is the Planck
        # log-derivative (dB/dT)/B of the target's blackbody function,
        # weighted by the actual in-band signal spectrum and integrated over
        # the band. This is the exact band integral; it reduces *exactly* to
        # the single-λ Planck-factor approximation
        # (performance.nedt.compute_nedt_from_snr) in the narrow-band limit.
        # Stored for PerformanceStage, which prefers it over the
        # approximation when available.
        try:
            target_temp_K: float = params.get("source.target.temperature")
        except (KeyError, TypeError):
            target_temp_K = float("nan")
        if np.isfinite(target_temp_K) and target_temp_K > 0.0:
            b_planck = planck_spectral_radiance(wl, target_temp_K)
            dbdt_planck = planck_spectral_radiance_dT(wl, target_temp_K)
            log_deriv = np.zeros_like(wl)
            nonzero = b_planck > 0.0
            log_deriv[nonzero] = dbdt_planck[nonzero] / b_planck[nonzero]  # [1/K]
            ds_dt_rate = e_rate * log_deriv  # [e-/s/µm/K]
            ds_dt_per_s = float(np.trapezoid(ds_dt_rate[mask], wl_band))
            if regime == RadiometricRegime.POINT_SOURCE:
                ds_dt_e_per_K = ds_dt_per_s * t_int * EE_box
            else:
                ds_dt_e_per_K = ds_dt_per_s * t_int
        else:
            ds_dt_e_per_K = None

        # --- Background reference and contrast ---
        # Compute what a pure-background pixel would produce. The
        # contrast ΔS = signal_e − background_e is the detection-
        # relevant quantity: positive for hot targets, negative for
        # cold targets relative to background.
        bg_frame_c = state.frames.get("at_aperture_background")
        has_background = bg_frame_c is not None and bg_frame_c.spectral_radiance is not None

        if regime == RadiometricRegime.POINT_SOURCE:
            # signal_e is already the target-only contribution (no
            # background in the point source equation). The target
            # signal IS the excess over background.
            contrast_e = signal_e
            background_e = 0.0
        elif has_background:
            # Extended and sub-pixel: compute background-only pixel signal.
            # The at_aperture_background frame already bundles
            # L_bg · τ_full_up + L_path_full; transmit through the optics
            # once to reach the FPA.
            tau_opt_bg: float = optics_out["tau_opt"]
            L_bg_post = bg_frame_c.spectral_radiance * tau_opt_bg
            bg_photon_rate = L_bg_post * A_collect * Omega_pixel * (lam_m / hc)
            bg_e_rate = bg_photon_rate * qe_curve
            bg_e_rate_band = bg_e_rate[mask]
            bg_e_per_s = float(np.trapezoid(bg_e_rate_band, wl_band))
            background_e = bg_e_per_s * t_int
            contrast_e = signal_e - background_e
        else:
            # No background descriptor (matrix Decision #13 — computed-
            # extended cells skip the bg photon reference entirely).
            background_e = 0.0
            contrast_e = signal_e

        frame = RadiometricFrame(
            name="photoelectrons",
            wavelength_um=wl,
            in_band_value=signal_e,
            in_band_unit="e-",
            notes=(
                f"∫ QE·L·A·Ω·λ/hc dλ × t_int; "
                f"filter [{lam_min}–{lam_max}] µm, regime={regime.value}"
            ),
        )

        state = state.with_frame(frame)
        state = state.with_stage_output(
            "spectral_integration",
            "signal_e",
            signal_e,
        )
        state = state.with_stage_output(
            "spectral_integration",
            "e_rate_per_s",
            e_per_s,
        )
        state = state.with_stage_output(
            "spectral_integration",
            "background_e",
            background_e,
        )
        state = state.with_stage_output(
            "spectral_integration",
            "contrast_e",
            contrast_e,
        )
        if ds_dt_e_per_K is not None:
            state = state.with_stage_output(
                "spectral_integration",
                "ds_dt_e_per_K",
                ds_dt_e_per_K,
            )

        # --- Nearfield and stray light electron integration ---
        # Convert irradiance at FPA [W/m²/µm] to electrons per pixel.
        # E(λ) × A_pixel × QE(λ) × (λ/hc) → e-/s/µm, integrate → × t_int.
        pixel_pitch_x: float = params.get("detector.pixel_pitch_x_um")
        pixel_pitch_y: float = params.get("detector.pixel_pitch_y_um")
        A_pixel = pixel_pitch_x * pixel_pitch_y  # m² (already in canonical)

        nearfield_e = 0.0
        stray_e = 0.0

        nf_sd = optics_out.get("nearfield_irradiance_at_fpa")
        if nf_sd is not None:
            nf_vals = nf_sd.values if hasattr(nf_sd, "values") else nf_sd
            nf_e_rate = nf_vals * A_pixel * qe_curve * (lam_m / hc)
            nf_e_rate_band = nf_e_rate[mask]
            if nf_e_rate_band.size >= 2:
                nearfield_e = float(np.trapezoid(nf_e_rate_band, wl_band)) * t_int

        stray_sd = optics_out.get("stray_light_irradiance_at_fpa")
        if stray_sd is not None:
            stray_vals = stray_sd.values if hasattr(stray_sd, "values") else stray_sd
            stray_e_rate = stray_vals * A_pixel * qe_curve * (lam_m / hc)
            stray_e_rate_band = stray_e_rate[mask]
            if stray_e_rate_band.size >= 2:
                stray_e = float(np.trapezoid(stray_e_rate_band, wl_band)) * t_int

        state = state.with_stage_output(
            "spectral_integration",
            "nearfield_e",
            nearfield_e,
        )
        state = state.with_stage_output(
            "spectral_integration",
            "stray_e",
            stray_e,
        )
        # Export QE so backward-propagation code (responsivity.py) can
        # include it without cross-stage imports from radiant.detector.
        state = state.with_stage_output(
            "spectral_integration",
            "qe_curve",
            qe_curve,
        )
        return state.with_stage_output(
            "spectral_integration",
            "qe_scalar",
            qe_value,
        )
