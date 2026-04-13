"""ReadoutStage — canonical 12-step readout chain.

Implements the full readout pipeline from
``docs/RADIANT_Detector_Complete.md`` §6:

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

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import NoiseTerm
from radiant.detector.noise import (
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)
from radiant.readout.binning import (
    offchip_scale_fpn,
    offchip_scale_read_noise,
    offchip_scale_shot_noise,
    offchip_scale_signal,
    onchip_scale_fpn,
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
from radiant.readout.tdi import (
    tdi_scale_fpn,
    tdi_scale_read_noise,
    tdi_scale_shot_noise,
    tdi_scale_signal,
)


def _scale_noise_term(
    raw_value: float,
    term_name: str,
    n_tdi: int,
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
    - Read noise: × 1 (TDI), × 1 (on-chip), × √P (off-chip), coadd_temporal
    - kTC noise: same as read noise
    - Quantization: × 1 (TDI), × 1 (on-chip), × √P (off-chip), coadd_temporal
    - FPN (spatial): × N_tdi, × M (on-chip), × P (off-chip), coadd_fpn
    """
    is_spatial = term_name in SPATIAL_TERMS
    is_read_like = term_name in ("read_noise", "ktc_reset", "quantization")

    if is_spatial:
        # FPN scales linearly with signal at every stage
        v = tdi_scale_fpn(raw_value, n_tdi)
        v = onchip_scale_fpn(v, mx_on, my_on)
        v = offchip_scale_fpn(v, px_off, py_off)
        v = coadd_scale_fpn(v, n_coadds, coadd_mode)
    elif is_read_like:
        # Read/kTC/quant: injected once after TDI + on-chip bin
        v = tdi_scale_read_noise(raw_value)
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

        # If DetectorStage didn't run (legacy/test), build a minimal budget.
        if budget_raw is None:
            from radiant.detector.noise import compute_noise_budget

            budget_raw = compute_noise_budget(
                signal_e=signal_e,
                read_noise_e_rms=params.get("readout.read_noise_e_rms"),
                gain_e_per_dn=params.get("readout.gain_e_per_dn"),
                cds_enabled=bool(params.get("readout.cds_enabled")),
                node_capacitance_F=params.get("readout.node_capacitance_F"),
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

        max_dn = (1 << adc_bits) - 1

        # ---- 2. TDI scaling on signal ----
        signal_e = tdi_scale_signal(signal_e, n_tdi)

        # ---- 3. On-chip binning on signal ----
        signal_e = onchip_scale_signal(signal_e, mx_on, my_on)

        # ---- 4. Well saturation check ----
        signal_e, well_status = check_well_saturation(signal_e, fwc_e)

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

        # ---- 12. Scale all 16 noise terms and emit NoiseTerms ----
        scaled_terms: dict[str, float] = {}
        for term_name, raw_value in budget_raw.terms.items():
            scaled_terms[term_name] = _scale_noise_term(
                raw_value=raw_value,
                term_name=term_name,
                n_tdi=n_tdi,
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

        # ---- Store stage outputs ----
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
