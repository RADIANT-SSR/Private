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

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.constants import hc
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime


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
        EE_box: float = optics_out["EE_box"]
        regime = optics_out["regime"]

        # Normalise regime to enum (handle legacy string values).
        if isinstance(regime, str):
            regime = RadiometricRegime(regime)

        # Guard: EE_box != 1.0 in extended regime is a programming error.
        if regime == RadiometricRegime.EXTENDED and EE_box != 1.0:
            raise RuntimeError(
                "SpectralIntegrationStage: EE_box != 1.0 but regime is "
                f"'extended' (EE_box={EE_box}). In extended-scene mode, "
                "EE_box must not be applied (Rule 9). This is a programming "
                "error in OpticsStage."
            )

        # Read post-optics spectral radiance.
        post_optics = state.frames["post_optics"]
        L = post_optics.spectral_radiance
        if L is None:
            raise ValueError(
                "SpectralIntegrationStage: 'post_optics' frame has no spectral_radiance."
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
            # S = L_target · τ_atm · τ_opt · A_collect · (A_target/R²) · (λ/hc)
            # L_post_optics includes L_path which fills the pixel as background,
            # so we reconstruct target-only contribution.
            source_out = state.stage_outputs["source"]
            A_target: float = source_out["projected_area_m2"]
            R: float = source_out["range_m"]
            if A_target is None or R is None or R <= 0.0:
                raise ValueError(
                    "SpectralIntegrationStage: point_source regime requires "
                    "projected_area_m2 and range_m from SourceStage. "
                    f"Got A_target={A_target}, R={R}."
                )

            # Target-only radiance through atmosphere and optics.
            L_target = state.frames["at_target"].spectral_radiance
            if L_target is None:
                raise ValueError(
                    "SpectralIntegrationStage: 'at_target' frame has no spectral_radiance."
                )
            atm_out = state.stage_outputs["atmosphere"]
            tau_atm = atm_out["tau_atm"]
            tau_opt: float = optics_out["tau_opt"]
            L_target_post = L_target * tau_atm * tau_opt

            Omega_target = A_target / (R * R)
            photon_rate = L_target_post * A_collect * Omega_target * (lam_m / hc)

        elif regime == RadiometricRegime.SUB_PIXEL:
            # Sub-pixel: mix target and background radiances.
            source_out = state.stage_outputs["source"]
            fill_fraction: float = source_out["fill_fraction"]
            L_background_src = source_out["L_background"]

            # Propagate background through atmosphere and optics.
            atm_out = state.stage_outputs["atmosphere"]
            tau_atm = atm_out["tau_atm"]
            L_path = atm_out["L_path"]
            tau_opt: float = optics_out["tau_opt"]

            L_bg_post_optics = (L_background_src * tau_atm + L_path) * tau_opt

            # L_mixed = ff · L_target · EE_box + (1 - ff) · L_bg
            # EE_box applies to target contribution only (Rule 9).
            L_mixed = fill_fraction * L * EE_box + (1.0 - fill_fraction) * L_bg_post_optics

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

        e_per_s = float(np.trapezoid(e_rate_band, wl_band))  # e-/s/pixel

        # For point source, EE_box is a post-integration multiplicative factor.
        if regime == RadiometricRegime.POINT_SOURCE:
            signal_e = e_per_s * t_int * EE_box
        else:
            # Extended: no EE_box. Sub-pixel: already mixed into L_mixed.
            signal_e = e_per_s * t_int

        # --- Background reference and contrast ---
        # Compute what a pure-background pixel would produce. The
        # contrast ΔS = signal_e − background_e is the detection-
        # relevant quantity: positive for hot targets, negative for
        # cold targets relative to background.
        source_out_c = state.stage_outputs.get("source", {})
        has_background = "L_background" in source_out_c

        if regime == RadiometricRegime.POINT_SOURCE:
            # signal_e is already the target-only contribution (no
            # background in the point source equation). The target
            # signal IS the excess over background.
            contrast_e = signal_e
            background_e = 0.0
        elif has_background:
            # Extended and sub-pixel: compute background-only pixel signal.
            L_bg_src = source_out_c["L_background"]
            atm_out_bg = state.stage_outputs["atmosphere"]
            tau_atm_bg = atm_out_bg["tau_atm"]
            L_path_bg = atm_out_bg["L_path"]
            tau_opt_bg: float = optics_out["tau_opt"]

            L_bg_post = (L_bg_src * tau_atm_bg + L_path_bg) * tau_opt_bg
            bg_photon_rate = L_bg_post * A_collect * Omega_pixel * (lam_m / hc)
            bg_e_rate = bg_photon_rate * qe_curve
            bg_e_rate_band = bg_e_rate[mask]
            bg_e_per_s = float(np.trapezoid(bg_e_rate_band, wl_band))
            background_e = bg_e_per_s * t_int
            contrast_e = signal_e - background_e
        else:
            # No background available (legacy / isolated test). Contrast
            # defaults to the full signal (equivalent to zero background).
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
