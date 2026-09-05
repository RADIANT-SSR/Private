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

import logging
import math
import warnings

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.noise_budget import (
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)
from radiant.core.parameters import ParameterSet, Provenance, UnknownParameterError
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
from radiant.readout.counting_quantization import (
    counting_quantization_noise_e,
    residue_adc_gain_e_per_dn,
)
from radiant.readout.counting_well import (
    convert_to_counts,
    counting_saturation,
    effective_well_e,
    packet_reset_noise_e,
)
from radiant.readout.electronics_mtf import electronics_kernel_2d, electronics_mtf_1d
from radiant.readout.errors import ReadoutValidationError
from radiant.readout.frame_timing import compute_frame_timing
from radiant.readout.saturation import (
    SaturationStatus,
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

logger = logging.getLogger(__name__)

# Parameters meaningful only under readout.architecture = "digital_counting"
# (Gap 117, docs/plans/Digital_Pixel_Readout_Plan.md §3). Explicitly setting
# any of them under "analog_well" is an over-specification error, the same
# posture as Rule 5's reflectance-plus-emissivity rejection.
_COUNTING_ONLY_PARAMS: tuple[str, ...] = (
    "readout.counter_bits",
    "readout.count_packet_e",
    "readout.residue_readout",
    "readout.max_count_rate_hz",
)


def _is_explicitly_set(params: ParameterSet, name: str) -> bool:
    """True when *name* was supplied by the user/config rather than defaulted."""
    return params.get_resolved(name).provenance is not Provenance.DEFAULT


def _validate_architecture_params(params: ParameterSet, architecture: str) -> None:
    """Cross-parameter validation for the readout-architecture dispatch (Rule 16).

    - ``analog_well``: no counting-only parameter may be explicitly set.
    - ``digital_counting``: ``count_packet_e`` is required (> 0), and
      ``full_well_capacity_e`` may not be explicitly set — the effective well
      is 2^counter_bits x count_packet_e, so an explicit analog full well
      over-specifies the system (its schema default passes silently).
    """
    if architecture == "analog_well":
        over_specified = [p for p in _COUNTING_ONLY_PARAMS if _is_explicitly_set(params, p)]
        if over_specified:
            raise ReadoutValidationError(
                f"ReadoutStage: counting-only parameter(s) {over_specified} are "
                f"explicitly set while readout.architecture = 'analog_well'. "
                f"These parameters describe the digital-pixel (DROIC) counting "
                f"chain and have no meaning for an analog charge well — setting "
                f"them over-specifies the readout. Either set "
                f"readout.architecture = 'digital_counting' or remove the "
                f"counting parameter(s)."
            )
        return

    # digital_counting
    if _is_explicitly_set(params, "readout.full_well_capacity_e"):
        fwc = params.get("readout.full_well_capacity_e")
        raise ReadoutValidationError(
            f"ReadoutStage: readout.full_well_capacity_e = {fwc:.4g} e- is "
            f"explicitly set while readout.architecture = 'digital_counting'. "
            f"Under counting the effective well is 2^counter_bits x "
            f"count_packet_e — an independent analog full well over-specifies "
            f"the system. Remove full_well_capacity_e (or select "
            f"readout.architecture = 'analog_well')."
        )
    count_packet_e: float = params.get("readout.count_packet_e")
    if count_packet_e <= 0.0:
        raise ReadoutValidationError(
            "ReadoutStage: readout.count_packet_e is required when "
            "readout.architecture = 'digital_counting' — the charge packet per "
            "count sets the effective well (2^counter_bits x count_packet_e) "
            "and the quantization noise, and it has no sensible default. Set "
            "readout.count_packet_e to the ROIC's charge-subtraction quantum "
            "in e- (> 0)."
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


# Map noise term names to physical basis descriptions (shared by the
# analog_well and digital_counting branches).
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
    "counting_quantization": "Packet or residue-ADC LSB/sqrt(12)",
    "packet_reset": "sqrt(n_counts) x kTC reset",
    "prnu": "Photo-response non-uniformity",
    "dsnu": "Dark-signal non-uniformity",
    "clutter": "Scene clutter",
    "persistence_noise": "Image persistence",
    "glow_shot": "Poisson",
}

# Canonical display units for this stage's scalar ``stage_outputs`` (CU-118) —
# declared next to the ``with_stage_output(...)`` emission sites and aggregated by
# ``radiant.api.stage_output_units``. "" marks a dimensionless numeric (bare number).
OUTPUT_UNITS: dict[str, str] = {
    "electronics_sigma_m": "m",
    "counts": "",
    "count_packet_e": "e-",
    "effective_well_e": "e-",
    "contrast_e_final": "e-",
    "signal_e_final": "e-",
    "signal_dn_final": "DN",
    "signal_dn_pre_coadd": "DN",
    "gain_e_per_dn": "e-/DN",
    "adc_full_scale_e": "e-",
    "matched_gain_e_per_dn": "e-/DN",
    "adc_well_match_ratio": "",
    "well_fill_fraction": "",
    "total_well_e": "e-",
    "full_well_capacity_e": "e-",
    "sigma_temporal_e": "e-",
    "sigma_spatial_e": "e-",
    "sigma_total_e": "e-",
    "read_noise_e": "e-",
    "quantization_noise_e": "e-",
    "frame_period_s": "s",
    "frame_rate_hz": "Hz",
    "duty_cycle": "",
    "frame_period_defaulted": "",
}


class ReadoutStage:
    """Chain stage implementing the full canonical readout chain."""

    @property
    def name(self) -> str:
        return "readout"

    def _emit_mtf_product_terms(self, state: ChainState, params: ParameterSet) -> ChainState:
        """MTF product path: TDI misalignment + electronics (Rule 4 both paths).

        Shared by the analog_well and digital_counting branches — TDI
        mis-registration MTF is retained under count-domain TDI (ruling D4:
        timing mis-registration exists regardless of charge vs count
        transfer) and the electronics blur is ROIC-output-side either way.
        """
        freq_mrad = state.spatial_freq_cycles_per_mrad
        if freq_mrad is None:
            return state
        misalign_pix: float = params.get("readout.tdi_misalign_pixels")
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
        focal_length_m: float = params.get("optics.focal_length_m")
        freq_m = freq_mrad / (focal_length_m * 1e-3)

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

        # ---- Electronics (amplifier bandwidth), Rule 4 both paths ----
        # Product path: analytic term here. PSF path: the matching
        # Gaussian-in-x kernel is built here (sized to the ePSF grid)
        # and applied by PerformanceStage, same pattern as IPC.
        elec_sigma_m: float = params.get("readout.electronics_sigma_um")
        state = state.with_mtf("mtf_electronics_x", electronics_mtf_1d(freq_m, elec_sigma_m))
        state = state.with_mtf("mtf_electronics_y", np.ones_like(freq_m))
        if elec_sigma_m > 0.0:
            plat_out = state.stage_outputs.get("platform", {})
            epsf = plat_out.get("effective_psf")
            if epsf is None:
                epsf = state.stage_outputs.get("optics", {}).get("effective_psf")
            if epsf is not None:
                npix = int(math.ceil(6.0 * elec_sigma_m / epsf.sample_spacing_m)) | 1
                npix = max(3, min(npix, epsf.data.shape[0]))
                kern = electronics_kernel_2d(npix, epsf.sample_spacing_m, elec_sigma_m)
                state = state.with_stage_output("readout", "electronics_kernel", kern)
        return state.with_stage_output("readout", "electronics_sigma_m", elec_sigma_m)

    def _emit_frame_timing(
        self,
        state: ChainState,
        integration_time_s: float | None,
        frame_period_s: float,
    ) -> ChainState:
        """Publish frame-timing outputs (RADIANT_Conventions.md §4); shared."""
        if integration_time_s is None:
            return state
        frame_timing = compute_frame_timing(integration_time_s, frame_period_s, warn=False)
        state = state.with_stage_output("readout", "frame_period_s", frame_timing.frame_period_s)
        state = state.with_stage_output("readout", "frame_rate_hz", frame_timing.frame_rate_hz)
        state = state.with_stage_output("readout", "duty_cycle", frame_timing.duty_cycle)
        return state.with_stage_output(
            "readout", "frame_period_defaulted", frame_timing.frame_period_defaulted
        )

    def _run_digital_counting(self, state: ChainState, params: ParameterSet) -> ChainState:
        """Digital-pixel (DROIC) counting readout — plan §2, Gap 117 Phase 2.

        Everything upstream is unchanged (charge in e- from DetectorStage);
        this branch replaces the charge-well saturation with the counting
        bound, the ADC quantization with the packet/residue-ADC branch, the
        per-frame kTC with the per-packet reset accumulation, and the DN
        conversion with the ruling-D2 word semantics. TDI/binning/coadd
        scaling and the MTF product terms are shared with the analog path.
        """
        # ---- 0. Read detector stage outputs ----
        det_out = state.stage_outputs.get("detector", {})
        signal_e: float = det_out.get("signal_e", 0.0)
        budget_raw: NoiseBudget | None = det_out.get("noise_budget_raw")
        if budget_raw is None:
            raise ReadoutValidationError(
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
        adc_bits: int = int(params.get("readout.adc_bits"))
        counter_bits: int = int(params.get("readout.counter_bits"))
        count_packet_e: float = params.get("readout.count_packet_e")
        residue_readout: bool = bool(params.get("readout.residue_readout"))
        max_count_rate_hz: float = params.get("readout.max_count_rate_hz")
        noise_regime: str = params.get("detector.noise_regime")
        tdi_digital: bool = params.get("readout.tdi_mode") == "digital"
        frame_period_s: float = params.get("readout.frame_period_s")
        try:
            integration_time_s: float | None = params.get("spectral_integration.integration_time_s")
        except (UnknownParameterError, KeyError):
            integration_time_s = None
            logger.debug(
                "ReadoutStage: spectral_integration.integration_time_s unavailable "
                "(partial chain); skipping frame-timing outputs."
            )

        # ---- Counting saturation bound (plan §2.3) ----
        if max_count_rate_hz > 0.0 and integration_time_s is None:
            raise ReadoutValidationError(
                "ReadoutStage: readout.max_count_rate_hz > 0 sets a comparator "
                "dead-time charge ceiling f_max x t_int x Q_pkt, which needs "
                "spectral_integration.integration_time_s — unavailable in this "
                "(partial) chain. Provide the integration time or set "
                "readout.max_count_rate_hz = 0.0 (no ceiling)."
            )
        if integration_time_s is not None:
            q_sat, bound_mechanism = counting_saturation(
                counter_bits, count_packet_e, max_count_rate_hz, integration_time_s
            )
        else:
            q_sat = effective_well_e(counter_bits, count_packet_e)
            bound_mechanism = "rollover"
        effective_well = effective_well_e(counter_bits, count_packet_e)

        # ---- Read non-signal electron sources for the counting-well check ----
        dark_e: float = det_out.get("dark_e", 0.0)
        glow_e: float = det_out.get("glow_e", 0.0)
        background_e: float = det_out.get("background_e", 0.0)
        regime = state.stage_outputs.get("optics", {}).get("regime")
        regime_value = getattr(regime, "value", regime)

        # ---- 2-3. TDI and on-chip binning on signal (count-domain: same
        # accumulation arithmetic; ruling D4 keeps the mis-registration MTF) ----
        signal_e = tdi_scale_signal(signal_e, n_tdi)
        signal_e = onchip_scale_signal(signal_e, mx_on, my_on)

        # ---- 4. Counting saturation check (Gap 73 well-fill semantics kept) ----
        m_onchip = mx_on * my_on
        non_signal_e = (dark_e + glow_e) * n_tdi * m_onchip
        if regime_value == "point_source":
            non_signal_e += background_e * n_tdi * m_onchip
        total_well_e = signal_e + non_signal_e
        _, well_status = check_well_saturation(total_well_e, q_sat)
        available_capacity = max(q_sat - non_signal_e, 0.0)
        signal_e_pre_clip = signal_e
        signal_e = min(signal_e, available_capacity)
        saturation_mechanism = (
            bound_mechanism if well_status is SaturationStatus.CLIPPED else "none"
        )

        if well_status is SaturationStatus.CLIPPED:
            # Rule 17: no silent clip (Gap 65 posture, counting flavor).
            if bound_mechanism == "dead_time":
                remedy = (
                    "Reduce spectral_integration.integration_time_s or the flux, "
                    "or raise readout.max_count_rate_hz if the comparator is faster."
                )
            else:
                remedy = (
                    "Reduce spectral_integration.integration_time_s, reduce "
                    "aperture/throughput, or raise readout.counter_bits / "
                    "readout.count_packet_e for a deeper effective well."
                )
            warnings.warn(
                f"ReadoutStage: digital-counting saturation ({bound_mechanism}) — "
                f"signal + dark + glow"
                f"{' + background pedestal' if regime_value == 'point_source' else ''} = "
                f"{total_well_e:.4g} e- exceeds the counting bound {q_sat:.4g} e- "
                f"(2^{counter_bits} x {count_packet_e:.4g} e-/count effective well"
                f"{'; dead-time ceiling governs' if bound_mechanism == 'dead_time' else ''}). "
                f"Signal clipped to {signal_e:.4g} e-. Downstream SNR/NEDT/NIIRS "
                f"reflect the CLIPPED signal. {remedy} "
                f"(readout.well_status = 'clipped'; readout.saturation_mechanism = "
                f"'{bound_mechanism}'; Gap 117)",
                UserWarning,
                stacklevel=2,
            )

        # Cap signal_shot to the clipped signal, mirroring the analog branch.
        if signal_e < signal_e_pre_clip and "signal_shot" in budget_raw.terms:
            effective_per_pixel = available_capacity / (n_tdi * m_onchip)
            terms_copy = dict(budget_raw.terms)
            terms_copy["signal_shot"] = math.sqrt(max(effective_per_pixel, 0.0))
            budget_raw = NoiseBudget(
                terms=terms_copy,
                sigma_temporal_e=budget_raw.sigma_temporal_e,
                sigma_spatial_e=budget_raw.sigma_spatial_e,
            )

        # ---- 5. Count conversion (plan §2.1) on the accumulated signal ----
        conversion = convert_to_counts(signal_e, count_packet_e)

        # ---- 6-7. DN semantics (ruling D2): DN digitizes the total signal
        # Q_pkt·n + Q_res, following the residue flag. Residue on: combined
        # word at gain Q_pkt/2^M e-/DN (signal_e/gain = n·2^M + res/gain
        # exactly); residue off: bare counter at gain Q_pkt e-/DN. The
        # sub-LSB rounding is carried by the counting_quantization noise
        # term, matching the analog convention of an unrounded DN value.
        if residue_readout:
            gain_eff_e_per_dn = residue_adc_gain_e_per_dn(count_packet_e, adc_bits)
        else:
            gain_eff_e_per_dn = count_packet_e
        signal_dn = signal_e / gain_eff_e_per_dn
        # No separate ADC saturation check: the counter IS the ADC; rollover
        # is handled by the counting-well clip above. adc_status stays "ok",
        # and the analog ADC↔well match diagnostics are meaningless here
        # (plan §2.3) — deliberately not published.

        # ---- 8-9. Off-chip binning and coadds on signal ----
        signal_dn_offchip = offchip_scale_signal(signal_dn, px_off, py_off)
        signal_dn_final = coadd_scale_signal(signal_dn_offchip, n_coadds, coadd_mode)
        signal_e_offchip = offchip_scale_signal(signal_e, px_off, py_off)
        signal_e_final = coadd_scale_signal(signal_e_offchip, n_coadds, coadd_mode)

        # Contrast through the same signal path (differential — never clipped).
        si_out = state.stage_outputs.get("spectral_integration", {})
        contrast_e_raw: float = si_out.get("contrast_e", 0.0)
        contrast_e_scaled = tdi_scale_signal(contrast_e_raw, n_tdi)
        contrast_e_scaled = onchip_scale_signal(contrast_e_scaled, mx_on, my_on)
        contrast_e_scaled = offchip_scale_signal(contrast_e_scaled, px_off, py_off)
        contrast_e_final = coadd_scale_signal(contrast_e_scaled, n_coadds, coadd_mode)

        # ---- 10. Noise terms: swap the analog conversion terms for the
        # counting pair, scale the rest exactly as the analog branch does ----
        raw_terms = dict(budget_raw.terms)
        sigma_ktc_raw = raw_terms.pop("ktc_reset", 0.0)  # already CDS-gated
        raw_terms.pop("quantization", None)  # analog-ADC term: replaced

        scaled_terms: dict[str, float] = {}
        for term_name, raw_value in raw_terms.items():
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
        # Counting terms are computed at the final accumulated charge level
        # (n_counts already reflects TDI + on-chip binning), so only the
        # post-conversion scalings apply: off-chip binning (independent
        # reads, √P) and coadds — the same rules the analog branch applies
        # to its read-like terms.
        counting_q = counting_quantization_noise_e(
            count_packet_e, residue_readout=residue_readout, adc_bits=adc_bits
        )
        packet_r = packet_reset_noise_e(conversion.n_counts, sigma_ktc_raw)
        for term_name, value in (
            ("counting_quantization", counting_q),
            ("packet_reset", packet_r),
        ):
            value = offchip_scale_read_noise(value, px_off, py_off)
            value = coadd_scale_temporal_noise(value, n_coadds, coadd_mode)
            scaled_terms[term_name] = value

        temporal_var = sum(v**2 for k, v in scaled_terms.items() if k in TEMPORAL_TERMS)
        spatial_var = sum(v**2 for k, v in scaled_terms.items() if k in SPATIAL_TERMS)
        sigma_temporal_e = math.sqrt(temporal_var)
        sigma_spatial_e = math.sqrt(spatial_var)
        if noise_regime == "detection":
            sigma_total_e = math.sqrt(temporal_var + spatial_var)
        else:
            sigma_total_e = sigma_temporal_e

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

        # ---- MTF product path (shared; D4 retains TDI mis-registration) ----
        state = self._emit_mtf_product_terms(state, params)

        # ---- Store stage outputs ----
        state = state.with_stage_output("readout", "architecture", "digital_counting")
        state = state.with_stage_output("readout", "counts", conversion.n_counts)
        state = state.with_stage_output("readout", "count_packet_e", count_packet_e)
        state = state.with_stage_output("readout", "effective_well_e", effective_well)
        state = state.with_stage_output("readout", "saturation_mechanism", saturation_mechanism)
        state = state.with_stage_output("readout", "contrast_e_final", contrast_e_final)
        state = state.with_stage_output("readout", "signal_e_final", signal_e_final)
        state = state.with_stage_output("readout", "signal_dn_final", signal_dn_final)
        state = state.with_stage_output("readout", "signal_dn_pre_coadd", signal_dn)
        state = state.with_stage_output("readout", "gain_e_per_dn", gain_eff_e_per_dn)
        state = state.with_stage_output("readout", "well_status", well_status.value)
        # full_well_capacity_e carries the *counting* saturation bound so
        # every downstream well consumer (well_fill_fraction, GUI banner,
        # well-margin and dynamic-range metrics) sees one consistent
        # saturation signal (plan §2.3).
        state = state.with_stage_output("readout", "well_fill_fraction", total_well_e / q_sat)
        state = state.with_stage_output("readout", "total_well_e", total_well_e)
        state = state.with_stage_output("readout", "full_well_capacity_e", q_sat)
        state = state.with_stage_output("readout", "adc_status", SaturationStatus.OK.value)
        state = state.with_stage_output("readout", "sigma_temporal_e", sigma_temporal_e)
        state = state.with_stage_output("readout", "sigma_spatial_e", sigma_spatial_e)
        state = state.with_stage_output("readout", "sigma_total_e", sigma_total_e)
        state = state.with_stage_output("readout", "noise_regime", noise_regime)
        state = state.with_stage_output("readout", "scaled_noise_terms", scaled_terms)
        state = self._emit_frame_timing(state, integration_time_s, frame_period_s)
        state = state.with_stage_output(
            "readout", "read_noise_e", scaled_terms.get("read_noise", 0.0)
        )
        return state.with_stage_output(
            "readout",
            "quantization_noise_e",
            scaled_terms.get("counting_quantization", 0.0),
        )

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # ---- Architecture dispatch (Gap 117 Phase 0) ----
        # Validate the architecture-scoped parameter combination before any
        # physics runs (Rule 16), then dispatch. The digital_counting branch
        # is schema-only until Phase 1 of the plan lands; the analog_well
        # branch below is byte-for-byte the pre-dispatch behavior.
        architecture: str = params.get("readout.architecture")
        _validate_architecture_params(params, architecture)
        if architecture == "digital_counting":
            return self._run_digital_counting(state, params)

        # ---- 0. Read detector stage outputs ----
        det_out = state.stage_outputs.get("detector", {})
        signal_e: float = det_out.get("signal_e", 0.0)
        budget_raw: NoiseBudget | None = det_out.get("noise_budget_raw")

        if budget_raw is None:
            raise ReadoutValidationError(
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
        frame_period_s: float = params.get("readout.frame_period_s")
        # Integration time lives in the spectral_integration namespace. In the
        # full chain it is always present; guard so a partial-chain readout run
        # (unit tests with a readout+detector-only ParameterSet) skips the
        # frame-timing publish rather than crashing — it is an inspection-only
        # output with no downstream physics consumer.
        try:
            integration_time_s: float | None = params.get("spectral_integration.integration_time_s")
        except (UnknownParameterError, KeyError):
            integration_time_s = None
            logger.debug(
                "ReadoutStage: spectral_integration.integration_time_s unavailable "
                "(partial chain); skipping frame-timing outputs."
            )

        max_dn = (1 << adc_bits) - 1

        # ---- ADC↔well match diagnostics (finding 10) ----
        # The three readout knobs — gain, ADC bit depth, full-well — are independent
        # inputs, NOT a derived group: gain = full_well / 2^bits is the *matched-ADC*
        # design target, an engineering choice, not a physical law (unlike ε = 1 − R,
        # Rule 5), and non-matched ADCs (deep well, partial digitization; or shallow
        # well, oversampled) are legitimate. These read-only outputs expose the
        # relationship so a user can see how their ADC range compares to the well:
        #   • adc_full_scale_e   = max_dn · gain  — the largest signal the ADC digitizes
        #   • matched_gain_e_per_dn = full_well / 2^bits — the gain that makes them equal
        #   • adc_well_match_ratio  = adc_full_scale / full_well — 1.0 when matched,
        #        <1 the ADC cannot reach the full well (undersampled), >1 wasted range.
        adc_full_scale_e = max_dn * gain_e_per_dn
        matched_gain_e_per_dn = fwc_e / float(1 << adc_bits)
        adc_well_match_ratio = adc_full_scale_e / fwc_e if fwc_e > 0.0 else float("inf")
        # Warn only on an *egregious* mismatch (>10× either way) — a matched or merely
        # suboptimal ADC (the flagship configs sit at 0.66–1.05) stays quiet; a config
        # whose ADC reaches only a few percent of the well (or vastly overshoots it) is
        # almost always an oversight, so point at the matched gain.
        if adc_well_match_ratio < 0.1 or adc_well_match_ratio > 10.0:
            warnings.warn(
                f"ReadoutStage: ADC full-scale ({adc_full_scale_e:.4g} e- = {adc_bits}-bit "
                f"at {gain_e_per_dn:.4g} e-/DN) is badly mismatched to the full well "
                f"({fwc_e:.4g} e-) — adc_well_match_ratio = {adc_well_match_ratio:.3g}. "
                f"For a matched ADC set readout.gain_e_per_dn ≈ "
                f"{matched_gain_e_per_dn:.4g} e-/DN (= full_well / 2^bits), or adjust "
                f"readout.adc_bits / readout.full_well_capacity_e. (finding 10)",
                UserWarning,
                stacklevel=2,
            )

        # ---- Read non-signal electron sources for well fill check ----
        dark_e: float = det_out.get("dark_e", 0.0)
        glow_e: float = det_out.get("glow_e", 0.0)
        background_e: float = det_out.get("background_e", 0.0)
        regime = state.stage_outputs.get("optics", {}).get("regime")
        regime_value = getattr(regime, "value", regime)

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
        # Gap 73: in point-source regime signal_e is the target-only excess,
        # so the full-pixel background pedestal is additional well charge that
        # accumulates like signal (TDI stages + on-chip binning). In extended
        # and sub-pixel regimes the background is already inside signal_e, so
        # it must NOT be added again here.
        if regime_value == "point_source":
            non_signal_e += background_e * n_tdi * m_onchip
        total_well_e = signal_e + non_signal_e
        _, well_status = check_well_saturation(total_well_e, fwc_e)
        available_fwc = max(fwc_e - non_signal_e, 0.0)
        signal_e_pre_clip = signal_e
        signal_e = min(signal_e, available_fwc)

        # Rule 17: clipping to a valid range requires at minimum a
        # UserWarning. Silent well saturation cost three scenarios
        # (6.1, 6.2, 8.2) real debugging time: two configs that should
        # produce different SNR instead produce bit-identical, clipped
        # results that read as "no effect" (Gap 65).
        if well_status is SaturationStatus.CLIPPED:
            warnings.warn(
                f"ReadoutStage: full well saturated — signal + dark + glow"
                f"{' + background pedestal' if regime_value == 'point_source' else ''} = "
                f"{total_well_e:.4g} e- exceeds full_well_capacity_e = {fwc_e:.4g} e- "
                f"(fill fraction {total_well_e / fwc_e:.2f}). Signal clipped to "
                f"{signal_e:.4g} e-. Downstream SNR/NEDT/NIIRS reflect the CLIPPED "
                f"signal and will not respond to scene/atmosphere changes. Reduce "
                f"spectral_integration.integration_time_s, reduce aperture/throughput, "
                f"or raise readout.full_well_capacity_e if this well is unrealistic. "
                f"(readout.well_status = 'clipped'; Gap 65)",
                UserWarning,
                stacklevel=2,
            )

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
        signal_dn_pre_clip = signal_dn
        signal_dn, adc_status = check_adc_saturation(signal_dn, max_dn)
        # Rule 17: same silent-clip warning as the well check above.
        if adc_status is SaturationStatus.CLIPPED:
            warnings.warn(
                f"ReadoutStage: ADC saturated — signal {signal_dn_pre_clip:.4g} DN "
                f"exceeds full scale {max_dn} DN ({adc_bits}-bit at "
                f"{gain_e_per_dn:.4g} e-/DN). Signal clipped to {max_dn} DN. "
                f"Increase readout.gain_e_per_dn or readout.adc_bits, or reduce "
                f"the signal (integration time, aperture). "
                f"(readout.adc_status = 'clipped'; Gap 65)",
                UserWarning,
                stacklevel=2,
            )

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

        # ---- MTF product path: TDI misalignment + electronics ----
        state = self._emit_mtf_product_terms(state, params)
        # ---- Store stage outputs ----
        state = state.with_stage_output("readout", "architecture", "analog_well")
        state = state.with_stage_output("readout", "contrast_e_final", contrast_e_final)
        state = state.with_stage_output("readout", "signal_e_final", signal_e_final)
        state = state.with_stage_output("readout", "signal_dn_final", signal_dn_final)
        state = state.with_stage_output("readout", "signal_dn_pre_coadd", signal_dn)
        # Stored so the post_readout->dn transfer factor stays computable when
        # the well saturates and signal_e_final = 0 (Gap 73 well-fill).
        state = state.with_stage_output("readout", "gain_e_per_dn", gain_e_per_dn)
        # ADC↔well match diagnostics (finding 10) — read-only; see the computation above.
        state = state.with_stage_output("readout", "adc_full_scale_e", adc_full_scale_e)
        state = state.with_stage_output("readout", "matched_gain_e_per_dn", matched_gain_e_per_dn)
        state = state.with_stage_output("readout", "adc_well_match_ratio", adc_well_match_ratio)
        state = state.with_stage_output("readout", "well_status", well_status.value)
        # CU-101: publish the supporting well-charge numbers so the
        # ChainResult.well_status() surface (GUI saturation banner) carries
        # everything a renderer needs — the clip state AND how full the well
        # is — with each value serialization-safe (survives save/load).
        state = state.with_stage_output("readout", "well_fill_fraction", total_well_e / fwc_e)
        state = state.with_stage_output("readout", "total_well_e", total_well_e)
        state = state.with_stage_output("readout", "full_well_capacity_e", fwc_e)
        state = state.with_stage_output("readout", "adc_status", adc_status.value)
        state = state.with_stage_output("readout", "sigma_temporal_e", sigma_temporal_e)
        state = state.with_stage_output("readout", "sigma_spatial_e", sigma_spatial_e)
        state = state.with_stage_output("readout", "sigma_total_e", sigma_total_e)
        state = state.with_stage_output("readout", "noise_regime", noise_regime)
        state = state.with_stage_output("readout", "scaled_noise_terms", scaled_terms)

        # Frame timing (RADIANT_Conventions.md §4): derive frame rate and duty
        # cycle from the integration time and the (optional) frame period, and
        # publish them for inspection. warn=False keeps an ordinary default
        # evaluation warning-free (CU-166); the unset case is surfaced by
        # frame_period_defaulted instead of a per-evaluate log line.
        state = self._emit_frame_timing(state, integration_time_s, frame_period_s)
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
