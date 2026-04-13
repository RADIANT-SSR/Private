"""OpticsStage — chain wrapper for full optics pipeline.

Handles all five transmission input modes, nearfield emission, stray
light, wavefront error, EffectivePSF construction, EE_box computation,
and **regime finalization** (Rule 10).

Produces
--------
Frame ``"post_optics"`` with spectral radiance:
    ``L_post_optics(λ) = L_at_aperture(λ) × τ_opt(λ)``

Stage outputs under ``stage_outputs["optics"]``:
    - ``A_collect``: collecting area [m²]
    - ``Omega_pixel``: single-pixel solid angle [sr]
    - ``tau_opt``: system throughput values (np.ndarray)
    - ``tau_opt_spectral``: system throughput (SpectralData, full provenance)
    - ``EE_box``: ensquared energy in 1×1 pixel (1.0 for extended regime)
    - ``regime``: finalized :class:`RadiometricRegime` enum value
    - ``effective_psf``: :class:`EffectivePSF` (diffraction-only for now)
    - ``nearfield_irradiance_at_fpa``: SpectralData [W/m²/µm]
    - ``stray_light_irradiance_at_fpa``: SpectralData [W/m²/µm]
    - ``stray_includes_thermal``: bool
    - ``elements``: tuple[OpticalElement, ...]
    - ``transmission_input_mode``: str

Regime finalization (Rule 10):
    Reads ``regime_tentative`` and ``angular_extent_rad`` from source
    stage outputs. Refines using PSF FWHM:
    - angular_extent >= 2 × psf_fwhm_rad → EXTENDED
    - angular_extent <= 0.5 × psf_fwhm_rad → POINT_SOURCE
    - else → SUB_PIXEL
    If no EffectivePSF is available, trusts the tentative classification.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.core.spectral import SpectralData
from radiant.optics.aperture import CircularAperture
from radiant.optics.diffraction import compute_psf
from radiant.optics.element_list import compute_nearfield_irradiance
from radiant.optics.psf import EffectivePSF, build_effective_psf
from radiant.optics.sampling import compute_sampling
from radiant.optics.stray_light import (
    StrayLightConfig,
    StrayLightInputMode,
    compute_stray_light_irradiance,
)
from radiant.optics.transmission_modes import (
    TransmissionInputMode,
    resolve_transmission,
)
from radiant.optics.wavefront import WavefrontError, WfeMode

logger = logging.getLogger(__name__)


def _build_effective_psf(
    state: ChainState,
    params: ParameterSet,
    aperture_m: float,
    focal_length_m: float,
    wfe_rms_waves: float = 0.0,
) -> tuple[ChainState, EffectivePSF | None]:
    """Build EffectivePSF from diffraction PSF and store in stage outputs.

    Uses band-center wavelength for the diffraction calculation.
    Gracefully skips if pixel pitch is unavailable.

    Returns (updated_state, epsf_or_None).
    """
    try:
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
    except (KeyError, TypeError):
        logger.debug("Pixel pitch not available; skipping EffectivePSF.")
        return state, None

    wavelength_m = float(state.wavelength_um[len(state.wavelength_um) // 2]) * 1e-6

    config = compute_sampling(
        wavelength_m=wavelength_m,
        focal_length_m=focal_length_m,
        aperture_diameter_m=aperture_m,
        pixel_pitch_m=pixel_pitch_m,
        pupil_npix=128,
        psf_oversample=8,
    )
    psf_arr = compute_psf(
        config,
        obscuration_ratio=params.get("optics.obscuration_ratio"),
        wfe_rms_waves=wfe_rms_waves,
    )

    epsf = build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=pixel_pitch_m,
        wavelength_um=wavelength_m * 1e6,
    )

    state = state.with_stage_output("optics", "effective_psf", epsf)
    return state, epsf


def _finalize_regime(
    tentative: RadiometricRegime,
    angular_extent_rad: float,
    epsf: EffectivePSF | None,
    focal_length_m: float,
    regime_override: str = "auto",
) -> RadiometricRegime:
    """Finalize regime using PSF FWHM (Rule 10).

    If ``regime_override`` is not ``"auto"``, the user has forced the
    regime — honor it without reclassification.

    If no EffectivePSF is available, trusts the tentative classification.
    """
    if regime_override != "auto":
        return RadiometricRegime(regime_override)

    if epsf is None:
        return tentative

    fwhm_m = epsf.fwhm(axis="x")
    psf_fwhm_rad = fwhm_m / focal_length_m

    if not math.isfinite(angular_extent_rad) and angular_extent_rad > 0:
        return RadiometricRegime.EXTENDED

    if angular_extent_rad >= 2.0 * psf_fwhm_rad:
        return RadiometricRegime.EXTENDED
    if angular_extent_rad <= 0.5 * psf_fwhm_rad:
        return RadiometricRegime.POINT_SOURCE
    return RadiometricRegime.SUB_PIXEL


def _compute_ee_box(
    regime: RadiometricRegime,
    epsf: EffectivePSF | None,
) -> float:
    """Compute EE_box for the finalized regime.

    Extended regime → 1.0 (EE_box not applied, Rule 9).
    Point/sub-pixel → ensquared energy in 1×1 pixel from EffectivePSF.
    If no EffectivePSF available, defaults to 1.0.
    """
    if regime == RadiometricRegime.EXTENDED:
        return 1.0
    if epsf is None:
        return 1.0
    return epsf.ensquared_energy_nxn(1)


class OpticsStage:
    """Chain stage for full optical throughput, nearfield, stray light, and regime finalization."""

    @property
    def name(self) -> str:
        return "optics"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # --- Aperture geometry (unchanged) ---
        aperture = CircularAperture(
            aperture_diameter_m=params.get("optics.aperture_diameter_m"),
            obscuration_ratio=params.get("optics.obscuration_ratio"),
        )
        focal_length_m: float = params.get("optics.focal_length_m")

        # --- Pixel solid angle ---
        pixel_pitch_x_m: float = params.get("detector.pixel_pitch_x_um")
        pixel_pitch_y_m: float = params.get("detector.pixel_pitch_y_um")
        omega_pixel = (pixel_pitch_x_m * pixel_pitch_y_m) / (focal_length_m**2)

        # --- Transmission mode dispatch ---
        mode_str: str = params.get("optics.transmission_input_mode")
        mode = TransmissionInputMode(mode_str)

        optics_temp_K: float = params.get("optics.optics_temperature_K")
        optics_dist_m: float = params.get("optics.optics_distance_to_fpa_m")
        if optics_dist_m <= 0:
            optics_dist_m = focal_length_m

        tx_result = resolve_transmission(
            mode,
            state.wavelength_um,
            transmission_scalar=params.get("optics.transmission_scalar"),
            optics_temperature_K=optics_temp_K,
            optics_distance_to_fpa_m=optics_dist_m,
            aperture_diameter_m=aperture.aperture_diameter_m,
        )

        # --- Apply transmission to produce post_optics frame ---
        at_aperture = state.frames["at_aperture"]
        L_at_aperture = at_aperture.spectral_radiance
        if L_at_aperture is None:
            raise ValueError("OpticsStage: 'at_aperture' frame has no spectral_radiance.")

        tau_vals = tx_result.transmission.values
        L_post_optics = L_at_aperture * tau_vals

        frame = RadiometricFrame(
            name="post_optics",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_post_optics,
            notes=f"x tau_opt ({mode_str})",
        )

        state = state.with_frame(frame)
        state = state.with_stage_output("optics", "A_collect", aperture.clear_area_m2)
        state = state.with_stage_output("optics", "Omega_pixel", omega_pixel)
        state = state.with_stage_output("optics", "tau_opt", tx_result.transmission.values)
        state = state.with_stage_output("optics", "tau_opt_spectral", tx_result.transmission)
        state = state.with_stage_output(
            "optics",
            "transmission_input_mode",
            mode_str,
        )
        state = state.with_stage_output("optics", "elements", tx_result.elements)

        # --- Wavefront error ---
        wfe_mode_str: str = params.get("optics.wfe_mode")
        wfe_rms: float = params.get("optics.wfe_rms_waves")
        wfe_ref: float = params.get("optics.wfe_reference_wavelength_um")
        wfe = WavefrontError(
            mode=WfeMode(wfe_mode_str),
            rms_waves=wfe_rms if wfe_mode_str == "scalar_rms" else None,
            reference_wavelength_um=wfe_ref,
        )
        state = state.with_stage_output("optics", "wavefront_error", wfe)

        # --- Build EffectivePSF ---
        state, epsf = _build_effective_psf(
            state,
            params,
            aperture_m=aperture.aperture_diameter_m,
            focal_length_m=focal_length_m,
            wfe_rms_waves=wfe_rms,
        )

        # --- Nearfield emission ---
        nearfield_enabled: int = params.get("optics.nearfield_enabled")
        stray_includes_thermal: int = params.get("optics.stray.includes_thermal")

        if nearfield_enabled and not stray_includes_thermal:
            cold_stop_eff: float = params.get("optics.cold_stop_efficiency")
            nf_irradiance = compute_nearfield_irradiance(
                tx_result.elements,
                state.wavelength_um,
                cold_stop_eff,
            )
        else:
            nf_irradiance = SpectralData(
                name="optics.nearfield_irradiance_at_fpa",
                wavelength_um=state.wavelength_um.copy(),
                values=np.zeros_like(state.wavelength_um),
                unit="W/m^2/um",
                source="Nearfield disabled"
                if not nearfield_enabled
                else "Nearfield suppressed (stray includes thermal)",
            )

        state = state.with_stage_output(
            "optics",
            "nearfield_irradiance_at_fpa",
            nf_irradiance,
        )

        # --- Stray light ---
        stray_mode_str: str = params.get("optics.stray.input_mode")
        stray_config = StrayLightConfig(
            input_mode=StrayLightInputMode(stray_mode_str),
            veiling_glare_fraction=params.get("optics.stray.veiling_glare_fraction"),
            absolute_irradiance_W_m2=params.get("optics.stray.absolute_irradiance_W_m2"),
            includes_thermal=bool(stray_includes_thermal),
        )

        # For veiling_glare, compute in-FOV irradiance from post-optics frame.
        in_fov_irr = None
        if stray_config.input_mode == StrayLightInputMode.VEILING_GLARE:
            # In-FOV irradiance at FPA = L_post_optics * Omega_pixel
            in_fov_irr = SpectralData(
                name="in_fov_irradiance",
                wavelength_um=state.wavelength_um.copy(),
                values=L_post_optics * omega_pixel,
                unit="W/m^2/um",
                source="L_post_optics * Omega_pixel",
            )

        stray_irradiance = compute_stray_light_irradiance(
            stray_config,
            state.wavelength_um,
            in_fov_irradiance=in_fov_irr,
        )
        state = state.with_stage_output(
            "optics",
            "stray_light_irradiance_at_fpa",
            stray_irradiance,
        )
        state = state.with_stage_output(
            "optics",
            "stray_includes_thermal",
            bool(stray_includes_thermal),
        )

        # --- Regime finalization (Rule 10) ---
        source_out = state.stage_outputs.get("source", {})
        tentative = source_out.get(
            "regime_tentative",
            RadiometricRegime.EXTENDED,
        )
        angular_extent_rad: float = source_out.get("angular_extent_rad", float("inf"))

        if isinstance(tentative, str):
            tentative = RadiometricRegime(tentative)

        regime_override: str = source_out.get("regime_override", "auto")

        regime = _finalize_regime(
            tentative=tentative,
            angular_extent_rad=angular_extent_rad,
            epsf=epsf,
            focal_length_m=focal_length_m,
            regime_override=regime_override,
        )

        ee_box = _compute_ee_box(regime, epsf)

        return state.with_stage_output("optics", "EE_box", ee_box).with_stage_output(
            "optics", "regime", regime
        )
