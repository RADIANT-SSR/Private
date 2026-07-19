"""Plotting utilities for RADIANT results.

matplotlib is an **optional** dependency. All functions import it lazily
and raise a clear error if it is not installed.

The :class:`Plottable` protocol defines the interface for objects that
can produce a matplotlib Figure via ``.plot()``.

Usage::

    from radiant.api.plot import plot_sweep, plot_noise_budget
    fig = plot_sweep(sweep_result)
    fig.savefig("snr_vs_aperture.png")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api.sweep import Sweep2DResult, SweepResult
    from radiant.optics.psf.effective import EffectivePSF

logger = logging.getLogger(__name__)


def _require_matplotlib() -> Any:
    """Import and return matplotlib.pyplot, raising a helpful error if missing."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError:
        raise ImportError(
            "matplotlib is required for plotting but is not installed.\n"
            "Install it with: pip install matplotlib"
        ) from None


# ------------------------------------------------------------------
# Plottable protocol
# ------------------------------------------------------------------


@runtime_checkable
class Plottable(Protocol):
    """Protocol for objects that can produce a matplotlib Figure."""

    def plot(self, **kwargs: Any) -> Figure:
        """Return a matplotlib Figure visualising this object."""
        ...


# ------------------------------------------------------------------
# Plot functions
# ------------------------------------------------------------------


def plot_sweep(result: SweepResult, **kwargs: Any) -> Figure:
    """Plot a 1-D sweep result.

    Parameters
    ----------
    result:
        A :class:`SweepResult` from a 1-D parameter sweep.
    **kwargs:
        Passed to ``ax.plot()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    ax.plot(result.values, result.metric_values, "o-", **kwargs)
    ax.set_xlabel(result.param_name)
    ax.set_ylabel(result.metric_name)
    ax.set_title(f"{result.metric_name} vs {result.param_name}")
    ax.grid(True, alpha=0.3)
    return cast("Figure", fig)


def plot_sweep_2d(result: Sweep2DResult, **kwargs: Any) -> Figure:
    """Plot a 2-D sweep result as a filled contour.

    Parameters
    ----------
    result:
        A :class:`Sweep2DResult` from a 2-D parameter sweep.
    **kwargs:
        Passed to ``ax.contourf()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    v1_grid, v2_grid = np.meshgrid(result.values1, result.values2, indexing="ij")
    cs = ax.contourf(v1_grid, v2_grid, result.grid, **kwargs)
    fig.colorbar(cs, ax=ax, label=result.metric_name)
    ax.set_xlabel(result.param1_name)
    ax.set_ylabel(result.param2_name)
    ax.set_title(f"{result.metric_name}")
    return cast("Figure", fig)


