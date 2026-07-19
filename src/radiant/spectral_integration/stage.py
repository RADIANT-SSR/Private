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
    background_e = full-pixel pedestal (Ω_pixel) when a background frame
    exists (Gap 73): real photo-charge that shot-noises and fills the
    well, but is NOT part of the target signal (contrast_e = signal_e).

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
from radiant.spectral_integration.errors import (
    SpectralIntegrationStateError,
    SpectralIntegrationValidationError,
)

logger = logging.getLogger(__name__)


def _background_pedestal_e(
    bg_spectral_radiance: np.ndarray,
    tau_opt_bg: float,
    lam_m: np.ndarray,
    mask: np.ndarray,
    wl_band: np.ndarray,
    collection: np.ndarray,
    a_collect: float,
    omega_pixel: float,
    t_int: float,
) -> float:
    """Full-pixel background pedestal in electrons per pixel per integration.

    The at-aperture background frame bundles ``L_bg·τ_full_up + L_path_full``;
    this transports it once through the optics and integrates the full-pixel
    photon flux (``Ω_pixel``) into electrons. Used identically by the
    extended/sub-pixel background reference and the point-source pedestal
    (Gap 73) — one computation, one place (Rule 19).
    """
    l_bg_post = bg_spectral_radiance * tau_opt_bg
    bg_photon_rate = l_bg_post * a_collect * omega_pixel * (lam_m / hc)
    bg_e_rate = bg_photon_rate * collection
    bg_e_per_s = float(np.trapezoid(bg_e_rate[mask], wl_band))
    return bg_e_per_s * t_int


