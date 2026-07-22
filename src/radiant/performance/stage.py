"""PerformanceStage — computes performance metrics from the chain state.

Computes SNR, contrast SNR, NEDT (when dS/dT available), saturation
margins, dynamic range, and spatial metrics (MTF, RER, EE, FWHM)
when an EffectivePSF is available from the optics stage.

The stage writes all results as metrics and stage outputs.
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import replace

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.geometry import slant_range_spherical_m
from radiant.core.parameters import ParameterSet
from radiant.performance.access_rate import compute_access_rate_m2_s
from radiant.performance.adc_margin import compute_adc_margin
from radiant.performance.consistency_check import check_dual_path_consistency
from radiant.performance.contrast_snr import compute_contrast_snr
from radiant.performance.detection_beer_lambert import detection_range_beer_lambert
from radiant.performance.diffraction_limit import (
    diffraction_limited_angular_rad,
    diffraction_limited_ground_m,
)
from radiant.performance.dynamic_range import compute_dynamic_range
from radiant.performance.folded_mtf import compute_folded_mtf
from radiant.performance.ground_range import compute_ground_range_m
from radiant.performance.gsd import compute_gsd, compute_gsd_from_geometry
from radiant.performance.metric_selection import (
    ALL_GROUPED_METRICS,
    GROUP_PARAMS,
    resolve_selection,
)
from radiant.performance.minimum_resolvable import minimum_resolvable_temperature_K
from radiant.performance.mtf_budget import compute_mtf_budget
from radiant.performance.nedt import compute_nedt, compute_nedt_from_snr
from radiant.performance.niirs import compute_niirs
from radiant.performance.qsample import compute_q
from radiant.performance.sampling_regime import classify_sampling_regime
from radiant.performance.scan_feasibility import scan_feasibility
from radiant.performance.scnr import compute_scnr
from radiant.performance.snr import compute_snr
from radiant.performance.strehl import compute_strehl
from radiant.performance.swath_width import compute_swath_width_m
from radiant.performance.system_mtf import mtf_at_nyquist, nyquist_freq
from radiant.performance.turbulence_mtf_term import kolmogorov_mtf_1d
from radiant.performance.well_margin import compute_well_margin

logger = logging.getLogger(__name__)


def _compute_spatial_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute spatial metrics from the EffectivePSF built by OpticsStage.

    Reads the EffectivePSF from ``stage_outputs["platform"]["effective_psf"]``
    (jitter-degraded) if available, otherwise falls back to
    ``stage_outputs["optics"]["effective_psf"]``.
    Skips gracefully if neither is available.
    """
    try:
        # Prefer platform ePSF (includes jitter); fall back to optics.
        plat_out = state.stage_outputs.get("platform", {})
        epsf = plat_out.get("effective_psf")
        if epsf is None:
            epsf = state.stage_outputs["optics"]["effective_psf"]
    except KeyError:
        logger.debug("EffectivePSF not available; skipping spatial metrics.")
        return state

    try:
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
    except (KeyError, TypeError):
        logger.debug("Pixel pitch not available; skipping spatial metrics.")
        return state

    # Apply the PSF-path IPC kernel built by the detector stage. It is
    # resampled to the PSF sample grid so its α couplings sit one *pixel
    # pitch* away (CU-083); the raw 3×3 kernel would place them one sample
    # away — orders of magnitude too close on the sub-µm PSF grid, making
    # the PSF-path IPC effect negligible and divergent from the analytic
    # MTF-product term (Rule 4).
    det_out = state.stage_outputs.get("detector", {})
    ipc_kern = det_out.get("ipc_kernel_psf")
    if ipc_kern is not None:
        epsf = epsf.with_kernel("ipc", ipc_kern)

    # Apply electronics blur kernel if the readout stage built one
    # (Rule 4: matches the mtf_electronics_x product term; Rule 11: the
    # kernel travels via ChainState, same pattern as the IPC kernel).
    elec_kern = state.stage_outputs.get("readout", {}).get("electronics_kernel")
    if elec_kern is not None:
        epsf = epsf.with_kernel("electronics", elec_kern)

    # Compute spatial metrics from EffectivePSF.
    fwhm_x = epsf.fwhm("x")
    fwhm_y = epsf.fwhm("y")
    rer = epsf.rer()
    ee_1x1 = epsf.ensquared_energy_nxn(1)
    ee_3x3 = epsf.ensquared_energy_nxn(3)

    # Strehl ratio (Rule 4: PSF-derived, not analytic). Peak of the
    # degraded PSF over the diffraction-limited reference built by
    # OpticsStage. The reference carries the same detector kernels
    # (pixel aperture, diffusion, and IPC below) so detector effects
    # cancel; WFE, defocus, jitter, smear, and turbulence do not.
    strehl: float | None = None
    ref_epsf = state.stage_outputs.get("optics", {}).get("reference_psf")
    if ref_epsf is not None:
        if ipc_kern is not None:
            ref_epsf = ref_epsf.with_kernel("ipc", ipc_kern)
        if elec_kern is not None:
            ref_epsf = ref_epsf.with_kernel("electronics", elec_kern)
        strehl = epsf.strehl(ref_epsf)

    # MTF curves (both axes) and scalar at Nyquist.
    freq_x, mtf_x = epsf.mtf_1d("x")
    freq_y, mtf_y = epsf.mtf_1d("y")
    mtf_ny = mtf_at_nyquist(freq_x, mtf_x, pixel_pitch_m)

    # Log (debug) when the Nyquist frequency exceeds the diffraction cutoff.
    # This is a valid, documented sampling regime (the detector oversamples the
    # optics), not a fault: the operative fact is already surfaced as structured
    # status — the q_center/q_min/q_max metrics, sampling_regime_code, and
    # mtf_at_nyquist ≈ 0. Per the zero-warnings-for-valid-scenarios bar (CU-166),
    # it is a debug note, not a per-evaluate warning (was logger.warning; CU-166
    # approach 4).
    try:
        f_number: float = params.get("optics.f_number")
        lambda_m = epsf.wavelength_um * 1e-6
        f_cutoff = 1.0 / (lambda_m * f_number)
        f_nyquist = 1.0 / (2.0 * pixel_pitch_m)
        if f_nyquist > f_cutoff:
            logger.debug(
                "Detector Nyquist frequency (%.0f cy/m) exceeds diffraction cutoff "
                "(%.0f cy/m) at λ=%.2f µm, f/%.1f. MTF at Nyquist is zero; "
                "this is physically correct and indicates the detector oversamples "
                "the optics (Q = %.2f).",
                f_nyquist,
                f_cutoff,
                epsf.wavelength_um,
                f_number,
                lambda_m * f_number / pixel_pitch_m,
            )
    except (KeyError, TypeError):
        pass  # f_number not available; skip diagnostic

    # Write metrics.
    state = state.with_metric("fwhm_x_m", fwhm_x)
    state = state.with_metric("fwhm_y_m", fwhm_y)
    state = state.with_metric("rer", rer)
    state = state.with_metric("ee_1x1", ee_1x1)
    state = state.with_metric("ee_3x3", ee_3x3)
    state = state.with_metric("mtf_at_nyquist", mtf_ny)
    if strehl is not None:
        state = state.with_metric("strehl", strehl)

    # Store full MTF curves and EffectivePSF for downstream access.
    state = state.with_stage_output("performance", "mtf_freq_x", freq_x)
    state = state.with_stage_output("performance", "mtf_x", mtf_x)
    state = state.with_stage_output("performance", "mtf_freq_y", freq_y)
    state = state.with_stage_output("performance", "mtf_y", mtf_y)
    state = state.with_stage_output("performance", "effective_psf", epsf)

    # Folded (aliased) MTF: meaningful for Q < 2.0.
    f_ny = nyquist_freq(pixel_pitch_m)
    folded_x = compute_folded_mtf(freq_x, mtf_x, f_ny, n_folds=3)
    folded_y = compute_folded_mtf(freq_y, mtf_y, f_ny, n_folds=3)

    state = state.with_stage_output("performance", "folded_mtf_x", folded_x)
    state = state.with_stage_output("performance", "folded_mtf_y", folded_y)

    # Scalar metrics at Nyquist.
    from radiant.performance.system_mtf import mtf_at_freq

    mtf_folded_ny = mtf_at_freq(f_ny, folded_x.freq, folded_x.mtf_folded)
    alias_frac_ny = mtf_at_freq(f_ny, folded_x.freq, folded_x.alias_fraction)

    state = state.with_metric("mtf_folded_at_nyquist", mtf_folded_ny)
    state = state.with_metric("alias_fraction_at_nyquist", alias_frac_ny)

    # --- MTF product path: turbulence MTF term ---
    freq_mrad = state.spatial_freq_cycles_per_mrad
    atm_out = state.stage_outputs.get("atmosphere", {})
    r0_m = atm_out.get("r0_m")
    if freq_mrad is not None and r0_m is not None and r0_m > 0.0:
        try:
            focal_length_turb: float = params.get("optics.focal_length_m")
        except (KeyError, TypeError):
            focal_length_turb = 0.0
        if focal_length_turb > 0.0:
            freq_m_turb = freq_mrad / (focal_length_turb * 1e3)
            wavelength_turb_m = epsf.wavelength_um * 1e-6
            mtf_turb = kolmogorov_mtf_1d(freq_m_turb, wavelength_turb_m, r0_m, focal_length_turb)
            state = state.with_mtf("mtf_turbulence_x", mtf_turb)
            state = state.with_mtf("mtf_turbulence_y", mtf_turb)

    # --- MTF product path: budget and system MTF ---
    if freq_mrad is not None and len(state.mtf_terms) > 0:
        try:
            focal_length_m: float = params.get("optics.focal_length_m")
        except (KeyError, TypeError):
            focal_length_m = 0.0

        if focal_length_m > 0.0:
            budget = compute_mtf_budget(
                state.mtf_terms,
                freq_mrad,
                pixel_pitch_m,
                focal_length_m,
            )
            state = state.with_stage_output("performance", "mtf_budget", budget)
            state = state.with_metric("mtf_system_at_nyquist_x", budget.system_mtf_at_nyquist_x)
            state = state.with_metric("mtf_system_at_nyquist_y", budget.system_mtf_at_nyquist_y)

    # --- Dual-path consistency check ---
    if freq_mrad is not None and len(state.mtf_terms) > 0:
        try:
            fl_check: float = params.get("optics.focal_length_m")
        except (KeyError, TypeError):
            fl_check = 0.0

        if fl_check > 0.0:
            consistency = check_dual_path_consistency(epsf, state.mtf_terms, freq_mrad, fl_check)
            state = state.with_stage_output("performance", "dual_path_consistency", consistency)
            if not (consistency.passed_x and consistency.passed_y):
                logger.warning(
                    "Dual-path MTF consistency check FAILED: "
                    "max_err_x=%.4f, max_err_y=%.4f (tol=%.4f)",
                    consistency.max_absolute_error_x,
                    consistency.max_absolute_error_y,
                    consistency.tolerance,
                )

    return state


