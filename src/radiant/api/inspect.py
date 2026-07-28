"""ChainResult inspector — tree-formatted view of stage outputs.

Provides :func:`inspect_result` for printing a formatted tree of all
stage outputs, noise terms, MTF terms, and metrics from a
:class:`~radiant.io.results.ChainResult`.

Usage::

    from radiant.api.inspect import inspect_result

    result = sensor.evaluate()
    print(inspect_result(result))          # full tree
    print(inspect_result(result, "optics"))  # single stage
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import numpy as np

from radiant.api.errors import ApiValidationError
from radiant.io.results import ChainResult

logger = logging.getLogger(__name__)

# Arrays larger than this collapse to NumPy's summarized `[a, b, ..., y, z]` form
# in the inspector tree, so nested arrays don't dump hundreds of lines (CU-113).
_ARRAY_SUMMARY_THRESHOLD = 20


def inspect_result(
    result: ChainResult,
    stage: str | None = None,
) -> str:
    """Format a ChainResult as a readable tree.

    Parameters
    ----------
    result:
        A completed :class:`ChainResult`.
    stage:
        If provided, show only the named stage's outputs.
        If None, show all stages, metrics, noise, and MTF.

    Returns
    -------
    str
        Formatted tree string.
    """
    # Summarise large NumPy arrays — including ones nested inside a stage-output
    # object's own repr — so a single evaluation's tree stays structural instead
    # of thousands of array-continuation lines (CU-113). `_fmt` already collapses
    # top-level arrays to `ndarray(shape=…)`; this context catches the rest.
    with np.printoptions(threshold=_ARRAY_SUMMARY_THRESHOLD, edgeitems=2):
        if stage is not None:
            return _format_stage(result, stage)
        return _format_full(result)


def _format_full(result: ChainResult) -> str:
    """Format the full ChainResult tree."""
    lines: list[str] = ["ChainResult"]

    # Metrics
    lines.append("\u251c\u2500\u2500 metrics")
    metrics = dict(result.metrics)
    metric_items = sorted(metrics.items())
    for i, (name, val) in enumerate(metric_items):
        connector = "\u2502   \u2514" if i == len(metric_items) - 1 else "\u2502   \u251c"
        lines.append(f"{connector}\u2500\u2500 {name}: {_fmt(val)}")

    # Noise terms
    if result.noise_terms:
        lines.append("\u251c\u2500\u2500 noise_terms")
        for i, nt in enumerate(result.noise_terms):
            connector = "\u2502   \u2514" if i == len(result.noise_terms) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {nt.name}: {nt.value_e:.4f} e- RMS")

    # MTF terms
    mtf_terms = dict(result.state.mtf_terms)
    if mtf_terms:
        lines.append("\u251c\u2500\u2500 mtf_terms")
        mtf_items = sorted(mtf_terms.items())
        for i, (name, arr) in enumerate(mtf_items):
            connector = "\u2502   \u2514" if i == len(mtf_items) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {name}: {_fmt(arr)}")

    # Frames
    frames = dict(result.frames)
    if frames:
        lines.append("\u251c\u2500\u2500 frames")
        frame_items = sorted(frames.keys())
        for i, fname in enumerate(frame_items):
            connector = "\u2502   \u2514" if i == len(frame_items) - 1 else "\u2502   \u251c"
            lines.append(f"{connector}\u2500\u2500 {fname}")

    # Stage outputs
    stages = dict(result.stage_outputs)
    stage_items = sorted(stages.items())
    for si, (sname, outputs) in enumerate(stage_items):
        is_last_stage = si == len(stage_items) - 1
        connector = "\u2514" if is_last_stage else "\u251c"
        lines.append(f"{connector}\u2500\u2500 stage: {sname}")
        output_items = sorted(outputs.items())
        for oi, (key, val) in enumerate(output_items):
            prefix = "    " if is_last_stage else "\u2502   "
            oconn = "\u2514" if oi == len(output_items) - 1 else "\u251c"
            lines.append(f"{prefix}{oconn}\u2500\u2500 {key}: {_fmt(val)}")

    return "\n".join(lines)


def _format_stage(result: ChainResult, stage: str) -> str:
    """Format a single stage's outputs."""
    outputs = result.stage_outputs.get(stage)
    if outputs is None:
        available = list(result.stage_outputs.keys())
        return f"Stage '{stage}' not found in result.\nAvailable stages: {available}"
    lines: list[str] = [f"stage: {stage}"]
    output_items = sorted(outputs.items())
    for i, (key, val) in enumerate(output_items):
        connector = "\u2514" if i == len(output_items) - 1 else "\u251c"
        lines.append(f"{connector}\u2500\u2500 {key}: {_fmt(val)}")
    return "\n".join(lines)