def plot_noise_budget(
    noise_terms: tuple[Any, ...] | list[Any],
    **kwargs: Any,
) -> Figure:
    """Plot a noise budget as a horizontal bar chart.

    Parameters
    ----------
    noise_terms:
        Tuple of :class:`NoiseTerm` objects.
    **kwargs:
        Passed to ``ax.barh()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    names = [nt.name for nt in noise_terms]
    values = [nt.value_e for nt in noise_terms]
    # Sort by magnitude
    order = np.argsort(values)[::-1]
    names_sorted = [names[i] for i in order]
    values_sorted = [values[i] for i in order]
    ax.barh(names_sorted, values_sorted, **kwargs)
    ax.set_xlabel("Noise (e- RMS)")
    ax.set_title("Noise Budget")
    ax.invert_yaxis()
    return cast("Figure", fig)


def plot_noise_pie(
    noise_terms: tuple[Any, ...] | list[Any],
    **kwargs: Any,
) -> Figure:
    """Plot the noise-term contributions as a **variance-weighted** pie chart.

    Presentation choice (physics-driven, documented): the total noise adds in
    **quadrature** — ``σ_total² = Σ σ_i²`` — so the meaningful "share of the
    noise" for a term is its fraction of the **variance** (σ_i²), not of σ_i.
    A pie of the σ_i themselves would not sum to the total noise (RMS values
    do not add linearly) and would visually overstate the small terms. The
    slices are therefore proportional to each term's **variance** (σ_i²), so
    they sum to 100 % of the noise **power**. Each wedge is labelled with the
    term name, its σ_i in **e- RMS** (unit on the label, R-UNITS), and its % of
    the total variance. Zero terms are omitted (they carry no power).

    This is the pie sibling of :func:`plot_noise_budget` (same
    ``result.noise_terms`` data, a different mark): the bar shows the absolute
    σ_i in e- RMS; the pie shows the variance share.

    Parameters
    ----------
    noise_terms:
        Tuple of :class:`~radiant.core.radiometry.NoiseTerm` objects.
    **kwargs:
        Passed to ``ax.pie()``.

    Returns
    -------
    Figure
        A matplotlib Figure.

    Raises
    ------
    ApiValidationError
        When every term's σ is zero (the variance shares are undefined — there
        is no noise power to apportion).
    """
    from radiant.api.errors import ApiValidationError

    plt = _require_matplotlib()
    kept = [(nt.name, float(nt.value_e)) for nt in noise_terms if float(nt.value_e) > 0.0]
    if not kept:
        raise ApiValidationError(
            "No non-zero noise terms to plot as a pie — every term's σ is zero, "
            "so the noise variance has no share to apportion."
        )
    # Sort by variance descending so the dominant contributor leads the wedges.
    kept.sort(key=lambda item: item[1], reverse=True)
    names = [name for name, _ in kept]
    sigmas = [sigma for _, sigma in kept]
    variances = [sigma * sigma for sigma in sigmas]
    total_var = float(sum(variances))
    labels = [
        f"{name}\n{sigma:.3g} e- RMS ({100.0 * var / total_var:.1f}%)"
        for name, sigma, var in zip(names, sigmas, variances, strict=True)
    ]
    fig, ax = plt.subplots(constrained_layout=True)
    ax.pie(variances, labels=labels, **kwargs)  # slices ∝ σ_i² (noise power)
    ax.set_aspect("equal")
    ax.set_title("Noise budget — share of variance (σ²; total noise power)")
    return cast("Figure", fig)


def plot_mtf_budget(budget: Any, **kwargs: Any) -> Figure:
    """Plot per-contributor MTF at Nyquist as a grouped bar chart (Gap 19).

    Parameters
    ----------
    budget:
        :class:`~radiant.performance.mtf_budget.MTFBudgetResult`.
    **kwargs:
        Passed to ``ax.barh()``.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    bases = sorted(
        {n[:-2] for n in budget.per_term_at_nyquist if n.endswith(("_x", "_y"))},
        key=lambda b: budget.per_term_at_nyquist.get(f"{b}_x", 1.0),
    )
    y = np.arange(len(bases))
    mx = [budget.per_term_at_nyquist.get(f"{b}_x", np.nan) for b in bases]
    my = [budget.per_term_at_nyquist.get(f"{b}_y", np.nan) for b in bases]
    ax.barh(y - 0.2, mx, height=0.4, label="x", **kwargs)
    ax.barh(y + 0.2, my, height=0.4, label="y", **kwargs)
    ax.set_yticks(y)
    ax.set_yticklabels(bases)
    ax.axvline(budget.system_mtf_at_nyquist_x, ls="--", lw=1, label="system (x)")
    ax.set_xlabel("MTF at Nyquist")
    ax.set_title("MTF budget at Nyquist")
    ax.legend()
    ax.invert_yaxis()
    return cast("Figure", fig)