def _compute_saturation_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute well margin, ADC margin, and dynamic range."""
    ro_out = state.stage_outputs.get("readout", {})

    # Well margin
    signal_e_final = ro_out.get("signal_e_final")
    try:
        fwc_e: float = params.get("readout.full_well_capacity_e")
    except (KeyError, TypeError):
        fwc_e = 0.0

    if signal_e_final is not None and fwc_e > 0.0:
        well_result = compute_well_margin(signal_e_final, fwc_e)
        if well_result.ok:
            state = state.with_metric("well_margin_dB", well_result.margin_dB)

    # ADC margin
    signal_dn = ro_out.get("signal_dn_pre_coadd")
    try:
        adc_bits: int = int(params.get("readout.adc_bits"))
        max_dn = (1 << adc_bits) - 1
    except (KeyError, TypeError):
        max_dn = 0

    if signal_dn is not None and max_dn > 0:
        adc_result = compute_adc_margin(signal_dn, max_dn)
        if adc_result.ok:
            state = state.with_metric("adc_margin_dB", adc_result.margin_dB)

    # Dynamic range: FWC / noise floor (dark + read + quant RSS)
    sigma_temporal = ro_out.get("sigma_temporal_e")
    if fwc_e > 0.0 and sigma_temporal is not None and sigma_temporal > 0.0:
        dr_result = compute_dynamic_range(fwc_e, sigma_temporal)
        if dr_result.ok:
            state = state.with_metric("dynamic_range_dB", dr_result.value_dB)

    return state


def _compute_gsd_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute ground sample distance when orbital/airborne geometry is available.

    Delegates to ``gsd.compute_gsd`` for the math.  Reads
    ``geometry.path_zenith_rad`` for off-nadir correction (defaults to 0.0
    if not set).  Skips gracefully when altitude or focal length is not set
    (e.g. lab/TVAC scenarios).
    """
    try:
        altitude_m: float = params.get("geometry.sensor_altitude_m")
    except (KeyError, TypeError):
        return state

    if altitude_m <= 0.0:
        return state

    try:
        focal_length_m: float = params.get("optics.focal_length_m")
        pitch_x_m: float = params.get("detector.pixel_pitch_x_um")
        pitch_y_m: float = params.get("detector.pixel_pitch_y_um")
    except (KeyError, TypeError):
        return state

    if focal_length_m <= 0.0:
        return state

    # ADR-0006: consume the slant range and incidence angle GeometryStage
    # derived once from the canonical target-side zenith. Falls back to the
    # legacy (altitude, angle) derivation only for partial fixtures that run
    # PerformanceStage without GeometryStage (CU-096 tracks retiring it).
    geo_out = state.stage_outputs.get("geometry", {})
    slant_range_m = geo_out.get("slant_range_m")
    incidence_rad = geo_out.get("incidence_angle_rad")
    if slant_range_m is not None and incidence_rad is not None:
        result = compute_gsd_from_geometry(
            pitch_x_m,
            pitch_y_m,
            focal_length_m,
            slant_range_m,
            incidence_rad,
        )
    else:
        try:
            path_zenith_rad: float = params.get("geometry.path_zenith_rad")
        except (KeyError, TypeError):
            path_zenith_rad = 0.0
        result = compute_gsd(
            pitch_x_m,
            pitch_y_m,
            altitude_m,
            focal_length_m,
            path_zenith_rad=path_zenith_rad,
        )
    state = state.with_metric("gsd_cross_track_m", result.cross_track_m)
    state = state.with_metric("gsd_along_track_m", result.along_track_m)
    state = state.with_metric("gsd_geometric_mean_m", result.geometric_mean_m)
    return _compute_scan_feasibility(state, params, result.along_track_m)