#: The PSF convolution kernels the **detector** contributes, in application order.
#: Named here (not discovered) because "which of these kernels is the detector's"
#: is a fact about the signal chain, not about any one result: pixel aperture and
#: charge diffusion are applied by OpticsStage, IPC by PerformanceStage, so no
#: single stage's output identifies the set.
_DETECTOR_KERNELS: tuple[str, ...] = ("pixel_aperture", "charge_diffusion", "ipc")


class ResultPlotNamespace:
    """Namespace for result plot accessors.

    Construct with a :class:`ChainResult`::

        plots = ResultPlotNamespace(result)
        plots.psf(); plots.noise_budget(); plots.mtf(); plots.mtf_budget()

    (``ChainResult`` lives in ``radiant.io`` which may not import the API
    layer, so the namespace is constructed here rather than attached as a
    ``result.plot`` property.) Lazily imports matplotlib — raises a
    helpful error if not installed.
    """

    def __init__(self, result: ChainResult) -> None:
        self._result = result

    def _degraded_psf(self) -> Any:
        """The **fully degraded** effective PSF — the one every spatial metric uses.

        Rule 4 makes one ``EffectivePSF`` the single source of truth for the
        spatial-domain metrics, and the stages build it up in order: ``optics``
        holds optical + pixel-aperture + diffusion, ``platform`` adds jitter,
        smear and turbulence, and ``performance`` adds the IPC and electronics
        kernels. Plotting the ``optics`` one — as these accessors used to —
        therefore showed a *different* PSF from the one EE_box, RER, FWHM and
        Strehl are computed from: with 15 µrad of jitter its peak is ~5× too
        high, because the jitter convolution is missing (owner walkthrough item
        20: "the PSF should then be the convolution of everything in the chain").

        Resolution order is most-degraded first, falling back for partial chains
        that stopped before the later stages.
        """
        outputs = self._result.stage_outputs
        for stage in ("performance", "platform", "optics"):
            psf_data = outputs.get(stage, {}).get("effective_psf")
            if psf_data is not None:
                return psf_data
        raise ApiValidationError(
            "No effective PSF found in result stage_outputs — looked in "
            "'performance', 'platform' and 'optics'. The chain must run "
            "OpticsStage to build one."
        )

    def psf(self, **kwargs: Any) -> Any:
        """Plot the fully degraded effective PSF as a 2D image.

        Cropped to a few detector pixels around the core and outlining the pixel
        the core lands in (walkthrough items 14 and 20); pass ``span_pixels`` to
        widen the window or ``pixel_outline=False`` to drop the outline.
        """
        from radiant.api.plot import plot_psf

        return plot_psf(self._degraded_psf(), **kwargs)

    def psf_pixel_grid(self, **kwargs: Any) -> Any:
        """Plot the fully degraded effective PSF with the detector **pixel grid** overlaid.

        Same figure as :meth:`psf`, but with pixel-boundary gridlines across the
        whole cropped window rather than a single outlined pixel, so the viewer
        sees how the PSF spreads across neighbouring detector pixels (arch-doc
        §4.4.1 Detector row). A GUI draw over already-computed data — no results
        change. Raises :class:`ApiValidationError` when no effective PSF exists.
        """
        from radiant.api.plot import plot_psf

        return plot_psf(self._degraded_psf(), pixel_grid=True, **kwargs)

    def spectral_atmosphere_background(self, **kwargs: Any) -> Any:
        """Plot the **background** arm's transmittance and path radiance vs λ.

        The sibling of :meth:`spectral_atmosphere`, which draws the *target*
        arm. The two are genuinely different columns whenever the target sits
        above the surface: the target arm carries ``τ_up`` / ``L_path_up``
        (target → sensor), while a surface background is seen through
        ``τ_full_up`` / ``L_path_full`` (ground → sensor), the full column
        including the air *below* the target. On the shipped MWIR example with a
        500 km sensor and a 10 km target the two transmittances are 0.87 and
        0.50 — the background is nearly a factor of two dimmer through the
        atmosphere, which is exactly the effect that sets contrast (owner
        walkthrough item 8: "depending on geometry these could be different,
        lets show both").

        For a surface-level target the two are identical by construction, and
        for an up-looking scene the topology sets the full column equal to the
        observer leg, so the two figures coincide — correctly, not by accident.

        Raises :class:`ApiValidationError` when the atmosphere stage did not run.
        """
        from radiant.api.plot import plot_atmosphere_spectral

        quantities = self._result.stage_outputs.get("atmosphere", {}).get("atm_quantities")
        if quantities is None:
            raise ApiValidationError(
                "No atmospheric quantities found in result "
                "stage_outputs['atmosphere']['atm_quantities'] — the chain must "
                "run AtmosphereStage."
            )
        return plot_atmosphere_spectral(
            self._result.state.wavelength_um,
            quantities.tau_full_up,
            quantities.L_path_full,
            title="Background path — τ_full_up & L_path_full (ground → sensor)",
            **kwargs,
        )

    def spectral_at_aperture_arms(self, **kwargs: Any) -> Any:
        """Plot the target and background radiance **at the aperture** together.

        The end of the atmospheric story on one axis: what actually arrives after
        each arm's own transmittance and path radiance have been applied (owner
        walkthrough item 8's third plot). Their ratio here — not the ratio at the
        source — is what the contrast metrics see.

        The background curve appears only when a background is configured; a
        target-only scene draws the target alone rather than failing.
        """
        from radiant.api.plot import plot_spectral_multi

        frames = self._result.frames
        target = frames.get("at_aperture_target") or frames.get("at_aperture")
        if target is None or target.spectral_radiance is None:
            raise ApiValidationError(
                "No at-aperture frame found in result.frames "
                "('at_aperture_target') — the chain must run AtmosphereStage."
            )
        series: dict[str, Any] = {"target": target.spectral_radiance}
        background = frames.get("at_aperture_background")
        if background is not None and background.spectral_radiance is not None:
            series["background"] = background.spectral_radiance
        return plot_spectral_multi(
            self._result.state.wavelength_um,
            series,
            ylabel="Radiance at aperture (W/m²/sr/µm)",
            title="At aperture — target vs background (after atmosphere)",
            **kwargs,
        )

    def spectral_irradiance_at_image(self, **kwargs: Any) -> Any:
        """Plot the at-image spectral irradiance E(λ) on one detector pixel.

        What the detector actually sees: power per unit focal-plane area,
        W/m²/µm (owner walkthrough item 16). This is the same ``photon_rate``
        the stage integrates into ``signal_e``, expressed as an irradiance —

            Φ(λ) = photon_rate(λ) · hc/λ      [W/µm on one pixel]
            E(λ) = Φ(λ) / A_pixel             [W/m²/µm at the image]

        — so it is **regime-correct by construction** (the rate already carries
        Ω_pixel for an extended scene and Ω_target for a point source) and
        integrates back to the published electron count exactly. Unlike
        :meth:`spectral_inband`, which draws the at-FPA *radiance*, this is the
        quantity the electron budget is built from, so the step from spectrum to
        electrons is traceable on one axis.

        Raises :class:`ApiValidationError` when the stage did not publish it —
        which happens only when the detector pixel area is not yet resolvable.
        """
        from radiant.api.plot import plot_spectral

        irradiance = self._result.stage_outputs.get("spectral_integration", {}).get(
            "spectral_irradiance_at_image"
        )
        if irradiance is None:
            raise ApiValidationError(
                "No at-image spectral irradiance found in "
                "stage_outputs['spectral_integration']"
                "['spectral_irradiance_at_image'] — the chain must run "
                "SpectralIntegrationStage with a resolvable detector pixel pitch."
            )
        kwargs.setdefault("ylabel", "Irradiance (W/m²/µm)")
        kwargs.setdefault("title", "At-image spectral irradiance on one pixel")
        return plot_spectral(self._result.state.wavelength_um, irradiance, **kwargs)

    def psf_kernels(self, **kwargs: Any) -> Any:
        """Plot every convolution kernel that degraded the effective PSF.

        One 2-D map per kernel, in the order applied — the optical PSF's
        successive degradations made visible instead of merely named in
        ``convolution_history`` (walkthrough item 15). Raises
        :class:`ApiValidationError` when the PSF retains no kernels, which means
        every optional degradation is configured to zero.
        """
        from radiant.api.plot import plot_psf_kernels

        return plot_psf_kernels(self._degraded_psf(), **kwargs)

    def detector_kernels(self, **kwargs: Any) -> Any:
        """Plot only the **detector-side** PSF convolution kernels.

        The subset of :meth:`psf_kernels` contributed by the detector — pixel
        aperture, charge diffusion, and inter-pixel capacitance — so the pixel
        illustration can sit beside the kernel that pixel actually imposes on the
        PSF (walkthrough item 19). Raises :class:`ApiValidationError` when none
        of them is present.
        """
        from radiant.api.plot import plot_psf_kernels

        return plot_psf_kernels(self._degraded_psf(), names=_DETECTOR_KERNELS, **kwargs)

    def pupil_amplitude(self, **kwargs: Any) -> Any:
        """Plot the pupil amplitude (apodization) map (Gap 89).

        Draws the dimensionless transmission across the complex pupil that
        produced the PSF/MTF — central obscuration, spider vanes, and any
        measured mask override — from ``stage_outputs['optics']
        ['pupil_amplitude']`` (arch-doc §4.4.1 Optics view). Raises
        :class:`ApiValidationError` when the map is absent.
        """
        from radiant.api.plot import plot_pupil_amplitude

        optics = self._result.stage_outputs.get("optics", {})
        amplitude = optics.get("pupil_amplitude")
        if amplitude is None:
            raise ApiValidationError(
                "No pupil amplitude map found in result "
                "stage_outputs['optics']['pupil_amplitude'] — the chain must "
                "run OpticsStage to build the complex pupil."
            )
        return plot_pupil_amplitude(
            amplitude, extent_m=optics.get("pupil_plane_extent_m"), **kwargs
        )

    def pupil_phase(self, **kwargs: Any) -> Any:
        """Plot the pupil wavefront-error (phase) map in waves (Gap 89).

        Draws the wavefront error across the complex pupil in **waves** at
        ``stage_outputs['optics']['pupil_wavelength_um']`` (phase_radians / 2π,
        zero outside the clear aperture), from ``stage_outputs['optics']
        ['pupil_phase_waves']`` (arch-doc §4.4.1 Optics view). An unaberrated
        system renders flat. Raises :class:`ApiValidationError` when the map is
        absent (e.g. a WFE mode with no pupil-phase representation).
        """
        from radiant.api.plot import plot_pupil_phase

        optics = self._result.stage_outputs.get("optics", {})
        phase_waves = optics.get("pupil_phase_waves")
        if phase_waves is None:
            raise ApiValidationError(
                "No pupil phase (WFE) map found in result "
                "stage_outputs['optics']['pupil_phase_waves'] — the chain must "
                "run OpticsStage with a WFE mode that has a pupil-phase "
                "representation (scalar_rms / zernike)."
            )
        return plot_pupil_phase(phase_waves, extent_m=optics.get("pupil_plane_extent_m"), **kwargs)

    def noise_budget(self, **kwargs: Any) -> Any:
        """Plot the noise budget as a horizontal bar chart."""
        from radiant.api.plot import plot_noise_budget

        return plot_noise_budget(self._result.noise_terms, **kwargs)

    def noise_pie(self, **kwargs: Any) -> Any:
        """Plot the noise budget as a variance-weighted pie chart.

        Same ``result.noise_terms`` data as :meth:`noise_budget` (the bar), a
        different mark: slices are proportional to each term's **variance**
        (σ_i²) because noise adds in quadrature (σ_total² = Σ σ_i²), so the
        wedges sum to 100 % of the noise **power** and each is labelled with the
        term name, its σ_i in e- RMS, and its % of the variance (zero terms
        omitted). Raises :class:`ApiValidationError` when the result carries no
        noise terms (the chain must run through ReadoutStage).
        """
        from radiant.api.plot import plot_noise_pie

        if not self._result.noise_terms:
            raise ApiValidationError(
                "No noise terms found in result.noise_terms — the chain must run "
                "the detector/readout stages to assemble the noise budget."
            )
        return plot_noise_pie(self._result.noise_terms, **kwargs)

    def mtf(self, **kwargs: Any) -> Any:
        """Plot all MTF terms, with the detector Nyquist limit marked.

        The Nyquist frequency is read from
        ``stage_outputs['performance']['nyquist_freq_cycles_per_mrad']`` —
        published by ``PerformanceStage`` on the chain's own angular axis — and
        drawn as a red dashed vertical line. It is absent (and the marker simply
        omitted) when the chain ran without a focal length.
        """
        from radiant.api.plot import plot_mtf_terms

        performance = self._result.stage_outputs.get("performance", {})
        return plot_mtf_terms(
            dict(self._result.state.mtf_terms),
            self._result.state.spatial_freq_cycles_per_mrad,
            nyquist_cycles_per_mrad=performance.get("nyquist_freq_cycles_per_mrad"),
            **kwargs,
        )

    def mtf_budget(self, **kwargs: Any) -> Any:
        """Plot the per-contributor MTF-at-Nyquist budget (Gap 19)."""
        from radiant.api.plot import plot_mtf_budget

        budget = self._result.stage_outputs.get("performance", {}).get("mtf_budget")
        if budget is None:
            raise ApiValidationError(
                "No MTF budget found in result stage_outputs['performance'] — "
                "the chain must run PerformanceStage with an MTF product path."
            )
        return plot_mtf_budget(budget, **kwargs)

    def spectral_source(self, **kwargs: Any) -> Any:
        """Plot the source (target + background) spectral radiance vs λ.

        Draws the target arm and, when present, the background arm from the
        earliest stored spectral-radiance frames — ``at_aperture_target``
        (falling back to the canonical ``at_aperture``) and
        ``at_aperture_background`` — in W/m²/sr/µm. These are the real stored
        frames closest to the arch-doc §4.4 Source default view; SourceStage
        itself publishes no radiance frame (radiance assembly happens in
        AtmosphereStage), so no at-target frame exists to plot without
        recomputation.
        """
        from radiant.api.plot import plot_spectral_multi

        frames = self._result.frames
        target = frames.get("at_aperture_target") or frames.get("at_aperture")
        if target is None or target.spectral_radiance is None:
            raise ApiValidationError(
                "No target spectral-radiance frame found in result.frames "
                "('at_aperture_target' / 'at_aperture') — the chain must run "
                "AtmosphereStage to assemble at-aperture radiance."
            )
        series: dict[str, Any] = {"target": target.spectral_radiance}
        background = frames.get("at_aperture_background")
        if background is not None and background.spectral_radiance is not None:
            series["background"] = background.spectral_radiance
        return plot_spectral_multi(
            target.wavelength_um,
            series,
            title="Source spectral radiance (at aperture)",
            ylabel="Radiance (W/m²/sr/µm)",
            **kwargs,
        )

    def spectral_source_emission(self, **kwargs: Any) -> Any:
        """Plot the pre-atmosphere source emission (target + background) vs λ.

        Draws the target arm and, when present, the background arm from the
        stored source-emission frames — ``at_source_target`` and
        ``at_source_background`` — in W/m²/sr/µm. These are the emitted+reflected
        radiance *leaving the source* **before** the atmospheric up-leg (Gap 91):
        the ``L_source`` the at-aperture assembly consumes, so
        ``at_aperture_target ≈ τ_up · at_source_target + L_path_up``. Unlike
        :meth:`spectral_source` (which draws the *at-aperture* frames, post
        atmosphere), this accessor isolates what the target/background emit and
        reflect before the atmosphere modulates them (arch-doc §4.4.1 Source
        view). Raises :class:`ApiValidationError` when the frame is absent.
        """
        from radiant.api.plot import plot_spectral_multi

        frames = self._result.frames
        target = frames.get("at_source_target")
        if target is None or target.spectral_radiance is None:
            raise ApiValidationError(
                "No source-emission frame found in result.frames "
                "('at_source_target') — the chain must run AtmosphereStage to "
                "assemble the pre-atmosphere source radiance."
            )
        series: dict[str, Any] = {"target": target.spectral_radiance}
        background = frames.get("at_source_background")
        if background is not None and background.spectral_radiance is not None:
            series["background"] = background.spectral_radiance
        return plot_spectral_multi(
            target.wavelength_um,
            series,
            title="Source emission spectral radiance (before atmosphere)",
            ylabel="Radiance (W/m²/sr/µm)",
            **kwargs,
        )

    def target_reflectance(self, **kwargs: Any) -> Any:
        """Plot the target's resolved reflectance ρ(λ) vs λ (dimensionless).

        Draws ``stage_outputs['source']['reflectance']`` — the surface
        property the analyst specified, resolved onto the chain wavelength
        grid by :mod:`radiant.core.target_reflectance`.  Two pathways
        publish it: a pure-reflective target (scalar ``source.target
        .reflectance`` or a λ-dependent ``reflectance_path`` CSV) and the
        mixed emit+reflect target, whose ρ = 1 − ε is Kirchhoff-derived
        (Rule 5).  This is the *input* view — the radiance ρ produces under
        the scene illumination is :meth:`spectral_reflected_radiance`.

        Raises :class:`ApiValidationError` when the scene's target carries
        no reflectance at all (a pure-thermal target, or a user-supplied
        at-aperture / at-source radiance or point intensity).
        """
        from radiant.api.plot import plot_spectral_multi

        reflectance = self._result.stage_outputs.get("source", {}).get("reflectance")
        if reflectance is None:
            raise ApiValidationError(
                "No target reflectance found in stage_outputs['source']"
                "['reflectance'] — this scene's target carries none. Set "
                "source.target.reflectance (or source.target.reflectance_path "
                "for a spectral ρ(λ)) for a pure-reflective target, or "
                "source.target.emissivity + temperature for the mixed "
                "emit+reflect target whose ρ = 1 − ε is Kirchhoff-derived."
            )
        return plot_spectral_multi(
            reflectance.wavelength_um,
            {"target": reflectance.values},
            title="Target reflectance ρ(λ)",
            ylabel="Reflectance ρ (dimensionless)",
            **kwargs,
        )

    def spectral_reflected_radiance(self, **kwargs: Any) -> Any:
        """Plot the reflected radiance leaving the target vs λ.

        Draws the ``at_source_target_reflected`` frame — the ρ-proportional
        part of the pre-atmosphere source emission (direct solar + diffuse
        sky, with the ε·B(T_t) self-emission dropped), in W/m²/sr/µm.  It is
        the radiance the reflectance plotted by :meth:`target_reflectance`
        actually produces under this scene's illumination, so the pair reads
        as cause and effect: change ρ, or move the sun on the Geometry stage,
        and this curve moves with it.

        For a pure-reflective target this is the whole source emission
        (:meth:`spectral_source_emission`); for a mixed emit+reflect target
        it isolates the reflected fraction.  It is identically zero for a
        scene with no reflective physics (pure-thermal target, or the sun
        below the horizon).  Raises :class:`ApiValidationError` when the
        frame is absent (the chain did not run AtmosphereStage).
        """
        from radiant.api.plot import plot_spectral_multi

        frame = self._result.frames.get("at_source_target_reflected")
        if frame is None or frame.spectral_radiance is None:
            raise ApiValidationError(
                "No reflected-radiance frame found in result.frames "
                "('at_source_target_reflected') — the chain must run "
                "AtmosphereStage to assemble the reflected source radiance."
            )
        return plot_spectral_multi(
            frame.wavelength_um,
            {"target (reflected)": frame.spectral_radiance},
            title="Reflected radiance leaving the target (before atmosphere)",
            ylabel="Radiance (W/m²/sr/µm)",
            **kwargs,
        )

    def optical_throughput(self, **kwargs: Any) -> Any:
        """Plot the assembled system optical throughput τ_opt(λ) (Gap 90).

        Draws the stored ``stage_outputs['optics']['tau_opt_spectral']``
        ``SpectralData`` — the dimensionless system transmission across the
        band (the product of every element's net throughput) — against its
        own wavelength grid (arch-doc §4.4.1 Optics view). Raises
        :class:`ApiValidationError` when the optics outputs are absent.
        """
        from radiant.api.plot import plot_optical_throughput

        optics = self._result.stage_outputs.get("optics", {})
        tau_opt_spectral = optics.get("tau_opt_spectral")
        if tau_opt_spectral is None:
            raise ApiValidationError(
                "No system optical throughput found in "
                "stage_outputs['optics']['tau_opt_spectral'] — the chain must "
                "run OpticsStage to assemble the optical transmission."
            )
        return plot_optical_throughput(
            tau_opt_spectral.wavelength_um,
            tau_opt_spectral.values,
            **kwargs,
        )

    def coating_spectra(self, **kwargs: Any) -> Any:
        """Plot per-element coating spectra — R / T / ε vs λ (Gap 90).

        Draws, for each optical element in
        ``stage_outputs['optics']['elements']``, its stored reflectance R and
        transmittance T ``SpectralData`` plus its Kirchhoff-derived emissivity
        ε (``element.emissivity``; ε = 1 − R for mirrors, the declared train
        emissivity for lumped pseudo-elements, 0 for simple refractives) — all
        dimensionless, on one y-axis (arch-doc §4.4.1 Optics view). A curve
        that is identically zero is omitted (a mirror contributes only R and ε,
        a simple refractive only T), so the overlay stays uncluttered without
        hiding any non-trivial contribution. Raises
        :class:`ApiValidationError` when no elements are present.
        """
        from radiant.api.plot import plot_coating_spectra

        optics = self._result.stage_outputs.get("optics", {})
        elements = optics.get("elements")
        if not elements:
            raise ApiValidationError(
                "No optical elements found in "
                "stage_outputs['optics']['elements'] — the chain must run "
                "OpticsStage with a resolved element list."
            )
        series: dict[str, Any] = {}
        for element in elements:
            for symbol, curve in (
                ("R", element.reflectance),
                ("T", element.transmittance),
                ("ε", element.emissivity),
            ):
                # Omit an all-zero curve: it carries no coating information and
                # only clutters the legend (a mirror has T ≡ 0; a simple
                # refractive has ε ≡ 0).
                if not np.any(curve.values):
                    continue
                series[f"{element.name} {symbol}"] = (curve.wavelength_um, curve.values)
        if not series:
            raise ApiValidationError(
                "Optical elements carry no non-zero coating spectra to plot "
                "(all R/T/ε curves are identically zero)."
            )
        return plot_coating_spectra(series, **kwargs)

    def spectral_atmosphere(self, **kwargs: Any) -> Any:
        """Plot atmospheric transmittance τ_atm(λ) and path radiance L_path(λ).

        Draws the two stored ``stage_outputs['atmosphere']`` spectral arrays —
        ``tau_atm`` (dimensionless) and ``L_path`` (W/m²/sr/µm) — on twin,
        unit-labelled y-axes (arch-doc §4.4 Atmosphere default view).
        """
        from radiant.api.plot import plot_atmosphere_spectral

        atmosphere = self._result.stage_outputs.get("atmosphere", {})
        tau_atm = atmosphere.get("tau_atm")
        l_path = atmosphere.get("L_path")
        if tau_atm is None or l_path is None:
            raise ApiValidationError(
                "No atmospheric spectral arrays found in "
                "stage_outputs['atmosphere'] ('tau_atm', 'L_path') — the chain "
                "must run AtmosphereStage."
            )
        # Named as the target arm so it reads as one of a pair with
        # spectral_atmosphere_background rather than as "the" atmosphere.
        kwargs.setdefault("title", "Target path — τ_up & L_path_up (target → sensor)")
        return plot_atmosphere_spectral(
            self._result.state.wavelength_um,
            tau_atm,
            l_path,
            **kwargs,
        )

    def spectral_inband(self, **kwargs: Any) -> Any:
        """Plot the band-filtered post-optics spectral radiance vs λ.

        Draws the stored ``post_optics`` frame — the at-FPA spectral radiance
        (at-aperture radiance filtered by optical throughput) that
        SpectralIntegrationStage integrates over the band — in W/m²/sr/µm
        (arch-doc §4.4 Spectral Integration default view). It is the real
        integrand frame; the collapsed in-band scalar is a single value, not a
        spectrum.
        """
        from radiant.api.plot import plot_spectral

        frame = self._result.frames.get("post_optics")
        if frame is None or frame.spectral_radiance is None:
            raise ApiValidationError(
                "No 'post_optics' spectral-radiance frame found in "
                "result.frames — the chain must run OpticsStage to produce the "
                "band-filtered at-FPA radiance."
            )
        return plot_spectral(
            frame.wavelength_um,
            frame.spectral_radiance,
            title="In-band spectral radiance (post-optics)",
            ylabel="Radiance (W/m²/sr/µm)",
            **kwargs,
        )


def _fmt(val: Any) -> str:
    """Format a value for tree display."""
    if isinstance(val, np.ndarray):
        if val.size <= 4:
            return repr(val)
        return f"ndarray(shape={val.shape}, dtype={val.dtype})"
    if isinstance(val, float):
        return f"{val:.6g}"
    if isinstance(val, Mapping):
        return f"dict({len(val)} keys)"
    return repr(val)
