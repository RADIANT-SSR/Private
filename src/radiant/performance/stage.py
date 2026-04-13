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

    Reads the EffectivePSF from ``stage_outputs["optics"]["effective_psf"]``.
    Skips gracefully if it is not available.
    """
    try:
        epsf = state.stage_outputs["optics"]["effective_psf"]
    except KeyError:
        logger.debug("EffectivePSF not available from optics stage; skipping spatial metrics.")
        return state

    try:
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
    except (KeyError, TypeError):
        logger.debug("Pixel pitch not available; skipping spatial metrics.")
        return state

    # Compute spatial metrics from EffectivePSF.
    fwhm_x = epsf.fwhm("x")
    fwhm_y = epsf.fwhm("y")
    rer = epsf.rer()
    ee_1x1 = epsf.ensquared_energy_nxn(1)
    ee_3x3 = epsf.ensquared_energy_nxn(3)

    # MTF at Nyquist.
    freq, mtf = epsf.mtf_1d("x")
    mtf_ny = mtf_at_nyquist(freq, mtf, pixel_pitch_m)

    # Write metrics.
    state = state.with_metric("fwhm_x_m", fwhm_x)
    state = state.with_metric("fwhm_y_m", fwhm_y)
    state = state.with_metric("rer", rer)
    state = state.with_metric("ee_1x1", ee_1x1)
    state = state.with_metric("ee_3x3", ee_3x3)
    state = state.with_metric("mtf_at_nyquist", mtf_ny)

    # Store EffectivePSF in performance outputs for downstream access.
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

        # Saturation and dynamic range metrics.
        return _compute_saturation_metrics(state, params)