def _compute_detection_range_metric(
    state: ChainState,
    params: ParameterSet,
    snr_result: object,
) -> ChainState:
    """Point-source detection range via the Beer-Lambert solver (Gap 77).

    Only meaningful in the point-source regime: the signal follows the
    inverse-square law with range, attenuated by a constant atmospheric
    extinction. Uses the current signal/noise at the source range as the
    reference point and bisects for the range where SNR equals
    ``performance.detection_snr_threshold``.

    Constant-extinction assumption: α is derived from the band-mean
    in-band transmittance over the source range (α = −ln(τ̄)/R). This is
    exact in vacuum (α = 0, pure inverse-square) and a first-order model
    for atmospheric paths; the full geometry-aware spherical-Earth
    slant-path solve (varying α along the path) is deferred. Skips
    gracefully outside the point-source regime or when the inputs are
    unavailable.
    """
    optics_out = state.stage_outputs.get("optics", {})
    regime = optics_out.get("regime")
    regime_value = getattr(regime, "value", regime)
    if regime_value != "point_source":
        return state

    signal_e = getattr(snr_result, "signal_e", None)
    noise_e = getattr(snr_result, "noise_e", None)
    if not signal_e or not noise_e or signal_e <= 0.0 or noise_e <= 0.0:
        return state

    source_out = state.stage_outputs.get("source", {})
    ref_range_m = source_out.get("range_m")
    if not ref_range_m or ref_range_m <= 0.0:
        return state

    # Constant extinction from the band-mean in-band transmittance.
    alpha = 0.0
    tau_atm = state.stage_outputs.get("atmosphere", {}).get("tau_atm")
    if tau_atm is not None:
        wl = state.wavelength_um
        lam_min = params.get("spectral_integration.filter_min_um")
        lam_max = params.get("spectral_integration.filter_max_um")
        band = (wl >= lam_min) & (wl <= lam_max)
        if band.any():
            tau_bar = float(np.mean(np.asarray(tau_atm)[band]))
            if 0.0 < tau_bar < 1.0:
                alpha = -math.log(tau_bar) / ref_range_m

    threshold: float = params.get("performance.detection_snr_threshold")
    result = detection_range_beer_lambert(
        signal_e_at_ref=float(signal_e),
        noise_e=float(noise_e),
        ref_range_m=float(ref_range_m),
        extinction_coeff=alpha,
        snr_threshold=threshold,
    )
    state = state.with_stage_output("performance", "detection_range_result", result)
    if result.ok:
        state = state.with_metric("detection_range_m", result.range_m)
    return state