def plot_psf(
    psf: EffectivePSF,
    *,
    pixel_grid: bool = False,
    pixel_grid_span: int = 16,
    **kwargs: Any,
) -> Figure:
    """Plot an EffectivePSF as a 2D image with log scale.

    Parameters
    ----------
    psf:
        An :class:`EffectivePSF` object.
    pixel_grid:
        When ``True``, overlay the **detector pixel grid** — pixel-boundary
        gridlines at the detector pixel pitch (``psf.pixel_pitch_m``) over the
        PSF (sampled at ``psf.sample_spacing_m``), so the viewer sees how the
        PSF spreads across detector pixels. The view is cropped to a window of
        ``pixel_grid_span`` detector pixels centred on the PSF peak (the full
        array spans many pixels — a whole-array grid would be an unreadable
        mesh), and the title carries the pitch (with units). Default ``False``
        leaves the plot byte-for-byte the shipped image.
    pixel_grid_span:
        Width of the cropped window, in detector pixels, when ``pixel_grid`` is
        set. Ignored otherwise.
    **kwargs:
        Passed to ``ax.imshow()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    from matplotlib.colors import LogNorm

    fig, ax = plt.subplots(constrained_layout=True)
    data = psf.data
    vmin = data[data > 0].min() if np.any(data > 0) else 1e-10
    defaults: dict[str, Any] = {
        "cmap": "viridis",
        "norm": LogNorm(vmin=vmin, vmax=data.max()),
        "origin": "lower",
    }
    defaults.update(kwargs)
    im = ax.imshow(data, **defaults)
    fig.colorbar(im, ax=ax, label="PSF intensity")
    if pixel_grid:
        pitch_um = psf.pixel_pitch_m * 1e6
        ax.set_title(f"Effective PSF · detector pixel grid ({pitch_um:.1f} µm pitch)")
        ax.set_xlabel("x (PSF samples)")
        ax.set_ylabel("y (PSF samples)")
        _overlay_pixel_grid(ax, psf, pixel_grid_span)
    else:
        ax.set_title("Effective PSF")
        ax.set_xlabel("x (pixels)")
        ax.set_ylabel("y (pixels)")
    return cast("Figure", fig)


def _overlay_pixel_grid(ax: Any, psf: EffectivePSF, span_pixels: int) -> None:
    """Draw detector pixel-boundary gridlines over a PSF image and crop to the core.

    The PSF array is sampled at ``psf.sample_spacing_m``; one detector pixel
    spans ``psf.pixel_pitch_m / sample_spacing_m`` samples. Boundaries straddle
    the centre sample so the central detector pixel is centred on the PSF peak.
    The axes are cropped to ``span_pixels`` detector pixels so the grid is a
    readable mesh over the concentrated PSF rather than hundreds of lines across
    the (largely empty) full array.
    """
    dx = psf.sample_spacing_m
    pitch = psf.pixel_pitch_m
    n = psf.data.shape[0]
    if dx <= 0.0 or pitch <= 0.0:
        return
    samples_per_pixel = pitch / dx
    center = (n - 1) / 2.0
    half_pixels = max(1, span_pixels // 2)
    offsets = [(k + 0.5) * samples_per_pixel for k in range(half_pixels)]
    positions = [center - off for off in offsets] + [center + off for off in offsets]
    for pos in positions:
        if -0.5 <= pos <= n - 0.5:
            ax.axvline(pos, color="white", lw=0.5, alpha=0.5)
            ax.axhline(pos, color="white", lw=0.5, alpha=0.5)
    lo = max(-0.5, center - half_pixels * samples_per_pixel)
    hi = min(n - 0.5, center + half_pixels * samples_per_pixel)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)


def _pupil_axes_labels(ax: Any, extent_m: float | None) -> dict[str, Any]:
    """Label pupil-plane axes; return imshow kwargs carrying the extent.

    When the physical pupil diameter ``extent_m`` [m] is known the map is
    drawn in metres across the pupil plane; otherwise axes fall back to
    sample indices (labelled as such).
    """
    if extent_m is not None:
        radius = 0.5 * extent_m
        ax.set_xlabel("pupil x (m)")
        ax.set_ylabel("pupil y (m)")
        return {"extent": (-radius, radius, -radius, radius)}
    ax.set_xlabel("pupil x (samples)")
    ax.set_ylabel("pupil y (samples)")
    return {}


def plot_pupil_amplitude(
    amplitude: npt.NDArray[np.float64],
    extent_m: float | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot the pupil amplitude (apodization) map as a 2D image.

    The amplitude is the dimensionless transmission across the pupil —
    1.0 in the clear aperture, 0.0 under the central obscuration / spider
    vanes, or the supplied measured mask. Mirrors :func:`plot_psf`.

    Parameters
    ----------
    amplitude:
        Pupil amplitude mask, shape ``(npix, npix)``.
    extent_m:
        Physical pupil diameter [m] for axis scaling. ``None`` labels axes
        in sample indices.
    **kwargs:
        Passed to ``ax.imshow()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()

    fig, ax = plt.subplots(constrained_layout=True)
    defaults: dict[str, Any] = {
        "cmap": "viridis",
        "origin": "lower",
        "vmin": 0.0,
        "vmax": max(1.0, float(np.max(amplitude)) if amplitude.size else 1.0),
    }
    defaults.update(_pupil_axes_labels(ax, extent_m))
    defaults.update(kwargs)
    im = ax.imshow(amplitude, **defaults)
    fig.colorbar(im, ax=ax, label="transmission (dimensionless)")
    ax.set_title("Pupil amplitude (apodization)")
    return cast("Figure", fig)


def plot_pupil_phase(
    phase_waves: npt.NDArray[np.float64],
    extent_m: float | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot the pupil wavefront-error (phase) map as a 2D image.

    The phase is the wavefront error across the pupil in **waves** (WFE),
    zero outside the clear aperture. A symmetric diverging colormap centres
    zero WFE, so an unaberrated pupil renders flat. Mirrors :func:`plot_psf`.

    Parameters
    ----------
    phase_waves:
        Pupil wavefront error in waves, shape ``(npix, npix)``.
    extent_m:
        Physical pupil diameter [m] for axis scaling. ``None`` labels axes
        in sample indices.
    **kwargs:
        Passed to ``ax.imshow()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()

    fig, ax = plt.subplots(constrained_layout=True)
    amax = float(np.max(np.abs(phase_waves))) if phase_waves.size else 0.0
    if amax == 0.0:
        amax = 1.0  # flat (zero-WFE) map — avoid a degenerate colour range
    defaults: dict[str, Any] = {
        "cmap": "RdBu_r",
        "origin": "lower",
        "vmin": -amax,
        "vmax": amax,
    }
    defaults.update(_pupil_axes_labels(ax, extent_m))
    defaults.update(kwargs)
    im = ax.imshow(phase_waves, **defaults)
    fig.colorbar(im, ax=ax, label="wavefront error (waves)")
    ax.set_title("Pupil wavefront error")
    return cast("Figure", fig)


def plot_mtf_terms(
    mtf_terms: dict[str, npt.NDArray[np.float64]],
    spatial_freq: npt.NDArray[np.float64] | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot all MTF terms on a single axis.

    Parameters
    ----------
    mtf_terms:
        Dict mapping term name → MTF array.
    spatial_freq:
        Spatial frequency axis (cycles/mrad). If None, uses array index.
    **kwargs:
        Passed to ``ax.plot()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)

    def _x_axis(arr: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        if spatial_freq is not None:
            return spatial_freq
        return np.arange(len(arr), dtype=np.float64)

    # Group per contributor, splitting the ``_x`` / ``_y`` axis suffix so a contributor's
    # along-track and cross-track roll-off become one legend entry when they coincide
    # (CU-117). This halves a ~16-line overlay (8 contributors × x/y) to ~8 labels without
    # dropping any curve: identical x/y are drawn once (one representative line + one
    # label); x/y that visibly differ keep both lines and both labels, so the overlay stays
    # honest (a real anisotropy is never hidden behind a single entry).
    grouped: dict[str, dict[str, npt.NDArray[np.float64]]] = {}
    order: list[str] = []
    for name in sorted(mtf_terms):
        if name.endswith(("_x", "_y")):
            base, axis = name[:-2], name[-1]
        else:
            base, axis = name, ""
        if base not in grouped:
            grouped[base] = {}
            order.append(base)
        grouped[base][axis] = mtf_terms[name]

    n_labels = 0
    for base in order:
        axes = grouped[base]
        xa, ya = axes.get("x"), axes.get("y")
        if xa is not None and ya is not None and np.allclose(xa, ya, atol=1e-9):
            # Isotropic contributor: one curve represents both axes — a single label.
            ax.plot(_x_axis(xa), xa, label=base, **kwargs)
            n_labels += 1
        elif xa is not None and ya is not None:
            # Anisotropic: keep both curves and both labels (honest — nothing merged away).
            ax.plot(_x_axis(xa), xa, label=f"{base} (x)", **kwargs)
            ax.plot(_x_axis(ya), ya, label=f"{base} (y)", **kwargs)
            n_labels += 2
        else:
            # A lone axis or an unsuffixed term (e.g. "system").
            for suffix, arr in axes.items():
                label = base if not suffix else f"{base} ({suffix})"
                ax.plot(_x_axis(arr), arr, label=label, **kwargs)
                n_labels += 1

    ax.set_xlabel("Spatial frequency (cycles/mrad)" if spatial_freq is not None else "Index")
    ax.set_ylabel("MTF")
    ax.set_title("MTF Budget")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    # Place the legend BELOW the axes in a compact multi-column block (constrained_layout
    # reserves the strip, so it re-fits on every resize). Unlike the previous inside
    # upper-right legend, a below-axes legend never blankets the curves in the GUI's narrow
    # embedded pane (CU-117); unlike an outside-right legend (tried and rejected) it costs
    # height, not width, so the plot never collapses to a sliver. Columns scale with the
    # (already halved) label count to keep the block a few rows tall.
    ncol = min(3, max(1, (n_labels + 3) // 4))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.30),  # clears the x-axis label; constrained_layout reserves it
        ncol=ncol,
        fontsize="small",
        frameon=False,
    )
    return cast("Figure", fig)


def plot_spectral(
    wavelength_um: npt.NDArray[np.float64],
    radiance: npt.NDArray[np.float64],
    *,
    title: str = "Spectral Radiance",
    ylabel: str = "Radiance (W/m\u00b2/sr/\u00b5m)",
    **kwargs: Any,
) -> Figure:
    """Plot spectral radiance vs wavelength.

    Parameters
    ----------
    wavelength_um:
        Wavelength array [\u00b5m].
    radiance:
        Spectral radiance array.
    title:
        Plot title.
    ylabel:
        Y-axis label.
    **kwargs:
        Passed to ``ax.plot()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    ax.plot(wavelength_um, radiance, **kwargs)
    ax.set_xlabel("Wavelength (\u00b5m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    return cast("Figure", fig)


def plot_spectral_multi(
    wavelength_um: npt.NDArray[np.float64],
    series: dict[str, npt.NDArray[np.float64]],
    *,
    title: str = "Spectral Radiance",
    ylabel: str = "Radiance (W/m\u00b2/sr/\u00b5m)",
    **kwargs: Any,
) -> Figure:
    """Plot several spectral curves that share one wavelength grid.

    Used for the Source default view (target + background at-aperture
    radiance), where every curve carries the same units and wavelength
    axis so a single y-axis is unambiguous.

    Parameters
    ----------
    wavelength_um:
        Shared 1-D wavelength grid [\u00b5m].
    series:
        Mapping ``label -> y(\u03bb)``; each array aligns with ``wavelength_um``.
    title:
        Plot title.
    ylabel:
        Y-axis label (must carry units \u2014 every curve shares them).
    **kwargs:
        Passed to ``ax.plot()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    for label, y in series.items():
        ax.plot(wavelength_um, y, label=label, **kwargs)
    ax.set_xlabel("Wavelength (\u00b5m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    if len(series) > 1:
        ax.legend(fontsize="small")
    return cast("Figure", fig)


def plot_optical_throughput(
    wavelength_um: npt.NDArray[np.float64],
    tau_opt: npt.NDArray[np.float64],
    *,
    title: str = "System optical throughput",
    **kwargs: Any,
) -> Figure:
    """Plot the assembled system optical throughput τ_opt(λ).

    Draws the dimensionless system transmission (product of every element's
    net throughput along the signal path) against wavelength. Mirrors
    :func:`plot_spectral`; the y-axis is bounded to [0, 1.05] and labelled
    ``τ_opt (dimensionless)`` (R-UNITS, short-label clip fix).

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm].
    tau_opt:
        System optical throughput τ_opt(λ) [dimensionless, in [0, 1]].
    title:
        Plot title.
    **kwargs:
        Passed to ``ax.plot()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    ax.plot(wavelength_um, tau_opt, **kwargs)
    ax.set_xlabel("Wavelength (µm)")
    ax.set_ylabel("τ_opt (dimensionless)")
    ax.set_title(title)
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    return cast("Figure", fig)


