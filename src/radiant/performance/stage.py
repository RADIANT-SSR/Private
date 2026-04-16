"""PerformanceStage — computes performance metrics from the chain state.

Computes SNR, contrast SNR, NEDT (when dS/dT available), saturation
margins, dynamic range, and spatial metrics (MTF, RER, EE, FWHM)
when an EffectivePSF is available from the optics stage.

The stage writes all results as metrics and stage outputs.
"""

from __future__ import annotations

import logging

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.performance.gsd import compute_gsd
from radiant.performance.nedt import compute_nedt_from_snr
from radiant.performance.niirs import compute_niirs
from radiant.performance.qsample import compute_q
from radiant.performance.strehl import compute_strehl
from radiant.performance.saturation_metrics import (
    compute_adc_margin,
    compute_dynamic_range,
    compute_well_margin,
)
from radiant.performance.snr import compute_contrast_snr, compute_snr
from radiant.performance.system_mtf import mtf_at_nyquist

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

    # Apply IPC kernel if available from detector stage.
    det_out = state.stage_outputs.get("detector", {})
    ipc_kern = det_out.get("ipc_kernel")
    if ipc_kern is not None:
        epsf = epsf.with_kernel("ipc", ipc_kern)

    # Compute spatial metrics from EffectivePSF.
    fwhm_x = epsf.fwhm("x")
    fwhm_y = epsf.fwhm("y")
    rer = epsf.rer()
    ee_1x1 = epsf.ensquared_energy_nxn(1)
    ee_3x3 = epsf.ensquared_energy_nxn(3)

    # MTF curves (both axes) and scalar at Nyquist.
    freq_x, mtf_x = epsf.mtf_1d("x")
    freq_y, mtf_y = epsf.mtf_1d("y")
    mtf_ny = mtf_at_nyquist(freq_x, mtf_x, pixel_pitch_m)

    # Warn when Nyquist frequency exceeds the diffraction cutoff.
    try:
        f_number: float = params.get("optics.f_number")
        lambda_m = epsf.wavelength_um * 1e-6
        f_cutoff = 1.0 / (lambda_m * f_number)
        f_nyquist = 1.0 / (2.0 * pixel_pitch_m)
        if f_nyquist > f_cutoff:
            logger.warning(
                "Detector Nyquist frequency (%.0f cy/m) exceeds diffraction cutoff "
                "(%.0f cy/m) at λ=%.2f µm, f/%.1f. MTF at Nyquist is zero; "
                "this is physically correct but indicates the detector oversamples "
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

    # Store full MTF curves and EffectivePSF for downstream access.
    state = state.with_stage_output("performance", "mtf_freq_x", freq_x)
    state = state.with_stage_output("performance", "mtf_x", mtf_x)
    state = state.with_stage_output("performance", "mtf_freq_y", freq_y)
    state = state.with_stage_output("performance", "mtf_y", mtf_y)
    return state.with_stage_output("performance", "effective_psf", epsf)


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

    Delegates to ``gsd.compute_gsd`` for the math.  Skips gracefully when
    altitude or focal length is not set (e.g. lab/TVAC scenarios).
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

    result = compute_gsd(pitch_x_m, pitch_y_m, altitude_m, focal_length_m)
    state = state.with_metric("gsd_cross_track_m", result.cross_track_m)
    state = state.with_metric("gsd_along_track_m", result.along_track_m)
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
    state = state.with_metric("q_max", result.q_max)
    return state


def _compute_strehl_metric(
    state: ChainState,
    params: ParameterSet,
) -> ChainState:
    """Compute Strehl ratio (Marechal approximation) when WFE is available."""
    try:
        wfe_rms: float = params.get("optics.wfe_rms_waves")
        wfe_ref: float = params.get("optics.wfe_reference_wavelength_um")
        fmin: float = params.get("spectral_integration.filter_min_um")
        fmax: float = params.get("spectral_integration.filter_max_um")
    except (KeyError, TypeError):
        return state

    operating_um = 0.5 * (fmin + fmax)
    strehl = compute_strehl(wfe_rms, wfe_ref, operating_um)
    return state.with_metric("strehl", strehl)


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
    state = state.with_metric("niirs", result.niirs)
    state = state.with_stage_output("performance", "niirs_result", result)
    return state


class PerformanceStage:
    """Chain stage for performance metrics."""

    @property
    def name(self) -> str:
        return "performance"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        result = compute_snr(state)

        state = state.with_metric("snr", result.value)
        state = state.with_stage_output("performance", "snr_result", result)

        # Contrast SNR: ΔS / σ — positive for hot, negative for cold.
        contrast_result = compute_contrast_snr(state)
        state = state.with_metric("contrast_snr", contrast_result.value)
        state = state.with_stage_output(
            "performance",
            "contrast_snr_result",
            contrast_result,
        )

        # Compute spatial metrics if EffectivePSF is available from optics.
        state = _compute_spatial_metrics(state, params)

        # Ground sample distance (when orbital/airborne geometry is set).
        state = _compute_gsd_metrics(state, params)

        # Sampling parameter Q.
        state = _compute_q_metrics(state, params)

        # Strehl ratio (Marechal approximation).
        state = _compute_strehl_metric(state, params)

        # NEDT (Planck-derivative approximation, requires SNR).
        state = _compute_nedt_metric(state, params)

        # NIIRS / IIRS (requires GSD, RER, SNR from earlier in this stage).
        state = _compute_niirs_metric(state, params)

        # Saturation and dynamic range metrics.
        return _compute_saturation_metrics(state, params)