def _compute_scan_feasibility(
    state: ChainState,
    params: ParameterSet,
    gsd_along_track_m: float,
) -> ChainState:
    """Pushbroom/TDI dwell-time feasibility guard (Gap 74, minimum slice).

    When a ground velocity is set, warn if the integration exceeds the
    per-line dwell (along-track smear > one ground sample) — a silently
    unphysical TDI timing whose reported SNR would still look authoritative.
    Stores ``max_integration_time_s``. Skips when no ground velocity is set.
    """
    try:
        v_ground: float = params.get("platform.ground_velocity_m_s")
        t_int: float = params.get("spectral_integration.integration_time_s")
    except (KeyError, TypeError):
        return state
    if v_ground <= 0.0 or t_int <= 0.0 or gsd_along_track_m <= 0.0:
        return state

    feas = scan_feasibility(gsd_along_track_m, v_ground, t_int)
    state = state.with_metric("max_integration_time_s", feas.max_integration_time_s)
    if not feas.feasible:
        try:
            n_tdi: int = int(params.get("readout.n_tdi"))
        except (KeyError, TypeError):
            n_tdi = 1
        tdi_note = (
            f" With n_tdi = {n_tdi}, the TDI stages cannot stay registered to the moving image."
            if n_tdi > 1
            else ""
        )
        warnings.warn(
            "ScanFeasibility: integration_time_s = "
            f"{t_int:.4g} s exceeds the per-line dwell "
            f"{feas.max_integration_time_s:.4g} s "
            f"(GSD_along / ground_velocity); the along-track image smears "
            f"{feas.smear_pixels:.2f} pixels during one integration, so the "
            "reported SNR is optimistic (the smear MTF captures the blur, but "
            f"the timing itself is infeasible).{tdi_note} Reduce "
            "spectral_integration.integration_time_s to "
            f"≤ {feas.max_integration_time_s:.4g} s, reduce "
            "platform.ground_velocity_m_s, or coarsen the GSD.",
            UserWarning,
            stacklevel=2,
        )
    return state