def plot_coating_spectra(
    series: dict[str, tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    *,
    title: str = "Per-element coating spectra",
    **kwargs: Any,
) -> Figure:
    """Plot per-element reflectance / transmission / emissivity curves.

    Each curve is a dimensionless spectral quantity (R, T, or ε) for one
    optical element; every curve shares the same y-axis (all are in [0, 1])
    but may carry its **own** wavelength grid, so each entry supplies its own
    ``(wavelength_um, values)`` pair. Isolates each element's coating
    contribution to (or limit on) throughput across the band.

    Parameters
    ----------
    series:
        Mapping ``label -> (wavelength_um [µm], values [dimensionless])``.
        Labels are typically ``"<element> R"`` / ``"<element> T"`` /
        ``"<element> ε"``.
    title:
        Plot title.
    **kwargs:
        Passed to ``ax.plot()`` for every curve.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax = plt.subplots(constrained_layout=True)
    for label, (wavelength_um, values) in series.items():
        ax.plot(wavelength_um, values, label=label, **kwargs)
    ax.set_xlabel("Wavelength (µm)")
    ax.set_ylabel("R / T / ε (dimensionless)")
    ax.set_title(title)
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    if series:
        # A per-element × per-quantity overlay can grow large; a compact
        # below-axes multi-column legend keeps the curves unobscured in the
        # narrow embedded GUI pane (mirrors plot_mtf_terms, CU-117).
        ncol = min(3, max(1, (len(series) + 3) // 4))
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.30),
            ncol=ncol,
            fontsize="small",
            frameon=False,
        )
    return cast("Figure", fig)


def plot_atmosphere_spectral(
    wavelength_um: npt.NDArray[np.float64],
    tau_atm: npt.NDArray[np.float64],
    l_path: npt.NDArray[np.float64],
    *,
    title: str = "Atmospheric Transmittance and Path Radiance",
    **kwargs: Any,
) -> Figure:
    """Plot atmospheric transmittance and path radiance vs wavelength.

    Transmittance (dimensionless, [0, 1]) and path radiance
    (W/m\u00b2/sr/\u00b5m) carry different units, so they render on twin y-axes
    that are each unit-labelled (R-UNITS).

    Parameters
    ----------
    wavelength_um:
        Shared 1-D wavelength grid [\u00b5m].
    tau_atm:
        Atmospheric transmittance \u03c4_atm(\u03bb) [dimensionless].
    l_path:
        Atmospheric path radiance L_path(\u03bb) [W/m\u00b2/sr/\u00b5m].
    title:
        Plot title.
    **kwargs:
        Passed to ``ax.plot()`` for both curves.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    fig, ax_tau = plt.subplots(constrained_layout=True)
    (line_tau,) = ax_tau.plot(wavelength_um, tau_atm, color="C0", label="\u03c4_atm", **kwargs)
    ax_tau.set_xlabel("Wavelength (\u00b5m)")
    ax_tau.set_ylabel("\u03c4_atm (dimensionless)", color="C0")
    ax_tau.tick_params(axis="y", labelcolor="C0")
    ax_tau.set_ylim(0.0, 1.05)
    ax_tau.grid(True, alpha=0.3)

    ax_lp = ax_tau.twinx()
    (line_lp,) = ax_lp.plot(wavelength_um, l_path, color="C1", label="L_path", **kwargs)
    ax_lp.set_ylabel("L_path (W/m\u00b2/sr/\u00b5m)", color="C1")
    ax_lp.tick_params(axis="y", labelcolor="C1")

    ax_tau.set_title(title)
    ax_tau.legend([line_tau, line_lp], ["\u03c4_atm", "L_path"], fontsize="small", loc="best")
    return cast("Figure", fig)