def _extended_contrast_reference_signal(
    params: ParameterSet,
    state: ChainState,
    wl: np.ndarray,
    lam_m: np.ndarray,
    mask: np.ndarray,
    wl_band: np.ndarray,
    collection: np.ndarray,
    a_collect: float,
    omega_pixel: float,
    t_int: float,
    optics_out: dict[str, object],
) -> float | None:
    """Reference-pixel signal S_b for the extended contrast (ADR-0005, Gap 52).

    When ``source.contrast_reference.temperature > 0`` this builds the
    in-band signal of a uniform reference scene in the neighbouring pixel —
    ``L_ref = ε_ref·B(λ,T_ref)·τ_atm + L_path`` transported once through the
    optics — for the extended ``contrast_snr`` differential. It is used ONLY
    for the contrast metric and NEVER enters the noise budget (Decision #13
    preserved). Returns None when no contrast reference is configured.
    """
    try:
        t_ref: float = params.get("source.contrast_reference.temperature")
    except (KeyError, TypeError):
        return None
    if not (np.isfinite(t_ref) and t_ref > 0.0):
        return None
    eps_ref: float = params.get("source.contrast_reference.emissivity")

    atm_out = state.stage_outputs.get("atmosphere", {})
    tau_atm = atm_out.get("tau_atm")
    l_path = atm_out.get("L_path")
    tau_opt = optics_out.get("tau_opt")
    if tau_atm is None or l_path is None or tau_opt is None:
        return None

    b_ref = planck_spectral_radiance(wl, t_ref)  # W/m²/sr/µm
    l_ref_at_aperture = eps_ref * b_ref * np.asarray(tau_atm) + np.asarray(l_path)
    l_ref_post = l_ref_at_aperture * tau_opt
    photon_rate = l_ref_post * a_collect * omega_pixel * (lam_m / hc)
    e_rate = photon_rate * collection
    ref_e_per_s = float(np.trapezoid(e_rate[mask], wl_band))
    return ref_e_per_s * t_int


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
                raise SpectralIntegrationStateError(
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
            raise SpectralIntegrationStateError(
                "SpectralIntegrationStage: EE_box != 1.0 but regime is "
                f"'extended' (EE_box={EE_box}). In extended-scene mode, "
                "EE_box must not be applied (Rule 9). This is a programming "
                "error in PlatformStage."
            )

        # Read post-optics spectral radiance.
        post_optics = state.frames["post_optics"]
        L = post_optics.spectral_radiance
        if L is None:
            raise SpectralIntegrationValidationError(
                "SpectralIntegrationStage: 'post_optics' frame has no spectral_radiance."
            )

        if np.any(np.isnan(L)):
            raise SpectralIntegrationValidationError(
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

        # Areal fill factor: only the photosensitive fraction FF of the pixel
        # collects photons (CU-074). Fold it into an effective per-λ collection
        # efficiency QE·FF used for every electron conversion; the stored
        # qe_curve/qe_scalar provenance stays pure QE. At FF = 1 this is a
        # no-op. The full-pitch pixel area is used only for the geometric
        # Ω_pixel (IFOV/GSD), never for photon collection.
        fill_factor: float = params.get("detector.fill_factor")
        collection = qe_curve * fill_factor

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
            # Gap 98 A: a point source is defined by its radiant intensity, not a
            # surface radiance × area. When neither an intensity input nor a
            # projected area is present, steer to the intensity surfaces rather than
            # back to `projected_area_m2` (the intensity paths publish a fictitious
            # reference area, so A_target is None only when no intensity was given).
            if A_target is None:
                raise SpectralIntegrationValidationError(
                    "SpectralIntegrationStage: point_source regime has no target "
                    "intensity. A point source is defined by its radiant intensity "
                    "I(λ) [W/sr], not a surface radiance × area — set one of "
                    "source.target.point_intensity_temperature_K (+ _area_m2, "
                    "_emissivity), source.target.point_intensity_band_W_per_sr, or "
                    "source.target.user_intensity_path; or give a projected area "
                    "(geometry.target.projected_area_m2) to model a resolved target."
                )
            if R is None or R <= 0.0:
                raise SpectralIntegrationValidationError(
                    "SpectralIntegrationStage: point_source regime requires a positive "
                    "slant range. Set geometry.target_range_m (or a geometry mode that "
                    f"derives the slant range). Got range_m={R}."
                )

            L_aperture_target = state.frames["at_aperture_target"].spectral_radiance
            if L_aperture_target is None:
                raise SpectralIntegrationValidationError(
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
                raise SpectralIntegrationValidationError(
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
            raise SpectralIntegrationValidationError(
                f"SpectralIntegrationStage: unknown regime {regime!r}."
            )

        # electron rate: × effective collection efficiency (QE·FF)
        e_rate = photon_rate * collection  # [e-/s/pixel/µm]

        # Apply filter bandpass mask and integrate.
        mask = (wl >= lam_min) & (wl <= lam_max)
        wl_band = wl[mask]
        e_rate_band = e_rate[mask]

        if wl_band.size < 2:
            raise SpectralIntegrationValidationError(
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
            # signal_e is the target-only excess: the point-source equation
            # uses Ω_target and strips path radiance, so the target signal
            # IS the contrast over the background pedestal.
            contrast_e = signal_e
            if has_background:
                # Gap 73: the sky/scene background fills the pixel IFOV
                # (Ω_pixel) behind the compact target. This full-pixel
                # pedestal is real photo-charge that shot-noises and fills
                # the well even though it is NOT part of the target signal.
                # Same full-pixel formula as the extended/sub-pixel branch,
                # so the noise budget is continuous across the
                # sub-pixel→point-source boundary.
                tau_opt_bg = optics_out["tau_opt"]
                background_e = _background_pedestal_e(
                    bg_frame_c.spectral_radiance,
                    tau_opt_bg,
                    lam_m,
                    mask,
                    wl_band,
                    collection,
                    A_collect,
                    Omega_pixel,
                    t_int,
                )
            else:
                background_e = 0.0
        elif has_background:
            # Extended and sub-pixel: compute background-only pixel signal.
            # The at_aperture_background frame already bundles
            # L_bg · τ_full_up + L_path_full; transmit through the optics
            # once to reach the FPA.
            tau_opt_bg = optics_out["tau_opt"]
            background_e = _background_pedestal_e(
                bg_frame_c.spectral_radiance,
                tau_opt_bg,
                lam_m,
                mask,
                wl_band,
                collection,
                A_collect,
                Omega_pixel,
                t_int,
            )
            contrast_e = signal_e - background_e
        else:
            # No background descriptor (matrix Decision #13 — computed-
            # extended cells skip the bg photon reference entirely).
            background_e = 0.0
            contrast_e = signal_e
            # ADR-0005 (Gap 52): if a contrast-reference scene is configured,
            # make contrast_e a true target-vs-background differential
            # signal_e − S_b. The reference is metric-only — background_e (and
            # thus the noise budget) stays 0, preserving Decision #13.
            ref_signal_e = _extended_contrast_reference_signal(
                params,
                state,
                wl,
                lam_m,
                mask,
                wl_band,
                collection,
                A_collect,
                Omega_pixel,
                t_int,
                optics_out,
            )
            if ref_signal_e is not None:
                contrast_e = signal_e - ref_signal_e
                state = state.with_stage_output(
                    "spectral_integration", "contrast_reference_signal_e", ref_signal_e
                )

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

        # Nearfield and stray irradiance also collect only on the active area:
        # use the effective QE·FF collection efficiency (CU-074).
        nf_sd = optics_out.get("nearfield_irradiance_at_fpa")
        if nf_sd is not None:
            nf_vals = nf_sd.values if hasattr(nf_sd, "values") else nf_sd
            nf_e_rate = nf_vals * A_pixel * collection * (lam_m / hc)
            nf_e_rate_band = nf_e_rate[mask]
            if nf_e_rate_band.size >= 2:
                nearfield_e = float(np.trapezoid(nf_e_rate_band, wl_band)) * t_int

        stray_sd = optics_out.get("stray_light_irradiance_at_fpa")
        if stray_sd is not None:
            stray_vals = stray_sd.values if hasattr(stray_sd, "values") else stray_sd
            stray_e_rate = stray_vals * A_pixel * collection * (lam_m / hc)
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