def _compute_access_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute access geometry metrics (ground range, swath, access rate).

    Requires GSD and altitude to have been computed first.  Skips
    gracefully when required inputs are not available.
    """
    # Require GSD and altitude.
    if "gsd_cross_track_m" not in state.metrics:
        return state

    try:
        altitude_m: float = params.get("geometry.sensor_altitude_m")
    except (KeyError, TypeError):
        return state

    if altitude_m <= 0.0:
        return state

    # Ground range — published by GeometryStage (ADR-0006); legacy
    # derivation only for partial fixtures without the stage (CU-096).
    geo_out = state.stage_outputs.get("geometry", {})
    ground_range = geo_out.get("ground_range_m")
    if ground_range is None:
        try:
            path_zenith_rad: float = params.get("geometry.path_zenith_rad")
        except (KeyError, TypeError):
            path_zenith_rad = 0.0
        ground_range = compute_ground_range_m(altitude_m, path_zenith_rad)
    state = state.with_metric("ground_range_m", ground_range)

    # Swath width (requires n_pixels_cross > 0).
    try:
        n_pixels_cross: int = int(params.get("detector.n_pixels_cross"))
    except (KeyError, TypeError):
        return state

    if n_pixels_cross <= 0:
        return state

    gsd_cross = state.metrics["gsd_cross_track_m"]
    swath = compute_swath_width_m(gsd_cross, n_pixels_cross)
    state = state.with_metric("swath_width_m", swath)

    # Access area rate (requires ground_speed_m_s). GeometryStage publishes
    # the resolved value (orbit-derived in circular_orbit mode, ADR-0006).
    ground_speed_pub = geo_out.get("ground_speed_m_s")
    if ground_speed_pub is not None:
        ground_speed: float = ground_speed_pub
    else:
        try:
            ground_speed = params.get("geometry.ground_speed_m_s")
        except (KeyError, TypeError):
            return state

    if ground_speed > 0.0:
        rate = compute_access_rate_m2_s(swath, ground_speed)
        state = state.with_metric("access_rate_m2_s", rate)

    return state


def _compute_q_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute the sampling parameter Q when optics and detector params are available."""
    try:
        f_number: float = params.get("optics.f_number")
        pitch_m: float = params.get("detector.pixel_pitch_x_um")
        lambda_min: float = params.get("spectral_integration.filter_min_um")
        lambda_max: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state

    result = compute_q(f_number, pitch_m, lambda_min, lambda_max)
    state = state.with_metric("q_center", result.q_center)
    state = state.with_metric("q_min", result.q_min)
    return state.with_metric("q_max", result.q_max)


