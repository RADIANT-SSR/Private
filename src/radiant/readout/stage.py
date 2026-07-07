"""ReadoutStage — canonical 12-step readout chain.

Implements the full readout pipeline from
``docs/architecture/RADIANT_Detector_Complete.md`` §6:

1. Read per-pixel electron counts from DetectorStage
2. Apply TDI scaling (signal × N, shot × √N, read × 1, FPN × N)
3. Apply on-chip binning (signal × M, shot × √M, read × 1)
4. Check well saturation (clip at FWC)
5. Add read noise (once, post-TDI/on-chip-bin)
6. Add kTC noise (suppressed if CDS enabled)
7. Convert to DN: signal_dn = signal_e / gain
8. Add quantization noise
9. Check ADC saturation (clip at 2^bits − 1)
10. Apply off-chip binning
11. Apply coadd scaling
12. Emit all 16 NoiseTerm objects with final scaled values

**ReadoutStage is the sole emitter of NoiseTerm objects.** DetectorStage
stores raw per-pixel values in ``stage_outputs["detector"]``; this stage
applies all scaling and emits the final noise budget.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.noise_budget import (
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import NoiseTerm
from radiant.readout.binning_offchip import (
    offchip_scale_read_noise,
    offchip_scale_shot_noise,
    offchip_scale_signal,
)
from radiant.readout.binning_onchip import (
    onchip_scale_read_noise,
    onchip_scale_shot_noise,
    onchip_scale_signal,
)
from radiant.readout.coadds import (
    CoaddMode,
    coadd_scale_fpn,
    coadd_scale_signal,
    coadd_scale_temporal_noise,
)
from radiant.readout.saturation import (
    check_adc_saturation,
    check_well_saturation,
)
from radiant.readout.tdi_mtf import tdi_misalign_m, tdi_misalign_mtf_1d
from radiant.readout.tdi_scaling import (
    tdi_scale_fpn,
    tdi_scale_read_noise,
    tdi_scale_shot_noise,
    tdi_scale_signal,
)


def _scale_noise_term(
    raw_value: float,
    term_name: str,
    n_tdi: int,
    tdi_digital: bool,
    mx_on: int,
    my_on: int,
    px_off: int,
    py_off: int,
    n_coadds: int,
    coadd_mode: CoaddMode,
) -> float:
    """Apply TDI → on-chip bin → off-chip bin → coadd scaling to one noise term.

    Scaling rules depend on the noise category:
    - Shot-like (temporal, non-read, non-kTC, non-quant): × √N_tdi, × √M, × √P, coadd_temporal
    - Read noise: × 1 (analog TDI) or × √N (digital TDI), × 1 (on-chip), × √P (off-chip)
    - kTC noise: same as read noise
    - Quantization: × 1 (TDI), × 1 (on-chip), × √P (off-chip), coadd_temporal
    - FPN (spatial): × N_tdi (correlated along TDI column),
      × √M (on-chip, independent pixels), × √P (off-chip, independent pixels)
    """
    is_spatial = term_name in SPATIAL_TERMS
    is_read_like = term_name in ("read_noise", "ktc_reset", "quantization")

    if is_spatial:
        # FPN: binning is always independent pixels (√M, √P).
        # TDI scaling depends on mode AND noise source:
        #
        # Clutter is scene-correlated (same ground point in every TDI
        # stage), so it always scales as ×N regardless of TDI mode.
        #
        # PRNU/DSNU are detector-pixel properties:
        #   Analog (pushbroom): different physical pixels per stage →
        #     independent → √N scaling.
        #   Digital (same pixel re-read): same pixel → correlated → ×N.
        is_scene_correlated = term_name == "clutter"
        if tdi_digital or is_scene_correlated:
            v = tdi_scale_fpn(raw_value, n_tdi)  # ×N (correlated)
        else:
            v = tdi_scale_shot_noise(raw_value, n_tdi)  # ×√N (independent)
        v = onchip_scale_shot_noise(v, mx_on, my_on)  # √M (independent pixels)
        v = offchip_scale_shot_noise(v, px_off, py_off)  # √P (independent pixels)
        v = coadd_scale_fpn(v, n_coadds, coadd_mode)
    elif is_read_like:
        # Read/kTC/quant: injected once after TDI + on-chip bin
        v = tdi_scale_read_noise(raw_value, n_tdi, digital=tdi_digital)
        v = onchip_scale_read_noise(v)
        v = offchip_scale_read_noise(v, px_off, py_off)
        v = coadd_scale_temporal_noise(v, n_coadds, coadd_mode)
    else:
        # Shot-like temporal noise
        v = tdi_scale_shot_noise(raw_value, n_tdi)
        v = onchip_scale_shot_noise(v, mx_on, my_on)
        v = offchip_scale_shot_noise(v, px_off, py_off)
        v = coadd_scale_temporal_noise(v, n_coadds, coadd_mode)
    return v


class ReadoutStage:
    """Chain stage implementing the full canonical readout chain."""

    @property
    def name(self) -> str:
        return "readout"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # ---- 0. Read detector stage outputs ----
        det_out = state.stage_outputs.get("detector", {})
        signal_e: float = det_out.get("signal_e", 0.0)
        budget_raw: NoiseBudget | None = det_out.get("noise_budget_raw")

        if budget_raw is None:
            raise ValueError(
                "ReadoutStage: stage_outputs['detector']['noise_budget_raw'] "
                "is missing. DetectorStage must run before ReadoutStage to "
                "populate the raw NoiseBudget. Add DetectorStage to your "
                "ChainRunner or, in unit tests, set the budget directly via "
                "state.with_stage_output('detector', 'noise_budget_raw', ...)."
            )

        # ---- 1. Read readout parameters ----
        n_tdi: int = int(params.get("readout.n_tdi"))
        mx_on: int = int(params.get("readout.binning_x_onchip"))
        my_on: int = int(params.get("readout.binning_y_onchip"))
        px_off: int = int(params.get("readout.binning_x_offchip"))
        py_off: int = int(params.get("readout.binning_y_offchip"))
        n_coadds: int = int(params.get("readout.n_coadds"))
        coadd_mode = CoaddMode(params.get("readout.coadd_mode"))
        gain_e_per_dn: float = params.get("readout.gain_e_per_dn")
        adc_bits: int = int(params.get("readout.adc_bits"))
        fwc_e: float = params.get("readout.full_well_capacity_e")
        noise_regime: str = params.get("detector.noise_regime")
        tdi_digital: bool = params.get("readout.tdi_mode") == "digital"

        max_dn = (1 << adc_bits) - 1

        # ---- Read non-signal electron sources for well fill check ----
        dark_e: float = det_out.get("dark_e", 0.0)
        glow_e: float = det_out.get("glow_e", 0.0)

        # ---- 2. TDI scaling on signal ----
        signal_e = tdi_scale_signal(signal_e, n_tdi)

        # ---- 3. On-chip binning on signal ----
        signal_e = onchip_scale_signal(signal_e, mx_on, my_on)

        # ---- 4. Well saturation check ----
        # The well fills with signal + dark + glow.  Dark and glow
        # accumulate per-pixel per integration; TDI stages accumulate
        # independently.  Nearfield and stray electrons also fill the
        # well in reality, but are tracked separately for noise purposes
        # — the user controls nearfield via cold_stop_efficiency.
        m_onchip = mx_on * my_on
        non_signal_e = (dark_e + glow_e) * n_tdi * m_onchip
        total_well_e = signal_e + non_signal_e
        _, well_status = check_well_saturation(total_well_e, fwc_e)
        available_fwc = max(fwc_e - non_signal_e, 0.0)
        signal_e_pre_clip = signal_e
        signal_e = min(signal_e, available_fwc)

        # If well saturation clipped the signal, cap the signal_shot raw
        # term so that after TDI+onchip scaling it gives √(clipped_signal)
        # instead of √(signal_unclipped). Other shot terms (background,
        # nearfield, etc.) are independent of the signal well and not capped.
        if signal_e < signal_e_pre_clip and "signal_shot" in budget_raw.terms:
            effective_per_pixel = available_fwc / (n_tdi * m_onchip)
            terms_copy = dict(budget_raw.terms)
            terms_copy["signal_shot"] = math.sqrt(max(effective_per_pixel, 0.0))
            budget_raw = NoiseBudget(
                terms=terms_copy,
                sigma_temporal_e=budget_raw.sigma_temporal_e,
                sigma_spatial_e=budget_raw.sigma_spatial_e,
            )

        # ---- 5-6. Read noise and kTC are already in budget_raw ----
        # (injected at per-pixel level; scaling handled in _scale_noise_term)

        # ---- 7. Convert to DN ----
        signal_dn = signal_e / gain_e_per_dn

        # ---- 8. Quantization noise already in budget_raw ----

        # ---- 9. ADC saturation check ----
        signal_dn, adc_status = check_adc_saturation(signal_dn, max_dn)

        # ---- 10-11. Off-chip binning and coadds on signal ----
        signal_dn_offchip = offchip_scale_signal(signal_dn, px_off, py_off)
        signal_dn_final = coadd_scale_signal(signal_dn_offchip, n_coadds, coadd_mode)

        # Also track signal in electrons through the full chain for SNR
        signal_e_offchip = offchip_scale_signal(signal_e, px_off, py_off)
        signal_e_final = coadd_scale_signal(signal_e_offchip, n_coadds, coadd_mode)

        # Scale contrast_e through the same signal path for contrast SNR.
        si_out = state.stage_outputs.get("spectral_integration", {})
        contrast_e_raw: float = si_out.get("contrast_e", 0.0)
        contrast_e_scaled = tdi_scale_signal(contrast_e_raw, n_tdi)
        contrast_e_scaled = onchip_scale_signal(contrast_e_scaled, mx_on, my_on)
        # Contrast is not clipped by well/ADC — it's a differential quantity.
        contrast_e_scaled = offchip_scale_signal(contrast_e_scaled, px_off, py_off)
        contrast_e_final = coadd_scale_signal(contrast_e_scaled, n_coadds, coadd_mode)

        # ---- 12. Scale all 16 noise terms and emit NoiseTerms ----
        scaled_terms: dict[str, float] = {}
        for term_name, raw_value in budget_raw.terms.items():
            scaled_terms[term_name] = _scale_noise_term(
                raw_value=raw_value,
                term_name=term_name,
                n_tdi=n_tdi,
                tdi_digital=tdi_digital,
                mx_on=mx_on,
                my_on=my_on,
                px_off=px_off,
                py_off=py_off,
                n_coadds=n_coadds,
                coadd_mode=coadd_mode,
            )

        # Compute final temporal and spatial RSS
        temporal_var = sum(v**2 for k, v in scaled_terms.items() if k in TEMPORAL_TERMS)
        spatial_var = sum(v**2 for k, v in scaled_terms.items() if k in SPATIAL_TERMS)
        sigma_temporal_e = math.sqrt(temporal_var)
        sigma_spatial_e = math.sqrt(spatial_var)

        # Select total noise based on noise regime
        if noise_regime == "detection":
            sigma_total_e = math.sqrt(temporal_var + spatial_var)
        else:
            # "imaging" — temporal only (FPN calibrated out)
            sigma_total_e = sigma_temporal_e

        # Map noise term names to physical basis descriptions
        _PHYSICAL_BASIS: dict[str, str] = {
            "signal_shot": "Poisson",
            "background_shot": "Poisson",
            "nearfield_shot": "Poisson",
            "straylight_shot": "Poisson",
            "dark_shot": "Poisson",
            "gr_noise": "Generation-recombination",
            "johnson_noise": "Johnson thermal",
            "flicker_1f": "1/f flicker",
            "read_noise": "Gaussian",
            "ktc_reset": "kTC reset",
            "quantization": "ADC LSB/sqrt(12)",
            "prnu": "Photo-response non-uniformity",
            "dsnu": "Dark-signal non-uniformity",
            "clutter": "Scene clutter",
            "persistence_noise": "Image persistence",
            "glow_shot": "Poisson",
        }

        # Emit all 16 NoiseTerm objects
        for term_name, value_e in scaled_terms.items():
            if term_name in TEMPORAL_TERMS:
                contributes_to = ("temporal", "total")
            else:
                contributes_to = ("spatial", "total")

            state = state.with_noise(
                NoiseTerm(
                    name=term_name,
                    value_e=value_e,
                    origin_frame="photoelectrons",
                    physical_basis=_PHYSICAL_BASIS.get(term_name, "unknown"),
                    contributes_to=contributes_to,
                )
            )

        # ---- MTF product path: TDI misalignment ----
        freq_mrad = state.spatial_freq_cycles_per_mrad
        if freq_mrad is not None:
            misalign_pix: float = params.get("readout.tdi_misalign_pixels")
            pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
            focal_length_m: float = params.get("optics.focal_length_m")
            freq_m = freq_mrad / (focal_length_m * 1e3)

            if misalign_pix > 0.0:
                misalign_m = tdi_misalign_m(misalign_pix, pixel_pitch_m)
                # TDI misalignment affects cross-scan (x) axis only.
                mtf_tdi_x = tdi_misalign_mtf_1d(freq_m, misalign_m)
                mtf_tdi_y = np.ones_like(freq_m)
            else:
                mtf_tdi_x = np.ones_like(freq_m)
                mtf_tdi_y = np.ones_like(freq_m)
            state = state.with_mtf("mtf_tdi_x", mtf_tdi_x)
            state = state.with_mtf("mtf_tdi_y", mtf_tdi_y)

        # ---- Store stage outputs ----
        state = state.with_stage_output("readout", "contrast_e_final", contrast_e_final)
        state = state.with_stage_output("readout", "signal_e_final", signal_e_final)
        state = state.with_stage_output("readout", "signal_dn_final", signal_dn_final)
        state = state.with_stage_output("readout", "signal_dn_pre_coadd", signal_dn)
        state = state.with_stage_output("readout", "well_status", well_status.value)
        state = state.with_stage_output("readout", "adc_status", adc_status.value)
        state = state.with_stage_output("readout", "sigma_temporal_e", sigma_temporal_e)
        state = state.with_stage_output("readout", "sigma_spatial_e", sigma_spatial_e)
        state = state.with_stage_output("readout", "sigma_total_e", sigma_total_e)
        state = state.with_stage_output("readout", "noise_regime", noise_regime)
        state = state.with_stage_output("readout", "scaled_noise_terms", scaled_terms)
        state = state.with_stage_output(
            "readout",
            "read_noise_e",
            scaled_terms.get("read_noise", 0.0),
        )
        return state.with_stage_output(
            "readout",
            "quantization_noise_e",
            scaled_terms.get("quantization", 0.0),
        )
