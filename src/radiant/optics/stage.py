"""OpticsStage — chain wrapper for full optics pipeline.

Handles all five transmission input modes, nearfield emission, stray
light, wavefront error, EffectivePSF construction, and **regime
finalization** (Rule 10). EE_box is computed downstream in
PlatformStage from the jitter/smear-degraded PSF.

Produces
--------
Frame ``"post_optics"`` with spectral radiance:
    ``L_post_optics(λ) = L_at_aperture(λ) × τ_opt(λ)``

Stage outputs under ``stage_outputs["optics"]``:
    - ``A_collect``: collecting area [m²]
    - ``Omega_pixel``: single-pixel solid angle [sr]
    - ``tau_opt``: system throughput values (np.ndarray)
    - ``tau_opt_spectral``: system throughput (SpectralData, full provenance)
    - ``regime``: finalized :class:`RadiometricRegime` enum value
    - ``effective_psf``: :class:`EffectivePSF` (diffraction + WFE +
      defocus-as-Z4 in the pupil, pixel aperture, charge diffusion)
    - ``reference_psf``: :class:`EffectivePSF` diffraction-limited
      reference (no WFE/defocus) with the same detector kernels, used
      for the PSF-derived Strehl ratio
    - ``pupil_amplitude``: complex-pupil amplitude/apodization map
      (np.ndarray, dimensionless transmission; Gap 89) — diagnostic view,
      never read back into the MTF/PSF computation
    - ``pupil_phase_waves``: complex-pupil wavefront-error map (np.ndarray,
      waves at ``pupil_wavelength_um``, phase_rad/2π, 0 outside the clear
      aperture; Gap 89) — diagnostic view only
    - ``pupil_wavelength_um``: wavelength at which ``pupil_phase_waves`` is
      expressed [µm] (band centre for polychromatic runs)
    - ``pupil_plane_extent_m``: physical pupil diameter [m] for axis scaling
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
import warnings

import numpy as np

from radiant.core.chain import ChainState
from radiant.core.constants import c as c_light
from radiant.core.constants import h as h_planck
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.core.spectral import SpectralData
from radiant.optics.aperture import CircularAperture
from radiant.optics.diffusion_kernel import make_diffusion_kernel_2d
from radiant.optics.element import ElementTransferMode
from radiant.optics.errors import OpticsValidationError
from radiant.optics.nearfield_irradiance import compute_nearfield_irradiance
from radiant.optics.pixel_kernel import make_pixel_aperture_kernel_2d
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf_mono import compute_psf
from radiant.optics.psf_poly import (
    compute_polychromatic_psf,
)
from radiant.optics.pupil_amplitude import SpiderVaneSpec, make_pupil_amplitude
from radiant.optics.pupil_mtf import (
    polychromatic_pupil_mtf,
    pupil_autocorrelation_mtf_1d,
    pupil_autocorrelation_mtf_2d,
    resolve_wfe_for_wavelength,
)
from radiant.optics.pupil_phase import make_pupil_phase_for_wfe
from radiant.optics.sampling import compute_sampling
from radiant.optics.scatter import (
    scatter_kernel_2d,
    scatter_mtf_1d,
    total_integrated_scatter,
)
from radiant.optics.stray_light import (
    StrayLightConfig,
    StrayLightInputMode,
    compute_stray_light_irradiance,
)
from radiant.optics.transmission_modes import (
    TransmissionInputMode,
    resolve_transmission,
)
from radiant.optics.wavefront import FieldWfeSample, WavefrontError, WfeMode

logger = logging.getLogger(__name__)


def _add_defocus_to_wfe(
    wfe: WavefrontError | None,
    defocus_um: float,
    f_number: float,
    wavelength_m: float,
) -> WavefrontError | None:
    """Fold a separate defocus offset into WFE as an equivalent Zernike Z4.

    The Noll Z4 (defocus) coefficient in waves is::

        Z4 = δ / (8 √3 λ f/#²)

    where δ is the axial defocus [m] and λ is the wavelength [m].
    (The Z4 OPD in metres, ``z4_waves × λ_ref``, is wavelength-independent,
    so any reference wavelength gives the same physical pupil after the
    ref→operating rescale in ``make_pupil_phase_zernike``.)

    If the existing WFE already has a Z4 Zernike coefficient, the defocus
    contribution is added to it.  For scalar-RMS WFE, the RMS screen is
    **preserved** and Z4 rides alongside it in ``zernike_coeffs`` — screen
    plus Zernike in one pupil phase (CU-058; the old behavior discarded the
    screen, which broke Rule 4 whenever scalar WFE and defocus were combined).
    """
    if defocus_um == 0.0:
        return wfe

    defocus_m = defocus_um * 1e-6
    z4_waves = defocus_m / (8.0 * math.sqrt(3.0) * wavelength_m * f_number**2)

    if wfe is None:
        return WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: z4_waves},
            reference_wavelength_um=wavelength_m * 1e6,
        )
    if wfe.mode == WfeMode.SCALAR_RMS:
        # Preserve the random screen; carry defocus as a deterministic Z4
        # term next to it. Rescale Z4 to the WFE's reference wavelength so
        # the OPD is unchanged (waves_ref × λ_ref = waves_here × λ_here).
        ref_m = wfe.reference_wavelength_um * 1e-6
        existing = dict(wfe.zernike_coeffs) if wfe.zernike_coeffs else {}
        existing[4] = existing.get(4, 0.0) + z4_waves * (wavelength_m / ref_m)
        return WavefrontError(
            mode=WfeMode.SCALAR_RMS,
            rms_waves=wfe.rms_waves,
            zernike_coeffs=existing,
            reference_wavelength_um=wfe.reference_wavelength_um,
        )
    if wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        new_coeffs = dict(wfe.zernike_coeffs)
        ref_m = wfe.reference_wavelength_um * 1e-6
        new_coeffs[4] = new_coeffs.get(4, 0.0) + z4_waves * (wavelength_m / ref_m)
        return WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs=new_coeffs,
            reference_wavelength_um=wfe.reference_wavelength_um,
        )
    # Other modes: cannot fold defocus — return as-is.
    return wfe


def _read_vane_spec(params: ParameterSet, aperture_m: float) -> SpiderVaneSpec | None:
    """Build a SpiderVaneSpec from optics params, or None when inactive.

    Converts the physical strut width [m] to a fraction of the pupil
    diameter (Rule 2: unit conversion at the stage boundary). Returns None
    when no struts are configured, so the pupil is byte-identical to the
    historical (vane-free) mask.
    """
    n_struts: int = params.get("optics.n_spiders")
    width_m: float = params.get("optics.spider_width_m")
    if n_struts <= 0 or width_m <= 0.0:
        return None
    return SpiderVaneSpec(
        n_struts=n_struts,
        width_frac=width_m / aperture_m,
        angle_offset_deg=params.get("optics.spider_angle_deg"),
    )


def _read_pupil_mask_override(state: ChainState) -> np.ndarray | None:
    """Measured/arbitrary pupil amplitude mask injected via optics_config.

    Returns ``state.stage_outputs["optics_config"]["pupil_mask_override"]``
    (a 2-D amplitude array) or None. Supersedes the parametric pupil
    geometry when present (Gap 54); None (default) preserves all results.
    """
    override = state.stage_outputs.get("optics_config", {}).get("pupil_mask_override")
    if override is None:
        return None
    return np.asarray(override, dtype=np.float64)


def _compute_optical_mtf_terms(
    state: ChainState,
    n_psf_wavelengths: int,
    wavelength_m: float | None,
    psf_wl_m: np.ndarray | None,
    weights: np.ndarray | None,
    focal_length_m: float,
    aperture_m: float,
    pixel_pitch_m: float,
    obscuration: float,
    wfe: WavefrontError | None,
    sample_spacing_m: float,
    chromatic_zernikes: dict[float, dict[int, float]] | None,
    vanes: SpiderVaneSpec | None = None,
    mask_override: np.ndarray | None = None,
) -> ChainState:
    """Compute optical MTF via pupil autocorrelation and store in ChainState.

    For monochromatic: builds pupil, computes 2-D autocorrelation MTF,
    extracts 1-D x and y slices.
    For polychromatic: calls ``polychromatic_pupil_mtf()`` for weighted
    average of monochromatic pupil autocorrelation MTFs.

    Defocus arrives already folded into ``wfe`` as Zernike Z4 by
    ``_build_effective_psf`` (CU-058) — the SAME WavefrontError object the
    PSF path consumes, so ``mtf_optics`` captures diffraction + WFE +
    defocus from the identical pupil.

    Stores ``mtf_optics_x``, ``mtf_optics_y`` in ``state.mtf_terms``
    and sets ``state.spatial_freq_cycles_per_mrad``.
    """
    pupil_npix = 128

    # Diagnostic pupil maps (Gap 89) — captured for persistence, NOT fed back
    # into the MTF/PSF computation. Set in whichever branch runs below; the
    # amplitude is wavelength-independent, the phase is expressed at
    # ``pupil_ref_wl_m`` (band centre for the polychromatic case).
    pupil_amp_map: np.ndarray | None = None
    pupil_phase_rad: np.ndarray | None = None
    pupil_ref_wl_m: float | None = None

    if n_psf_wavelengths <= 1:
        # Monochromatic: recompute pupil and autocorrelation MTF.
        assert wavelength_m is not None

        config = compute_sampling(
            wavelength_m=wavelength_m,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=pupil_npix,
            psf_oversample=8,
        )

        amplitude = make_pupil_amplitude(pupil_npix, obscuration, vanes, mask_override)
        try:
            # Shared dispatch with compute_psf (Rule 4 / CU-058).
            phase = make_pupil_phase_for_wfe(
                pupil_npix,
                wfe,
                operating_wavelength_m=wavelength_m,
                obscuration_ratio=obscuration,
            )
        except NotImplementedError:
            # Unsupported WFE mode for pupil autocorrelation — skip MTF.
            logger.warning(
                "WFE mode %r not supported for pupil autocorrelation MTF; skipping.",
                wfe.mode.value if wfe is not None else None,
            )
            return state

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        freq_m, mtf_x = pupil_autocorrelation_mtf_1d(mtf_2d, sample_spacing_m, "x")
        _, mtf_y = pupil_autocorrelation_mtf_1d(mtf_2d, sample_spacing_m, "y")

        # The pupil built above IS the one the MTF used — persist it verbatim.
        pupil_amp_map = amplitude
        pupil_phase_rad = phase
        pupil_ref_wl_m = wavelength_m
    else:
        # Polychromatic: weighted average of monochromatic pupil MTFs.
        assert psf_wl_m is not None
        assert weights is not None

        freq_m, mtf_x, mtf_y = polychromatic_pupil_mtf(
            wavelengths_m=psf_wl_m,
            weights=weights,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            obscuration_ratio=obscuration,
            wfe=wfe,
            pupil_npix=pupil_npix,
            psf_oversample=8,
            chromatic_zernikes=chromatic_zernikes,
            vanes=vanes,
            mask_override=mask_override,
        )

        # Representative diagnostic pupil at the band-centre wavelength (Gap 89).
        # This mirrors one term of the weighted average above; it is a view for
        # display only and is never fed back into the MTF product.
        rep_wl_m = float(psf_wl_m[len(psf_wl_m) // 2])
        rep_wfe = resolve_wfe_for_wavelength(wfe, rep_wl_m * 1e6, chromatic_zernikes)
        pupil_amp_map = make_pupil_amplitude(pupil_npix, obscuration, vanes, mask_override)
        try:
            pupil_phase_rad = make_pupil_phase_for_wfe(
                pupil_npix,
                rep_wfe,
                operating_wavelength_m=rep_wl_m,
                obscuration_ratio=obscuration,
            )
            pupil_ref_wl_m = rep_wl_m
        except NotImplementedError:
            # Unsupported WFE mode has no pupil-phase representation — persist
            # only the amplitude (obscuration/vanes/override still diagnostic).
            pupil_phase_rad = None

    # Convert frequency from cycles/m to cycles/mrad.
    # f_angular [cycles/mrad] = f_focal [cycles/m] * focal_length_m * 1e-3
    # (1 mrad on the focal plane = focal_length_m * 1e-3 m)
    freq_cycles_per_mrad = freq_m * focal_length_m * 1e-3

    state = state.with_spatial_freq(freq_cycles_per_mrad)
    state = state.with_mtf("mtf_optics_x", mtf_x)
    state = state.with_mtf("mtf_optics_y", mtf_y)

    # --- Gap 89: persist the diagnostic complex-pupil views (additive) ---
    # Two faces of the same complex pupil the MTF autocorrelation consumed:
    #   • pupil_amplitude    — dimensionless transmission mask (obscuration,
    #                          spider vanes, measured override included).
    #   • pupil_phase_waves  — wavefront error in WAVES at pupil_wavelength_um
    #                          (phase_radians / 2π), masked to 0 outside the
    #                          clear aperture. Waves is the natural WFE unit.
    # Neither array is read back by any computation (Rule 4 unchanged).
    if pupil_amp_map is not None:
        state = state.with_stage_output("optics", "pupil_amplitude", pupil_amp_map)
        state = state.with_stage_output("optics", "pupil_plane_extent_m", aperture_m)
        if pupil_phase_rad is not None and pupil_ref_wl_m is not None:
            phase_waves = pupil_phase_rad / (2.0 * np.pi)
            phase_waves = np.where(pupil_amp_map > 0.0, phase_waves, 0.0)
            state = state.with_stage_output("optics", "pupil_phase_waves", phase_waves)
            state = state.with_stage_output(
                "optics", "pupil_wavelength_um", pupil_ref_wl_m * 1e6
            )
    return state


def _build_effective_psf(
    state: ChainState,
    params: ParameterSet,
    aperture_m: float,
    focal_length_m: float,
    wfe: WavefrontError | None = None,
    chromatic_zernikes: dict[float, dict[int, float]] | None = None,
) -> tuple[ChainState, EffectivePSF | None]:
    """Build EffectivePSF from diffraction PSF and store in stage outputs.

    When ``optics.psf_n_wavelengths == 1`` (default), computes a single
    monochromatic PSF at band center. When > 1, computes a polychromatic
    PSF as the photon-flux-weighted average of monochromatic PSFs.

    Parameters
    ----------
    wfe:
        Wavefront error specification. Dispatches on ``wfe.mode``:
        ``SCALAR_RMS`` uses random phase screen (existing behavior),
        ``ZERNIKE`` uses deterministic Zernike polynomial phase.
        ``None`` = diffraction-limited.
    chromatic_zernikes:
        For refractive systems: wavelength-dependent Zernike coefficients.
        Maps wavelength_um → {noll_j: coeff_waves}. Passed through to
        ``compute_polychromatic_psf``.

    Returns (updated_state, epsf_or_None).
    """
    pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
    obscuration: float = params.get("optics.obscuration_ratio")
    n_psf_wavelengths: int = params.get("optics.psf_n_wavelengths")
    vanes = _read_vane_spec(params, aperture_m)
    mask_override = _read_pupil_mask_override(state)

    # --- CU-058: fold defocus into the pupil WFE ONCE, before both paths ---
    # The PSF path and the MTF product path then derive defocus from the
    # SAME complex pupil (Z4 phase), so FFT{PSF} equals the pupil
    # autocorrelation exactly (Wiener–Khinchin) and Rule 4's consistency
    # invariant holds by construction. The former PSF-path Gaussian defocus
    # kernel is gone — it modeled defocus differently from the product path.
    defocus_um: float = params.get("optics.defocus_um")
    if defocus_um != 0.0:
        f_number: float = params.get("optics.f_number")
        band_center_m = float(state.wavelength_um[len(state.wavelength_um) // 2]) * 1e-6
        wfe = _add_defocus_to_wfe(wfe, defocus_um, f_number, band_center_m)

    # Set in the polychromatic branch; consumed by MTF computation.
    psf_wl_m: np.ndarray | None = None

    if n_psf_wavelengths <= 1:
        # --- Monochromatic path (backward compatible) ---
        wavelength_m = float(state.wavelength_um[len(state.wavelength_um) // 2]) * 1e-6

        config = compute_sampling(
            wavelength_m=wavelength_m,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=128,
            psf_oversample=8,
        )
        psf_arr = compute_psf(config, obscuration, wfe, vanes, mask_override)
        sample_spacing_m = config.focal_spacing_m
        wavelength_um = wavelength_m * 1e6
    else:
        # --- Polychromatic path ---
        wl_um = state.wavelength_um
        psf_wl_um = np.linspace(float(wl_um[0]), float(wl_um[-1]), n_psf_wavelengths)
        psf_wl_m = psf_wl_um * 1e-6

        # Compute photon-flux weights: L(lambda) * lambda/(hc).
        # Gap 17: an injected optics_config["psf_weighting_spectrum"]
        # (SpectralData, W/m²/sr/µm) overrides the scene spectrum so the
        # PSF weighting can be decoupled from the radiometric source
        # (e.g. blackbody- vs solar-weighted PSF comparisons).
        override_sd = state.stage_outputs.get("optics_config", {}).get("psf_weighting_spectrum")
        if override_sd is not None:
            if float(override_sd.wavelength_um[-1]) < float(psf_wl_um[0]) or float(
                override_sd.wavelength_um[0]
            ) > float(psf_wl_um[-1]):
                raise OpticsValidationError(
                    "OpticsStage: psf_weighting_spectrum grid "
                    f"[{float(override_sd.wavelength_um[0]):.3g}, "
                    f"{float(override_sd.wavelength_um[-1]):.3g}] µm does not "
                    f"overlap the PSF band [{float(psf_wl_um[0]):.3g}, "
                    f"{float(psf_wl_um[-1]):.3g}] µm. Provide an override "
                    "spectrum covering the sensor band."
                )
            L_interp = np.interp(psf_wl_um, override_sd.wavelength_um, override_sd.values)
            weighting_source = f"override:{override_sd.name}"
        else:
            post_optics_frame = state.frames.get("post_optics")
            if post_optics_frame is not None and post_optics_frame.spectral_radiance is not None:
                L_interp = np.interp(psf_wl_um, wl_um, post_optics_frame.spectral_radiance)
                weighting_source = "post_optics"
            else:
                at_aperture = state.frames["at_aperture"]
                if at_aperture.spectral_radiance is not None:
                    L_interp = np.interp(psf_wl_um, wl_um, at_aperture.spectral_radiance)
                    weighting_source = "at_aperture"
                else:
                    L_interp = np.ones(n_psf_wavelengths)
                    weighting_source = "flat"
        state = state.with_stage_output("optics", "psf_weighting_source", weighting_source)

        weights = L_interp * psf_wl_m / (h_planck * c_light)
        weights = np.maximum(weights, 1e-30)

        store_per_wl = n_psf_wavelengths > 1

        poly_result = compute_polychromatic_psf(
            wavelengths_m=psf_wl_m,
            weights=weights,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            obscuration_ratio=obscuration,
            wfe=wfe,
            pupil_npix=128,
            psf_oversample=8,
            store_per_wavelength=store_per_wl,
            chromatic_zernikes=chromatic_zernikes,
            vanes=vanes,
            mask_override=mask_override,
        )

        psf_arr = poly_result.combined_psf
        sample_spacing_m = poly_result.pixel_scale_m

        # Flux-weighted mean wavelength for EffectivePSF metadata.
        wavelength_um = float(np.average(psf_wl_um, weights=weights))

        logger.info(
            "Polychromatic PSF: %d wavelengths (%.2f-%.2f um), effective lambda = %.3f um",
            n_psf_wavelengths,
            psf_wl_um[0],
            psf_wl_um[-1],
            wavelength_um,
        )

        # Store per-wavelength PSFs if available (Gap 16).
        if poly_result.per_wavelength is not None:
            per_wl_epsfs: dict[float, EffectivePSF] = {}
            for wl_key, psf_mono in poly_result.per_wavelength.items():
                per_wl_epsfs[wl_key] = build_effective_psf(
                    psf_mono,
                    kernels=[],
                    sample_spacing_m=sample_spacing_m,
                    pixel_pitch_m=pixel_pitch_m,
                    wavelength_um=wl_key,
                )
            state = state.with_stage_output("optics", "per_wavelength_psfs", per_wl_epsfs)

    epsf = build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=sample_spacing_m,
        pixel_pitch_m=pixel_pitch_m,
        wavelength_um=wavelength_um,
    )

    # --- Diffraction-limited reference PSF (for PSF-derived Strehl) ---
    # Same aperture geometry (obscuration included) and sampling, but no
    # wavefront error. Receives the same detector kernels as the actual
    # PSF below so that detector effects cancel in the Strehl peak ratio;
    # aberration kernels (defocus, jitter, smear, turbulence) are applied
    # only to the actual PSF.
    wfe_is_null = wfe is None or (
        wfe.mode == WfeMode.SCALAR_RMS
        and (wfe.rms_waves or 0.0) == 0.0
        and not wfe.zernike_coeffs  # folded defocus Z4 counts as aberration
    )
    if wfe_is_null and chromatic_zernikes is None:
        ref_psf_arr = psf_arr
    elif n_psf_wavelengths <= 1:
        ref_psf_arr = compute_psf(config, obscuration, None, vanes, mask_override)
    else:
        ref_result = compute_polychromatic_psf(
            wavelengths_m=psf_wl_m,
            weights=weights,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            obscuration_ratio=obscuration,
            wfe=None,
            pupil_npix=128,
            psf_oversample=8,
            store_per_wavelength=False,
            chromatic_zernikes=None,
            vanes=vanes,
            mask_override=mask_override,
        )
        ref_psf_arr = ref_result.combined_psf

    ref_epsf = build_effective_psf(
        ref_psf_arr,
        kernels=[],
        sample_spacing_m=sample_spacing_m,
        pixel_pitch_m=pixel_pitch_m,
        wavelength_um=wavelength_um,
    )

    # --- §6 step 1: Pixel aperture rect kernel ---
    pixel_pitch_y_m: float = params.get("detector.pixel_pitch_y_um")
    fill_factor: float = params.get("detector.fill_factor")
    npix_kern = epsf.data.shape[0]
    # Ensure odd kernel size.
    if npix_kern % 2 == 0:
        npix_kern -= 1
    npix_kern = max(npix_kern, 3)

    k_pixel = make_pixel_aperture_kernel_2d(
        npix_kern, sample_spacing_m, pixel_pitch_m, pixel_pitch_y_m, fill_factor
    )
    epsf = epsf.with_kernel("pixel_aperture", k_pixel)
    ref_epsf = ref_epsf.with_kernel("pixel_aperture", k_pixel)

    # --- §6 step 2: Charge diffusion Gaussian kernel ---
    diffusion_length_m: float = params.get("detector.charge_diffusion_length_m")
    if diffusion_length_m > 0.0:
        sigma_diff = diffusion_length_m / math.sqrt(2.0)
        npix_diff = int(math.ceil(6.0 * sigma_diff / sample_spacing_m)) | 1
        npix_diff = min(npix_diff, epsf.data.shape[0])
        npix_diff = max(npix_diff, 3)
        k_diff = make_diffusion_kernel_2d(npix_diff, sample_spacing_m, diffusion_length_m)
        epsf = epsf.with_kernel("charge_diffusion", k_diff)
        ref_epsf = ref_epsf.with_kernel("charge_diffusion", k_diff)

    # --- MTF product path: optical MTF via pupil autocorrelation ---
    # `wfe` already carries any folded defocus Z4 (CU-058), so both paths
    # receive the identical WavefrontError object.
    state = _compute_optical_mtf_terms(
        state,
        n_psf_wavelengths=n_psf_wavelengths,
        wavelength_m=(
            float(state.wavelength_um[len(state.wavelength_um) // 2]) * 1e-6
            if n_psf_wavelengths <= 1
            else None
        ),
        psf_wl_m=psf_wl_m if n_psf_wavelengths > 1 else None,
        weights=weights if n_psf_wavelengths > 1 else None,
        focal_length_m=focal_length_m,
        aperture_m=aperture_m,
        pixel_pitch_m=pixel_pitch_m,
        obscuration=obscuration,
        wfe=wfe,
        sample_spacing_m=sample_spacing_m,
        chromatic_zernikes=chromatic_zernikes,
        vanes=_read_vane_spec(params, aperture_m),
        mask_override=_read_pupil_mask_override(state),
    )

    state = state.with_stage_output("optics", "effective_psf", epsf)
    state = state.with_stage_output("optics", "reference_psf", ref_epsf)
    return state, epsf


# PSF-FWHM-based regime finalization boundaries (Rule 10; Matrix §1.1).
# Distinct from the IFOV-based tentative thresholds in ``core.regime`` —
# the finalization compares the target's angular extent to the *achieved*
# PSF width, not the geometric pixel footprint (CU-044: named, not shared,
# because the bases differ).
_EXTENDED_PSF_FWHM_MULTIPLE: float = 2.0
_POINT_SOURCE_PSF_FWHM_MULTIPLE: float = 0.5


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

    if math.isnan(angular_extent_rad):
        logger.warning(
            "_finalize_regime: angular_extent_rad is NaN; falling back to tentative regime '%s'.",
            tentative.value,
        )
        return tentative

    if not math.isfinite(angular_extent_rad) and angular_extent_rad > 0:
        return RadiometricRegime.EXTENDED

    if angular_extent_rad >= _EXTENDED_PSF_FWHM_MULTIPLE * psf_fwhm_rad:
        return RadiometricRegime.EXTENDED
    if angular_extent_rad <= _POINT_SOURCE_PSF_FWHM_MULTIPLE * psf_fwhm_rad:
        return RadiometricRegime.POINT_SOURCE
    return RadiometricRegime.SUB_PIXEL


# Matrix §7 thresholds for PSF-dependent angular-size checks.
# Point-source: fail above 0.1 × PSF_FWHM (angular extent no longer << PSF).
_POINT_SOURCE_ANGULAR_SIZE_LIMIT: float = 0.1
# Sub-pixel: warn below 0.01 × PSF_FWHM (descriptor has degraded into the
# point-source corner of the §1.1 decision region).
_SUBPIXEL_RECLASSIFICATION_THRESHOLD: float = 0.01


def _warn_declared_regime_mismatch(
    declared_scene_type: str,
    regime: RadiometricRegime,
) -> None:
    """Cross-check the user's DECLARED scene type against the derived regime (T2).

    ``source.scene_type`` is the user's declared intent; ``'auto'`` means "no
    declaration — infer", so only an explicit declaration is checked. When the
    declared type disagrees with the finalized (derived) :class:`RadiometricRegime`
    the mismatch is surfaced as a :class:`UserWarning`, never silent (Rule 17) — e.g.
    the user declared ``'extended'`` but the target angular size against the PSF/IFOV
    derived ``'point_source'``.

    This is a **soft notice**: the chain uses the *derived* regime regardless;
    ``source.regime_override`` is the hard force (see RADIANT_Source_Target_System
    §8.10). Distinct from :func:`_validate_psf_regime_consistency`, which guards the
    point/sub-pixel PSF-breakdown *physics* (raise/warn), not the declaration.
    The declared scene-type strings map 1:1 onto the regime enum values
    (``extended`` / ``sub_pixel`` / ``point_source``).
    """
    if declared_scene_type == "auto":
        return
    if RadiometricRegime(declared_scene_type) == regime:
        return
    warnings.warn(
        f"Declared source.scene_type={declared_scene_type!r} does not match the "
        f"derived radiometric regime {regime.value!r} (finalized from the target "
        f"angular size against the PSF/IFOV). The chain used the derived regime; "
        f"to force a regime instead, set source.regime_override.",
        UserWarning,
        stacklevel=2,
    )


def _validate_psf_regime_consistency(
    scene_type: str,
    angular_extent_rad: float,
    epsf: EffectivePSF | None,
    focal_length_m: float,
) -> None:
    """Matrix §7 PSF-dependent angular-size checks.

    Runs after :func:`_finalize_regime` resolves the radiometric regime;
    it does not modify the regime, only guards against the two physics
    inconsistencies the matrix flags:

    * **Point-source descriptor with a resolved target** — if
      ``√A_t / d > 0.1 · PSF_FWHM`` the point-source approximation is
      breaking down (the target is no longer ≪ the PSF).  Raise
      :class:`ParameterBoundsError` per matrix §7 line 485 (this is a
      physics error, not a warning).
    * **Sub-pixel descriptor with √A_t / d ≪ PSF_FWHM** — below
      ``0.01 · PSF_FWHM`` the sub-pixel descriptor is effectively a
      point source and carries unused area/shape fields.  Emit a
      :class:`UserWarning` suggesting reclassification per matrix §1.1.

    Both checks are skipped when there is no EffectivePSF (degenerate
    chain) or the scene_type is not one of ``{point_source, sub_pixel}``.
    ``angular_extent_rad`` of 0 or non-finite is also skipped because the
    descriptor carries no resolved geometry — the guard is only
    meaningful when √A_t / d is a positive finite number.
    """
    if epsf is None:
        return
    if scene_type not in ("point_source", "sub_pixel"):
        return
    if not math.isfinite(angular_extent_rad) or angular_extent_rad <= 0.0:
        return
    if focal_length_m <= 0.0:
        return

    fwhm_m = epsf.fwhm(axis="x")
    psf_fwhm_rad = fwhm_m / focal_length_m
    if psf_fwhm_rad <= 0.0:
        return

    ratio = angular_extent_rad / psf_fwhm_rad

    if scene_type == "point_source" and ratio > _POINT_SOURCE_ANGULAR_SIZE_LIMIT:
        raise ParameterBoundsError(
            what=(
                f"OpticsStage: point_source target has resolved angular extent "
                f"√A_t/d = {angular_extent_rad:.3e} rad, which is "
                f"{ratio:.3f}× PSF_FWHM ({psf_fwhm_rad:.3e} rad); the "
                f"point-source approximation requires √A_t/d ≤ "
                f"{_POINT_SOURCE_ANGULAR_SIZE_LIMIT:g}·PSF_FWHM "
                f"(matrix §7)."
            ),
            why=(
                "Point-source spectral intensity I(λ) = ∫L(λ)dA collapses a "
                "finite-area target into a zero-dimensional emitter by "
                "pre-integrating over the target area.  When the target's "
                "angular extent exceeds ~10% of the system PSF_FWHM the "
                "target is resolved and the point-source form silently "
                "drops spatial structure (Rule 17 forbids that)."
            ),
            action=(
                "Either (a) switch scene_type to 'sub_pixel' and supply A_t "
                "+ shape explicitly, or (b) move the target farther from "
                "the sensor (larger d) so √A_t/d falls below "
                f"{_POINT_SOURCE_ANGULAR_SIZE_LIMIT:g}·PSF_FWHM, or "
                "(c) use the extended regime if the target fills the pixel."
            ),
            context={
                "scene_type": scene_type,
                "angular_extent_rad": angular_extent_rad,
                "psf_fwhm_rad": psf_fwhm_rad,
                "ratio": ratio,
                "threshold": _POINT_SOURCE_ANGULAR_SIZE_LIMIT,
            },
        )

    if scene_type == "sub_pixel" and ratio < _SUBPIXEL_RECLASSIFICATION_THRESHOLD:
        warnings.warn(
            (
                f"OpticsStage: sub_pixel target has angular extent "
                f"√A_t/d = {angular_extent_rad:.3e} rad, which is only "
                f"{ratio:.3e}× PSF_FWHM ({psf_fwhm_rad:.3e} rad) — the "
                f"target is effectively a point source.  Matrix §1.1 "
                f"suggests reclassifying to scene_type='point_source' to "
                f"avoid carrying unused A_t/shape fields."
            ),
            UserWarning,
            stacklevel=2,
        )


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
            n_spiders=params.get("optics.n_spiders"),
            spider_width_m=params.get("optics.spider_width_m"),
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

        # Mode 5 (full prescription): element list injected via
        # stage_outputs["optics_config"]["element_list"] by the IO/API
        # layer before chain execution.
        optics_config = state.stage_outputs.get("optics_config", {})
        full_elements = optics_config.get("element_list")
        if full_elements is not None:
            mode = TransmissionInputMode.FULL_PRESCRIPTION
            mode_str = mode.value

        scalar_emissivity: float = params.get("optics.scalar_emissivity")
        if scalar_emissivity > 0.0 and mode != TransmissionInputMode.SCALAR:
            logger.warning(
                "optics.scalar_emissivity=%.3g is ignored in '%s' transmission "
                "mode — it applies only to scalar mode. Element emissivities "
                "are Kirchhoff-derived in element-based modes.",
                scalar_emissivity,
                mode.value,
            )

        # Modes 2-4 (Gap 68): non-scalar inputs are injected pre-chain via
        # stage_outputs["optics_config"] (Rule 6 — e.g.
        # Sensor.evaluate(extra_stage_outputs=...)); the stage only reads them.
        tx_result = resolve_transmission(
            mode,
            state.wavelength_um,
            transmission_scalar=params.get("optics.transmission_scalar"),
            scalar_emissivity=scalar_emissivity,
            transmission_spectral=optics_config.get("transmission_spectral"),
            telescope_transmission=optics_config.get("telescope_transmission"),
            filter_specs=tuple(optics_config.get("filter_specs", ())),
            key_elements=tuple(optics_config.get("key_elements", ())),
            residual_transmission=optics_config.get("residual_transmission"),
            full_elements=tuple(full_elements) if full_elements is not None else (),
            optics_temperature_K=optics_temp_K,
            optics_distance_to_fpa_m=optics_dist_m,
            aperture_diameter_m=aperture.aperture_diameter_m,
        )

        # --- Apply transmission to produce post_optics frame ---
        at_aperture = state.frames["at_aperture"]
        L_at_aperture = at_aperture.spectral_radiance
        if L_at_aperture is None:
            raise OpticsValidationError(
                "OpticsStage: 'at_aperture' frame has no spectral_radiance."
            )

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
        # Check for injected WavefrontError (e.g. Zernike from API layer).
        wfe_injected = optics_config.get("wavefront_error")
        chromatic_zernikes: dict[float, dict[int, float]] | None = None

        if wfe_injected is not None:
            wfe = wfe_injected
        else:
            wfe_mode_str: str = params.get("optics.wfe_mode")
            wfe_rms: float = params.get("optics.wfe_rms_waves")
            wfe_ref: float = params.get("optics.wfe_reference_wavelength_um")

            if wfe_mode_str == "scalar_rms":
                wfe = WavefrontError(
                    mode=WfeMode.SCALAR_RMS,
                    rms_waves=wfe_rms,
                    reference_wavelength_um=wfe_ref,
                )
            else:
                raise OpticsValidationError(
                    f"WFE mode '{wfe_mode_str}' requires a WavefrontError "
                    f"object injected via optics_config['wavefront_error']. "
                    f"Only 'scalar_rms' can be built from parameters alone."
                )

        # For field_dependent WFE: look up the selected field point.
        field_sample: FieldWfeSample | None = None
        if wfe.mode == WfeMode.FIELD_DEPENDENT:
            field_x: float = params.get("optics.field_position_x")
            field_y: float = params.get("optics.field_position_y")
            field_sample = wfe.at_field(field_x, field_y)

            # Build a ZERNIKE-mode WFE from this field point's coefficients.
            wfe_for_psf = WavefrontError(
                mode=WfeMode.ZERNIKE,
                zernike_coeffs=field_sample.zernike_coeffs,
                reference_wavelength_um=wfe.reference_wavelength_um,
            )

            # For refractive systems, extract chromatic Zernikes.
            if (
                wfe.optical_type == ElementTransferMode.REFRACTIVE
                and field_sample.chromatic_zernikes is not None
            ):
                chromatic_zernikes = field_sample.chromatic_zernikes

            state = state.with_stage_output(
                "optics",
                "field_sample",
                field_sample,
            )
            state = state.with_stage_output(
                "optics",
                "field_position_deg",
                (field_x, field_y),
            )

            logger.info(
                "Field-dependent WFE: position (%.3f, %.3f) deg, "
                "optical_type=%s, %d Zernike terms%s",
                field_x,
                field_y,
                wfe.optical_type.value,
                len(field_sample.zernike_coeffs),
                f", {len(chromatic_zernikes)} chromatic wavelengths" if chromatic_zernikes else "",
            )
        else:
            wfe_for_psf = wfe

        state = state.with_stage_output("optics", "wavefront_error", wfe)

        # --- Build EffectivePSF ---
        state, epsf = _build_effective_psf(
            state,
            params,
            aperture_m=aperture.aperture_diameter_m,
            focal_length_m=focal_length_m,
            wfe=wfe_for_psf,
            chromatic_zernikes=chromatic_zernikes,
        )

        # --- Defocus (CU-058) ---
        # Defocus is folded into the pupil WFE as Zernike Z4 inside
        # _build_effective_psf, entering the PSF and MTF product paths
        # through the SAME complex pupil (Rule 4). No spatial kernel and
        # no separate analytic MTF term — either would double-count.

        # --- Surface-roughness scatter (TIS, Gap 31) ---
        # Rule 4: kernel on the PSF path + analytic term on the MTF
        # product path; the two are exact Fourier pairs.
        roughness_m: float = params.get("optics.surface_roughness_nm")
        if roughness_m > 0.0 and epsf is not None:
            sigma_halo_m: float = params.get("optics.scatter_halo_sigma_um")
            lam_m = epsf.wavelength_um * 1e-6
            tis = total_integrated_scatter(roughness_m, lam_m)

            spacing = epsf.sample_spacing_m
            npix_sc = int(math.ceil(6.0 * sigma_halo_m / spacing)) | 1
            # Cap to the largest odd size within the PSF grid — the kernel
            # builder requires odd npix, and the grid is typically even.
            npix_cap_sc = epsf.data.shape[0] - (1 - epsf.data.shape[0] % 2)
            npix_sc = max(3, min(npix_sc, npix_cap_sc))
            k_scatter = scatter_kernel_2d(npix_sc, spacing, sigma_halo_m, tis)
            epsf = epsf.with_kernel("scatter", k_scatter)
            state = state.with_stage_output("optics", "effective_psf", epsf)
            state = state.with_stage_output("optics", "scatter_tis", tis)

            freq_mrad_sc = state.spatial_freq_cycles_per_mrad
            if freq_mrad_sc is not None:
                freq_m_sc = freq_mrad_sc / (focal_length_m * 1e-3)
                mtf_sc = scatter_mtf_1d(freq_m_sc, sigma_halo_m, tis)
                state = state.with_mtf("mtf_scatter_x", mtf_sc)
                state = state.with_mtf("mtf_scatter_y", mtf_sc.copy())

            logger.info(
                "Scatter applied: sigma_s=%.1f nm at λ=%.2f µm → TIS=%.4f, "
                "halo σ=%.0f µm, kernel %dx%d",
                roughness_m * 1e9,
                epsf.wavelength_um,
                tis,
                sigma_halo_m * 1e6,
                npix_sc,
                npix_sc,
            )

        # --- Nearfield emission ---
        nearfield_enabled: int = params.get("optics.nearfield_enabled")
        stray_includes_thermal: int = params.get("optics.stray.includes_thermal")

        if nearfield_enabled and not stray_includes_thermal:
            cold_stop_eff: float = params.get("optics.nearfield_fraction")
            nf_result = compute_nearfield_irradiance(
                tx_result.elements,
                state.wavelength_um,
                cold_stop_eff,
            )
            nf_irradiance = nf_result.total
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
            nf_result = None

        state = state.with_stage_output(
            "optics",
            "nearfield_irradiance_at_fpa",
            nf_irradiance,
        )
        if nf_result is not None:
            state = state.with_stage_output(
                "optics",
                "nearfield_per_element",
                nf_result.per_element,
            )

        # --- Stray light ---
        stray_mode_str: str = params.get("optics.stray.input_mode")
        # spectral_file mode (Gap 68): the curve is injected pre-chain via
        # stage_outputs["optics_config"]["stray_light_spectral"] (Rule 6).
        stray_spectral = optics_config.get("stray_light_spectral")
        if stray_mode_str == "spectral_file" and stray_spectral is None:
            raise OpticsValidationError(
                "optics.stray.input_mode = 'spectral_file' requires a "
                "SpectralData curve injected pre-chain via "
                "stage_outputs['optics_config']['stray_light_spectral'] — e.g. "
                "Sensor.evaluate(extra_stage_outputs={'optics_config': "
                "{'stray_light_spectral': curve}}) (Rule 6: stages do not read files)."
            )
        stray_config = StrayLightConfig(
            input_mode=StrayLightInputMode(stray_mode_str),
            veiling_glare_fraction=params.get("optics.stray.veiling_glare_fraction"),
            absolute_irradiance_W_m2=params.get("optics.stray.absolute_irradiance_W_m2"),
            spectral_file=(stray_spectral.name or "<injected>")
            if stray_spectral is not None
            else None,
            includes_thermal=bool(stray_includes_thermal),
        )

        # For veiling_glare, compute in-FOV irradiance from post-optics frame.
        in_fov_irr = None
        if stray_config.input_mode == StrayLightInputMode.VEILING_GLARE:
            # Image-plane irradiance at the FPA = radiance × the f-cone solid
            # angle Ω_cone = A_collect / focal², i.e. the etendue-invariant AΩ
            # per unit detector area (A_collect·Ω_pixel / A_pixel = A_collect /
            # focal²).  This is NOT the pixel IFOV solid angle Ω_pixel: using
            # Ω_pixel under-counts by A_collect / A_pixel ≈ (D/pitch)²·π/4 and
            # makes veiling glare effectively inert.  With Ω_cone the stray
            # electrons equal vgf × signal electrons for a uniform extended
            # scene, because the signal path also collects L·A_collect·Ω_pixel
            # onto the same pixel area.  (CU-062)
            omega_fcone = aperture.clear_area_m2 / (focal_length_m**2)
            in_fov_irr = SpectralData(
                name="in_fov_irradiance",
                wavelength_um=state.wavelength_um.copy(),
                values=L_post_optics * omega_fcone,
                unit="W/m^2/um",
                source="L_post_optics * (A_collect / focal_length^2)  [f-cone solid angle]",
            )

        stray_irradiance = compute_stray_light_irradiance(
            stray_config,
            state.wavelength_um,
            in_fov_irradiance=in_fov_irr,
            preloaded_spectral=stray_spectral,
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

        # --- Veiling-glare spatial halo (Gap 60, opt-in) ---
        # Rule 4: the veiling-glare fraction re-imaged as a Gaussian halo
        # enters BOTH paths — kernel (1−vgf)·δ + vgf·G(σ) on the PSF path,
        # exact analytic Fourier pair (1−vgf) + vgf·exp(−2π²σ²f²) on the
        # MTF product path.  Same fractional-redistribution model as the
        # TIS scatter halo (Gap 31), so the scatter builders are reused
        # with vgf as the fraction.  Off by default: the radiometric
        # pedestal above stays the always-on baseline.
        vg_mtf_enabled: int = params.get("optics.stray.veiling_glare_mtf")
        vgf = stray_config.veiling_glare_fraction
        if (
            vg_mtf_enabled
            and stray_config.input_mode == StrayLightInputMode.VEILING_GLARE
            and vgf > 0.0
            and epsf is not None
        ):
            sigma_stray_m: float = params.get("optics.stray.halo_sigma_um")
            spacing_vg = epsf.sample_spacing_m
            npix_vg = int(math.ceil(6.0 * sigma_stray_m / spacing_vg)) | 1
            npix_cap_vg = epsf.data.shape[0] - (1 - epsf.data.shape[0] % 2)
            npix_vg = max(3, min(npix_vg, npix_cap_vg))
            k_stray = scatter_kernel_2d(npix_vg, spacing_vg, sigma_stray_m, vgf)
            epsf = epsf.with_kernel("stray_halo", k_stray)
            state = state.with_stage_output("optics", "effective_psf", epsf)

            freq_mrad_vg = state.spatial_freq_cycles_per_mrad
            if freq_mrad_vg is not None:
                freq_m_vg = freq_mrad_vg / (focal_length_m * 1e-3)
                mtf_vg = scatter_mtf_1d(freq_m_vg, sigma_stray_m, vgf)
                state = state.with_mtf("mtf_stray_x", mtf_vg)
                state = state.with_mtf("mtf_stray_y", mtf_vg.copy())

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

        # Matrix §7 PSF-dependent validation on the scene_type axis
        # (separate from the radiometric regime which is IFOV-based):
        # point-source with √A_t/d > 0.1·PSF_FWHM raises, sub-pixel with
        # √A_t/d < 0.01·PSF_FWHM warns.  Reads the published descriptor
        # so the scene_type is the descriptor-declared value, not the
        # finalized regime (they can differ at the PSF/IFOV boundary).
        target_desc = source_out.get("target")
        if target_desc is not None:
            _validate_psf_regime_consistency(
                scene_type=target_desc.scene_type,
                angular_extent_rad=angular_extent_rad,
                epsf=epsf,
                focal_length_m=focal_length_m,
            )

        # Declared-vs-derived regime cross-check (ADR-0008 Amendment 1 / T2).
        # SourceStage publishes the declared scene_type; default 'auto' (no
        # cross-check) when absent (degenerate chains / minimal stage tests).
        _warn_declared_regime_mismatch(
            source_out.get("scene_type_declared", "auto"), regime
        )

        # EE_box is computed in PlatformStage from the fully degraded PSF
        # (jitter, smear, turbulence included) and applied once in
        # SpectralIntegrationStage (Rule 9).
        return state.with_stage_output("optics", "regime", regime)