def _compute_diffraction_limit_metrics(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Diffraction-limited resolution: angular (always) and ground (Gap 49).

    Angular Rayleigh resolution needs only the band-center wavelength and
    aperture; the ground projection additionally needs the slant range.
    Skips gracefully when inputs are unavailable.
    """
    try:
        aperture_m: float = params.get("optics.aperture_diameter_m")
        lambda_min: float = params.get("spectral_integration.filter_min_um")
        lambda_max: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state
    if aperture_m <= 0.0 or lambda_min <= 0.0 or lambda_max <= 0.0:
        return state

    lambda_center_m = 0.5 * (lambda_min + lambda_max) * 1e-6
    angular_rad = diffraction_limited_angular_rad(lambda_center_m, aperture_m)
    state = state.with_metric("diffraction_limit_angular_urad", angular_rad * 1e6)

    # Ground projection at the slant range, consistent with the GSD metric.
    try:
        altitude_m: float = params.get("geometry.sensor_altitude_m")
    except (KeyError, TypeError):
        return state
    if altitude_m <= 0.0:
        return state
    # Slant range — published by GeometryStage (ADR-0006); legacy
    # derivation only for partial fixtures without the stage (CU-096).
    range_pub = state.stage_outputs.get("geometry", {}).get("slant_range_m")
    if range_pub is not None:
        range_m = float(range_pub)
    else:
        try:
            path_zenith_rad: float = params.get("geometry.path_zenith_rad")
        except (KeyError, TypeError):
            path_zenith_rad = 0.0
        range_m = slant_range_spherical_m(altitude_m, path_zenith_rad)
    ground_m = diffraction_limited_ground_m(lambda_center_m, aperture_m, range_m)
    return state.with_metric("diffraction_limit_ground_m", ground_m)


def _compute_sampling_regime_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Detector- vs diffraction-limited sampling regime code (Gap 50).

    Derived from ``q_center`` (0.0 detector-limited, 1.0 near-critical,
    2.0 diffraction-limited). Skips when Q is unavailable.
    """
    q = state.metrics.get("q_center")
    if q is None or q <= 0.0:
        return state
    return state.with_metric("sampling_regime_code", classify_sampling_regime(q))


def _compute_strehl_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute the analytic Marechal Strehl diagnostic when WFE is available.

    The reported ``strehl`` metric is PSF-derived (Rule 4) and computed in
    ``_compute_spatial_metrics``. This analytic value is kept as the
    named diagnostic ``strehl_marechal`` — a fast small-aberration
    cross-check that ignores obscuration, defocus, jitter, and smear.
    """
    try:
        wfe_rms: float = params.get("optics.wfe_rms_waves")
        wfe_ref: float = params.get("optics.wfe_reference_wavelength_um")
        fmin: float = params.get("spectral_integration.filter_min_um")
        fmax: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state

    operating_um = 0.5 * (fmin + fmax)
    strehl_marechal = compute_strehl(wfe_rms, wfe_ref, operating_um)
    return state.with_metric("strehl_marechal", strehl_marechal)


def _compute_nedt_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute NEDT using the Planck-derivative approximation.

    Requires SNR to already be computed and stored in ``state.metrics``.
    Uses target temperature and band-center wavelength from params.
    """
    snr = state.metrics.get("snr")
    if snr is None or snr <= 0.0:
        return state

    # Prefer the exact band-integrated dS/dT (Gap 43) computed by
    # SpectralIntegrationStage; fall back to the single-λ Planck-factor
    # approximation when it is unavailable (e.g. no target temperature).
    si_out = state.stage_outputs.get("spectral_integration", {})
    ds_dt = si_out.get("ds_dt_e_per_K")
    signal_e = si_out.get("signal_e")
    if ds_dt is not None and ds_dt > 0.0 and signal_e is not None:
        noise_e = signal_e / snr  # snr = signal_e / noise_e
        result = compute_nedt(noise_e, ds_dt)
        if result.ok:
            state = state.with_metric("nedt_K", result.value_K)
            return state.with_stage_output("performance", "nedt_result", result)

    try:
        target_temp: float = params.get("source.target.temperature")
        fmin: float = params.get("spectral_integration.filter_min_um")
        fmax: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state

    lambda_eff_um = 0.5 * (fmin + fmax)
    result = compute_nedt_from_snr(target_temp, snr, lambda_eff_um)
    if result.ok:
        state = state.with_metric("nedt_K", result.value_K)
        state = state.with_stage_output("performance", "nedt_result", result)
    return state


def _compute_mrt_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Minimum resolvable temperature at Nyquist (Gap 53).

    MRT(f_Ny) = k · NETD / MTF_sys(f_Ny) — the contrast-limited resolution
    metric at the detector Nyquist frequency. Requires NETD and the
    system MTF at Nyquist; skips gracefully otherwise.
    """
    netd = state.metrics.get("nedt_K")
    mtf_ny = state.metrics.get("mtf_at_nyquist")
    if netd is None or mtf_ny is None or mtf_ny <= 0.0:
        return state
    return state.with_metric("mrt_at_nyquist_K", minimum_resolvable_temperature_K(netd, mtf_ny))


def _classify_band(lambda_center_um: float) -> str:
    """Classify spectral band from center wavelength for GIQE/IIRS dispatch."""
    if lambda_center_um < 1.0:
        return "vis"
    if lambda_center_um < 2.5:
        return "nir"
    if lambda_center_um < 7.0:
        return "mwir"
    return "lwir"


def _compute_niirs_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute NIIRS (GIQE-5) or IIRS from previously computed metrics.

    Requires GSD, RER, and SNR to already be in ``state.metrics``.
    Skips gracefully when any required metric is missing (e.g. lab/TVAC).
    """
    # All three must be available.
    gsd_along = state.metrics.get("gsd_along_track_m")
    gsd_cross = state.metrics.get("gsd_cross_track_m")
    rer = state.metrics.get("rer")
    snr = state.metrics.get("snr")

    if any(v is None for v in (gsd_along, gsd_cross, rer, snr)):
        logger.debug("GSD, RER, or SNR not available; skipping NIIRS.")
        return state
    if snr <= 0.0 or rer <= 0.0:
        return state

    # Determine band from filter center wavelength.
    try:
        fmin: float = params.get("spectral_integration.filter_min_um")
        fmax: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state

    band = _classify_band(0.5 * (fmin + fmax))

    # RER is currently a geometric mean; use for both axes.
    result = compute_niirs(gsd_along, gsd_cross, rer, rer, snr, band=band)

    # Applicability gate (CU-166 approach 2, owner-ratified 2026-07-20:
    # strict refusal). Any input outside the GIQE-5 calibration envelope
    # makes the fitted formula unreliable, so by default NIIRS is N/A —
    # an ADR-B result-typed failure on `niirs_result`, no `niirs` metric.
    # `performance.niirs.allow_extrapolated = true` opts back into the
    # extrapolated value (still flagged). The `niirs_extrapolated` metric
    # is emitted either way: it describes the configuration, which is
    # known regardless of whether the value is surfaced.
    try:
        allow_extrapolated = bool(params.get("performance.niirs.allow_extrapolated"))
    except (KeyError, TypeError):
        allow_extrapolated = False  # partial fixtures: strict default
    state = state.with_metric("niirs_extrapolated", 1.0 if result.extrapolated else 0.0)
    if result.extrapolated and not allow_extrapolated:
        result = replace(
            result,
            failure_reason=(
                "NIIRS/IIRS not applicable: "
                + "; ".join(result.warnings)
                + " — the GIQE-5 fit is unreliable outside its calibration "
                "envelope. Set performance.niirs.allow_extrapolated=true to "
                "report the extrapolated value anyway."
            ),
        )
        return state.with_stage_output("performance", "niirs_result", result)
    state = state.with_metric("niirs", result.niirs)
    # Extrapolation beyond the GIQE-5 calibration band is carried as structured
    # status only — the `niirs_extrapolated` metric (0/1), `result.extrapolated`,
    # and `result.warnings` on the stage output. It is deliberately NOT re-emitted
    # as a `warnings.warn` every evaluate: a metric outside its own calibration
    # band is a configuration property, not a per-evaluate event, and re-announcing
    # it floods sweeps / the GUI console (CU-166; owner bar: a valid scenario
    # evaluates warning-free). Consumers render the caveat once from the fields.
    return state.with_stage_output("performance", "niirs_result", result)


# Metric keys each helper (or inline block) can write. Used to gate the helper
# on the dependency-closure *compute* set (Gap 96): a helper runs iff it would
# produce at least one metric the selection needs. The scalar-metric helpers
# ``snr``/``contrast_snr``/``scnr`` are gated individually (their keys, below);
# the multi-metric helpers are gated on the union of what they can write.
_PRODUCES_SPATIAL = frozenset(
    {
        "fwhm_x_m",
        "fwhm_y_m",
        "rer",
        "ee_1x1",
        "ee_3x3",
        "mtf_at_nyquist",
        "strehl",
        "mtf_system_at_nyquist_x",
        "mtf_system_at_nyquist_y",
        "mtf_folded_at_nyquist",
        "alias_fraction_at_nyquist",
    }
)
_PRODUCES_GSD = frozenset(
    {
        "gsd_cross_track_m",
        "gsd_along_track_m",
        "gsd_geometric_mean_m",
        "max_integration_time_s",
    }
)
_PRODUCES_ACCESS = frozenset({"ground_range_m", "swath_width_m", "access_rate_m2_s"})
_PRODUCES_Q = frozenset({"q_center", "q_min", "q_max"})
_PRODUCES_DIFFRACTION = frozenset({"diffraction_limit_angular_urad", "diffraction_limit_ground_m"})
_PRODUCES_NIIRS = frozenset({"niirs", "niirs_extrapolated"})
_PRODUCES_SATURATION = frozenset({"well_margin_dB", "adc_margin_dB", "dynamic_range_dB"})


def _enabled_groups(params: ParameterSet) -> frozenset[str]:
    """Read the five metric-group flags, defaulting to enabled when unset.

    A missing or unresolved flag means "on": partial fixtures build a
    ParameterSet without the performance metric-selection defs, and the
    all-on default must reproduce pre-Gap-96 behavior exactly (Rule 6 — the
    stage reads the selection from the ParameterSet, mutating nothing).
    """
    enabled: set[str] = set()
    for group, param_name in GROUP_PARAMS.items():
        try:
            flag = bool(params.get(param_name))
        except (KeyError, TypeError):
            flag = True  # flag absent/unresolved → group on (additive default)
        if flag:
            enabled.add(group)
    return frozenset(enabled)


class PerformanceStage:
    """Chain stage for performance metrics."""

    @property
    def name(self) -> str:
        return "performance"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # Gap 96: resolve which metric groups are enabled into the surfaced set
        # (what we emit) and the compute set (its dependency closure — the
        # prerequisites we must calculate even if they are not themselves
        # surfaced). Each _compute_* helper is gated on the compute set; the
        # compute-only prerequisites are dropped at the end so only surfaced
        # metrics reach the result. Default (all groups on) ⇒ compute == every
        # metric ⇒ nothing gated and nothing dropped ⇒ identical to before.
        surfaced, compute = resolve_selection(_enabled_groups(params))

        snr_result = None
        if "snr" in compute:
            snr_result = compute_snr(state)
            state = state.with_metric("snr", snr_result.value)
            state = state.with_stage_output("performance", "snr_result", snr_result)

        # Contrast SNR: ΔS / σ — positive for hot, negative for cold.
        if "contrast_snr" in compute:
            contrast_result = compute_contrast_snr(state)
            state = state.with_metric("contrast_snr", contrast_result.value)
            state = state.with_stage_output(
                "performance",
                "contrast_snr_result",
                contrast_result,
            )

        # SCNR: clutter-inclusive detection FoM (Gap 77) — always includes
        # the spatial noise, unlike snr/contrast_snr.
        if "scnr" in compute:
            scnr_result = compute_scnr(state)
            state = state.with_metric("scnr", scnr_result.value)
            state = state.with_stage_output("performance", "scnr_result", scnr_result)

        # Point-source detection range (Gap 77). Needs the SNR result object;
        # detection_range_m requires snr, so the closure guarantees snr_result.
        if "detection_range_m" in compute and snr_result is not None:
            state = _compute_detection_range_metric(state, params, snr_result)

        # Compute spatial metrics if EffectivePSF is available from optics. The
        # Rule-4 dual-path consistency check lives here; when the whole spatial
        # path is deselected (and nothing enabled needs a spatial input) it does
        # not run — there is no spatial computation to check (owner-ratified).
        if compute & _PRODUCES_SPATIAL:
            state = _compute_spatial_metrics(state, params)

        # Ground sample distance (when orbital/airborne geometry is set).
        if compute & _PRODUCES_GSD:
            state = _compute_gsd_metrics(state, params)

        # Access geometry (ground range, swath width, access rate).
        if compute & _PRODUCES_ACCESS:
            state = _compute_access_metrics(state, params)

        # Sampling parameter Q.
        if compute & _PRODUCES_Q:
            state = _compute_q_metrics(state, params)

        # Diffraction-limited resolution (Gap 49) and sampling regime (Gap 50).
        if compute & _PRODUCES_DIFFRACTION:
            state = _compute_diffraction_limit_metrics(state, params)
        if "sampling_regime_code" in compute:
            state = _compute_sampling_regime_metric(state, params)

        # Strehl ratio (Marechal approximation).
        if "strehl_marechal" in compute:
            state = _compute_strehl_metric(state, params)

        # NEDT (Planck-derivative approximation, requires SNR).
        if "nedt_K" in compute:
            state = _compute_nedt_metric(state, params)

        # Minimum resolvable temperature at Nyquist (Gap 53; needs NEDT + MTF).
        if "mrt_at_nyquist_K" in compute:
            state = _compute_mrt_metric(state, params)

        # NIIRS / IIRS (requires GSD, RER, SNR from earlier in this stage).
        if compute & _PRODUCES_NIIRS:
            state = _compute_niirs_metric(state, params)

        # Saturation and dynamic range metrics.
        if compute & _PRODUCES_SATURATION:
            state = _compute_saturation_metrics(state, params)

        # Drop dependency-closure prerequisites that were computed but not
        # selected for surfacing (Gap 96). Only grouped (PerformanceStage-owned)
        # keys are touched — never a metric written elsewhere.
        for key in ALL_GROUPED_METRICS - surfaced:
            state = state.without_metric(key)

        return state
