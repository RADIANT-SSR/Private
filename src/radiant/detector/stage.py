"""DetectorStage — assembles per-pixel electron counts and raw noise budget.

Reads signal, background, nearfield, and stray electron counts from
the spectral integration stage. Computes dark current, glow, and
builds the raw (pre-TDI, pre-binning) noise budget using all 16
noise sources.

**No NoiseTerm emission.** All noise terms are stored in
``stage_outputs["detector"]`` and the ReadoutStage is the sole emitter
of ``NoiseTerm`` objects (after applying TDI/binning/coadd scaling).
"""

from __future__ import annotations

import math

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.detector.dark_current import DarkCurrent
from radiant.detector.diffusion import diffusion_mtf_1d
from radiant.detector.ipc import ipc_kernel, ipc_kernel_pitch_spaced, ipc_mtf_1d
from radiant.detector.noise.budget import compute_noise_budget


class DetectorStage:
    """Chain stage for detector electron counts and raw noise budget."""

    @property
    def name(self) -> str:
        return "detector"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # --- Read upstream electron counts ---
        si_out = state.stage_outputs.get("spectral_integration", {})
        signal_e: float = si_out.get("signal_e", 0.0)
        background_e: float = si_out.get("background_e", 0.0)
        nearfield_e: float = si_out.get("nearfield_e", 0.0)
        stray_e: float = si_out.get("stray_e", 0.0)

        # Also read from photoelectrons frame as fallback for signal
        pe_frame = state.frames.get("photoelectrons")
        if pe_frame is not None and pe_frame.in_band_value is not None:
            signal_e = float(pe_frame.in_band_value)

        t_int: float = params.get("spectral_integration.integration_time_s")

        # --- Dark current ---
        dark = DarkCurrent(
            rate_e_per_s=params.get("detector.dark_rate_e_per_s"),
            reference_temperature_K=params.get("detector.dark_reference_temperature_K"),
            activation_energy_eV=params.get("detector.dark_activation_energy_eV"),
        )
        detector_temp_K: float = params.get("detector.detector_temperature_K")
        # CU-081 (warning-free-UX campaign): a temperature-inert dark rate is a
        # property of the configuration (dark_activation_energy_eV = 0), not a
        # per-evaluate event — carry it as a structured status note on the detector
        # stage output instead of a UserWarning that fires on every evaluate.
        dark_temperature_note = ""
        if dark.activation_energy_eV > 0.0:
            dark = dark.at_temperature(detector_temp_K)
        elif abs(detector_temp_K - dark.reference_temperature_K) > 1.0:
            dark_temperature_note = (
                f"detector_temperature_K = {detector_temp_K:.1f} K differs from "
                f"dark_reference_temperature_K = {dark.reference_temperature_K:.1f} K, "
                "but dark_activation_energy_eV = 0, so dark current does NOT scale with "
                "temperature — the temperature setting has no effect on dark noise. Set "
                "dark_activation_energy_eV (e.g. ~0.5 eV for MWIR HgCdTe) for Arrhenius "
                "scaling, or reference the dark rate to the operating temperature (CU-081)."
            )
        dark_e = dark.electrons_accumulated(t_int)

        # --- Glow ---
        glow_rate: float = params.get("detector.glow_e_per_s")
        glow_e = glow_rate * t_int

        # --- Pixel area for Johnson noise ---
        pixel_pitch_x: float = params.get("detector.pixel_pitch_x_um")
        pixel_pitch_y: float = params.get("detector.pixel_pitch_y_um")
        pixel_area_m2 = pixel_pitch_x * pixel_pitch_y

        # --- Build raw noise budget (pre-TDI, pre-binning) ---
        budget = compute_noise_budget(
            signal_e=signal_e,
            background_e=background_e,
            nearfield_e=nearfield_e,
            stray_e=stray_e,
            dark_e=dark_e,
            glow_e=glow_e,
            gr_factor=params.get("detector.gr_factor"),
            r0a_ohm_cm2=params.get("detector.r0a_ohm_cm2"),
            pixel_area_m2=pixel_area_m2,
            detector_temp_K=detector_temp_K,
            t_int_s=t_int,
            flicker_K=params.get("detector.flicker_K"),
            flicker_f_low_hz=params.get("detector.flicker_f_low_hz"),
            flicker_f_high_hz=params.get("detector.flicker_f_high_hz"),
            read_noise_e_rms=params.get("readout.read_noise_e_rms"),
            node_capacitance_F=params.get("readout.node_capacitance_F"),
            cds_enabled=bool(params.get("readout.cds_enabled")),
            gain_e_per_dn=params.get("readout.gain_e_per_dn"),
            prnu_pct=params.get("detector.prnu_pct"),
            dsnu_e_rms=params.get("detector.dsnu_e_rms"),
            clutter_sigma=params.get("detector.clutter_sigma"),
            prior_signal_e=params.get("detector.prior_signal_e"),
            persistence_fraction=params.get("detector.persistence_fraction"),
            persistence_tau_s=params.get("detector.persistence_tau_s"),
            frame_interval_s=t_int,  # approximate: use t_int as frame period
        )

        # --- IPC kernel (for downstream spatial metric convolution) ---
        ipc_coupling: float = params.get("detector.ipc_coupling")
        if ipc_coupling > 0.0:
            # Raw 3×3 kernel (logical, pixel-grid — provenance/inspection).
            state = state.with_stage_output("detector", "ipc_kernel", ipc_kernel(ipc_coupling))
            # PSF-path kernel: resample the couplings to one pixel pitch on the
            # PSF sample grid (CU-083). The raw 3×3 would place them one sample
            # (sub-µm) away, making the PSF-path IPC blur negligible. The PSF's
            # sample spacing comes from the optics EffectivePSF via stage
            # outputs (Rule 6/11: read-only, no cross-stage import).
            optics_epsf = state.stage_outputs.get("optics", {}).get("effective_psf")
            if optics_epsf is not None:
                state = state.with_stage_output(
                    "detector",
                    "ipc_kernel_psf",
                    ipc_kernel_pitch_spaced(
                        ipc_coupling,
                        optics_epsf.sample_spacing_m,
                        pixel_pitch_x,
                        pixel_pitch_y,
                    ),
                )

        # --- MTF product path: pixel aperture, IPC, charge diffusion ---
        freq_mrad = state.spatial_freq_cycles_per_mrad
        if freq_mrad is not None:
            focal_length_m: float = params.get("optics.focal_length_m")
            freq_m = freq_mrad / (focal_length_m * 1e-3)

            # Pixel aperture MTF = |sinc(f · pitch · √FF)| — the photosite
            # linear width is pitch·√FF for areal fill factor FF (CU-074).
            # This matches the PSF-path pixel_aperture kernel width exactly,
            # so the two Rule-4 paths agree at fill_factor < 1.
            fill_factor: float = params.get("detector.fill_factor")
            sqrt_ff = math.sqrt(fill_factor)
            mtf_pixel_x = np.abs(np.sinc(freq_m * pixel_pitch_x * sqrt_ff))
            mtf_pixel_y = np.abs(np.sinc(freq_m * pixel_pitch_y * sqrt_ff))
            state = state.with_mtf("mtf_pixel_aperture_x", mtf_pixel_x)
            state = state.with_mtf("mtf_pixel_aperture_y", mtf_pixel_y)

            # IPC MTF (both axes).
            if ipc_coupling > 0.0:
                mtf_ipc_x = ipc_mtf_1d(freq_m, ipc_coupling, pixel_pitch_x, axis="x")
                # CU-085: the y-axis MTF must use the y pitch (was pixel_pitch_x —
                # wrong for rectangular pixels; harmless when pitch_x == pitch_y).
                mtf_ipc_y = ipc_mtf_1d(freq_m, ipc_coupling, pixel_pitch_y, axis="y")
            else:
                mtf_ipc_x = np.ones_like(freq_m)
                mtf_ipc_y = np.ones_like(freq_m)
            state = state.with_mtf("mtf_ipc_x", mtf_ipc_x)
            state = state.with_mtf("mtf_ipc_y", mtf_ipc_y)

            # Charge diffusion MTF (isotropic: same for x and y).
            diffusion_length_m: float = params.get("detector.charge_diffusion_length_m")
            if diffusion_length_m > 0.0:
                mtf_diff = diffusion_mtf_1d(freq_m, diffusion_length_m)
            else:
                mtf_diff = np.ones_like(freq_m)
            state = state.with_mtf("mtf_charge_diffusion_x", mtf_diff)
            state = state.with_mtf("mtf_charge_diffusion_y", mtf_diff)

        # --- Store all outputs for ReadoutStage ---
        state = state.with_stage_output("detector", "signal_e", signal_e)
        state = state.with_stage_output("detector", "background_e", background_e)
        state = state.with_stage_output("detector", "nearfield_e", nearfield_e)
        state = state.with_stage_output("detector", "stray_e", stray_e)
        state = state.with_stage_output("detector", "dark_e", dark_e)
        state = state.with_stage_output("detector", "glow_e", glow_e)
        if dark_temperature_note:
            state = state.with_stage_output(
                "detector", "dark_temperature_note", dark_temperature_note
            )
        return state.with_stage_output("detector", "noise_budget_raw", budget)
