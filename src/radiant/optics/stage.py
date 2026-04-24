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
from radiant.optics.defocus import defocus_kernel_2d, defocus_sigma_m
from radiant.optics.diffusion_kernel import make_diffusion_kernel_2d
from radiant.optics.element import ElementTransferMode
from radiant.optics.nearfield_irradiance import compute_nearfield_irradiance
from radiant.optics.pixel_kernel import make_pixel_aperture_kernel_2d
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.optics.psf_mono import compute_psf
from radiant.optics.psf_poly import (
    compute_polychromatic_psf,
)
from radiant.optics.pupil_amplitude import make_pupil_amplitude
from radiant.optics.pupil_mtf import (
    polychromatic_pupil_mtf,
    pupil_autocorrelation_mtf_1d,
    pupil_autocorrelation_mtf_2d,
)
from radiant.optics.pupil_phase import make_pupil_phase, make_pupil_phase_zernike
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

    If the existing WFE already has a Z4 Zernike coefficient, the defocus
    contribution is added to it.  For scalar-RMS WFE, converts to a
    single-term Zernike with Z4 only.
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
        # Convert scalar RMS to a Z4-only Zernike (defocus dominates).
        return WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs={4: z4_waves},
            reference_wavelength_um=wfe.reference_wavelength_um,
        )
    if wfe.mode == WfeMode.ZERNIKE:
        assert wfe.zernike_coeffs is not None
        new_coeffs = dict(wfe.zernike_coeffs)
        new_coeffs[4] = new_coeffs.get(4, 0.0) + z4_waves
        return WavefrontError(
            mode=WfeMode.ZERNIKE,
            zernike_coeffs=new_coeffs,
            reference_wavelength_um=wfe.reference_wavelength_um,
        )
    # Other modes: cannot fold defocus — return as-is.
    return wfe


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
    defocus_um: float = 0.0,
    f_number: float = 0.0,
) -> ChainState:
    """Compute optical MTF via pupil autocorrelation and store in ChainState.

    For monochromatic: builds pupil, computes 2-D autocorrelation MTF,
    extracts 1-D x and y slices.
    For polychromatic: calls ``polychromatic_pupil_mtf()`` for weighted
    average of monochromatic pupil autocorrelation MTFs.

    If ``defocus_um != 0``, folds defocus into the pupil phase as
    equivalent Zernike Z4 so that ``mtf_optics`` captures
    diffraction + WFE + defocus as a single term.

    Stores ``mtf_optics_x``, ``mtf_optics_y`` in ``state.mtf_terms``
    and sets ``state.spatial_freq_cycles_per_mrad``.
    """
    pupil_npix = 128

    if n_psf_wavelengths <= 1:
        # Monochromatic: recompute pupil and autocorrelation MTF.
        assert wavelength_m is not None

        # Fold defocus into WFE for MTF product path.
        wfe_mtf = _add_defocus_to_wfe(wfe, defocus_um, f_number, wavelength_m)

        config = compute_sampling(
            wavelength_m=wavelength_m,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            pupil_npix=pupil_npix,
            psf_oversample=8,
        )

        amplitude = make_pupil_amplitude(pupil_npix, obscuration)
        if wfe_mtf is None:
            phase = np.zeros((pupil_npix, pupil_npix), dtype=np.float64)
        elif wfe_mtf.mode == WfeMode.SCALAR_RMS:
            rms = wfe_mtf.rms_waves if wfe_mtf.rms_waves is not None else 0.0
            phase = make_pupil_phase(pupil_npix, rms, wavelength_m)
        elif wfe_mtf.mode == WfeMode.ZERNIKE:
            assert wfe_mtf.zernike_coeffs is not None
            ref_m = wfe_mtf.reference_wavelength_um * 1e-6
            phase = make_pupil_phase_zernike(
                pupil_npix,
                wfe_mtf.zernike_coeffs,
                reference_wavelength_m=ref_m,
                operating_wavelength_m=wavelength_m,
                obscuration_ratio=obscuration,
            )
        else:
            # Unsupported WFE mode for pupil autocorrelation — skip MTF.
            logger.warning(
                "WFE mode %r not supported for pupil autocorrelation MTF; skipping.",
                wfe_mtf.mode.value,
            )
            return state

        mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
        freq_m, mtf_x = pupil_autocorrelation_mtf_1d(mtf_2d, sample_spacing_m, "x")
        _, mtf_y = pupil_autocorrelation_mtf_1d(mtf_2d, sample_spacing_m, "y")
    else:
        # Polychromatic: weighted average of monochromatic pupil MTFs.
        assert psf_wl_m is not None
        assert weights is not None

        # For polychromatic, defocus is folded into WFE for each wavelength
        # inside polychromatic_pupil_mtf via the WFE object.
        wl_center_m = float(psf_wl_m[len(psf_wl_m) // 2])
        wfe_mtf = _add_defocus_to_wfe(wfe, defocus_um, f_number, wl_center_m)

        freq_m, mtf_x, mtf_y = polychromatic_pupil_mtf(
            wavelengths_m=psf_wl_m,
            weights=weights,
            focal_length_m=focal_length_m,
            aperture_diameter_m=aperture_m,
            pixel_pitch_m=pixel_pitch_m,
            obscuration_ratio=obscuration,
            wfe=wfe_mtf,
            pupil_npix=pupil_npix,
            psf_oversample=8,
            chromatic_zernikes=chromatic_zernikes,
        )

    # Convert frequency from cycles/m to cycles/mrad.
    # f_angular [cycles/mrad] = f_focal [cycles/m] * focal_length_m * 1e3
    # (1 mrad on the focal plane = focal_length_m * 1e-3 m)
    freq_cycles_per_mrad = freq_m * focal_length_m * 1e3

    state = state.with_spatial_freq(freq_cycles_per_mrad)
    state = state.with_mtf("mtf_optics_x", mtf_x)
    state = state.with_mtf("mtf_optics_y", mtf_y)

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
        psf_arr = compute_psf(config, obscuration, wfe)
        sample_spacing_m = config.focal_spacing_m
        wavelength_um = wavelength_m * 1e6
    else:
        # --- Polychromatic path ---
        wl_um = state.wavelength_um
        psf_wl_um = np.linspace(float(wl_um[0]), float(wl_um[-1]), n_psf_wavelengths)
        psf_wl_m = psf_wl_um * 1e-6

        # Compute photon-flux weights: L(lambda) * lambda/(hc).
        post_optics_frame = state.frames.get("post_optics")
        if post_optics_frame is not None and post_optics_frame.spectral_radiance is not None:
            L_interp = np.interp(psf_wl_um, wl_um, post_optics_frame.spectral_radiance)
        else:
            at_aperture = state.frames["at_aperture"]
            if at_aperture.spectral_radiance is not None:
                L_interp = np.interp(psf_wl_um, wl_um, at_aperture.spectral_radiance)
            else:
                L_interp = np.ones(n_psf_wavelengths)

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
        )

        psf_arr = poly_result.combined_psf
        sample_spacing_m = poly_result.pixel_scale_m

        # Flux-weighted mean wavelength for EffectivePSF metadata.
        wavelength_um = float(np.average(psf_wl_um, weights=weights))

        logger.info(
            "Polychromatic PSF: %d wavelengths (%.2f-%.2f um), "
            "effective lambda = %.3f um",
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
            state = state.with_stage_output(
                "optics", "per_wavelength_psfs", per_wl_epsfs
            )

    epsf = build_effective_psf(
        psf_arr,
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

    # --- §6 step 2: Charge diffusion Gaussian kernel ---
    diffusion_length_m: float = params.get("detector.charge_diffusion_length_m")
    if diffusion_length_m > 0.0:
        sigma_diff = diffusion_length_m / math.sqrt(2.0)
        npix_diff = int(math.ceil(6.0 * sigma_diff / sample_spacing_m)) | 1
        npix_diff = min(npix_diff, epsf.data.shape[0])
        npix_diff = max(npix_diff, 3)
        k_diff = make_diffusion_kernel_2d(npix_diff, sample_spacing_m, diffusion_length_m)
        epsf = epsf.with_kernel("charge_diffusion", k_diff)

    # --- MTF product path: optical MTF via pupil autocorrelation ---
    defocus_um: float = params.get("optics.defocus_um")
    f_number: float = params.get("optics.f_number")
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
        defocus_um=defocus_um,
        f_number=f_number,
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

    if math.isnan(angular_extent_rad):
        logger.warning(
            "_finalize_regime: angular_extent_rad is NaN; "
            "falling back to tentative regime '%s'.",
            tentative.value,
        )
        return tentative

    if not math.isfinite(angular_extent_rad) and angular_extent_rad > 0:
        return RadiometricRegime.EXTENDED

    if angular_extent_rad >= 2.0 * psf_fwhm_rad:
        return RadiometricRegime.EXTENDED
    if angular_extent_rad <= 0.5 * psf_fwhm_rad:
        return RadiometricRegime.POINT_SOURCE
    return RadiometricRegime.SUB_PIXEL


# Matrix §7 thresholds for PSF-dependent angular-size checks.
# Point-source: fail above 0.1 × PSF_FWHM (angular extent no longer << PSF).
_POINT_SOURCE_ANGULAR_SIZE_LIMIT: float = 0.1
# Sub-pixel: warn below 0.01 × PSF_FWHM (descriptor has degraded into the
# point-source corner of the §1.1 decision region).
_SUBPIXEL_RECLASSIFICATION_THRESHOLD: float = 0.01


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

        # Mode 5 (full prescription): element list injected via
        # stage_outputs["optics_config"]["element_list"] by the IO/API
        # layer before chain execution.
        optics_config = state.stage_outputs.get("optics_config", {})
        full_elements = optics_config.get("element_list")
        if full_elements is not None:
            mode = TransmissionInputMode.FULL_PRESCRIPTION
            mode_str = mode.value

        tx_result = resolve_transmission(
            mode,
            state.wavelength_um,
            transmission_scalar=params.get("optics.transmission_scalar"),
            full_elements=tuple(full_elements) if full_elements is not None else (),
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
                raise ValueError(
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
                "optics", "field_sample", field_sample,
            )
            state = state.with_stage_output(
                "optics", "field_position_deg", (field_x, field_y),
            )

            logger.info(
                "Field-dependent WFE: position (%.3f, %.3f) deg, "
                "optical_type=%s, %d Zernike terms%s",
                field_x,
                field_y,
                wfe.optical_type.value,
                len(field_sample.zernike_coeffs),
                f", {len(chromatic_zernikes)} chromatic wavelengths"
                if chromatic_zernikes
                else "",
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

        # --- Defocus blur ---
        defocus_um: float = params.get("optics.defocus_um")
        if defocus_um != 0.0 and epsf is not None:
            f_number: float = params.get("optics.f_number")
            defocus_m = defocus_um * 1e-6
            sigma_def = defocus_sigma_m(defocus_m, f_number)

            # Warn if Gaussian approximation may be inaccurate.
            # Z4 = delta / (8 * lambda * f/#^2)  — warn if > ~2 waves.
            wl_center_m = float(
                state.wavelength_um[len(state.wavelength_um) // 2]
            ) * 1e-6
            if wl_center_m > 0.0:
                z4_waves = abs(defocus_m) / (8.0 * wl_center_m * f_number**2)
                if z4_waves > 2.0:
                    logger.warning(
                        "Defocus = %.1f µm produces %.1f waves of Z4 at "
                        "λ=%.2f µm, f/%.1f. Gaussian approximation may be "
                        "inaccurate; consider Zernike Z4 wavefront error "
                        "for large defocus.",
                        defocus_um,
                        z4_waves,
                        wl_center_m * 1e6,
                        f_number,
                    )

            # Kernel size: 6σ span, capped to PSF grid.
            sample_spacing_m = epsf.sample_spacing_m
            npix_needed = int(math.ceil(6.0 * sigma_def / sample_spacing_m)) | 1
            npix_needed = min(npix_needed, epsf.data.shape[0])
            npix_needed = max(npix_needed, 3)

            kernel = defocus_kernel_2d(npix_needed, sample_spacing_m, sigma_def)
            epsf = epsf.with_kernel("defocus", kernel)

            # Update stored ePSF.
            state = state.with_stage_output("optics", "effective_psf", epsf)
            state = state.with_stage_output(
                "optics", "defocus_sigma_m", sigma_def,
            )

            logger.info(
                "Defocus applied: δ=%.1f µm, σ=%.3f µm (%.3f pix), "
                "kernel %dx%d",
                defocus_um,
                sigma_def * 1e6,
                sigma_def / sample_spacing_m,
                npix_needed,
                npix_needed,
            )

        # --- Nearfield emission ---
        nearfield_enabled: int = params.get("optics.nearfield_enabled")
        stray_includes_thermal: int = params.get("optics.stray.includes_thermal")

        if nearfield_enabled and not stray_includes_thermal:
            cold_stop_eff: float = params.get("optics.cold_stop_efficiency")
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

        ee_box = _compute_ee_box(regime, epsf)

        return state.with_stage_output("optics", "EE_box", ee_box).with_stage_output(
            "optics", "regime", regime
        )
