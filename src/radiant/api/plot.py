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
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Final, Protocol, cast, runtime_checkable

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api.sweep import Sweep2DResult, SweepResult
    from radiant.optics.psf.effective import EffectivePSF

logger = logging.getLogger(__name__)

# Default plotted window for a PSF, in detector pixels (±6). The PSF array covers
# far more focal plane than the PSF occupies, so an uncropped render is a bright
# dot in an empty field (owner walkthrough item 14: "zoomed into like +/-5 or 10
# pixel widths"). Presentation-only: it changes no computed value.
_DEFAULT_PSF_SPAN_PIXELS: Final[int] = 12

# Fraction of a convolution kernel's volume the plotted crop must retain. A kernel
# is stored at whatever grid its construction needed, not at its support, so this
# is what turns "a dot in a 1023² field" into a readable shape. Presentation-only.
_KERNEL_SUPPORT_FRACTION: Final[float] = 0.999

# Smallest variance share that still earns an on-wedge label in the noise pie.
# Below ~3 % a wedge subtends under 11°, so its label collides with its
# neighbours' — those terms are carried by the legend instead (see
# :func:`plot_noise_pie`). Presentation-only: it changes no computed value.
_PIE_LABEL_MIN_SHARE: Final[float] = 0.03

# Dark-theme matplotlib rcParams — chrome only (background, axes, text, ticks, grid).
# Data-series colours keep matplotlib's cycle, which reads on both backgrounds.
_DARK_RCPARAMS: dict[str, Any] = {
    "figure.facecolor": "#1e1e1e",
    "savefig.facecolor": "#1e1e1e",
    "axes.facecolor": "#252526",
    "axes.edgecolor": "#8a8a8a",
    "axes.labelcolor": "#e0e0e0",
    "axes.titlecolor": "#e0e0e0",
    "text.color": "#e0e0e0",
    "xtick.color": "#c0c0c0",
    "ytick.color": "#c0c0c0",
    "grid.color": "#3a3a3a",
    "legend.facecolor": "#252526",
    "legend.edgecolor": "#3a3a3a",
}


@contextmanager
def plot_theme(dark: bool = False) -> Iterator[None]:
    """Context manager applying a dark (or light) matplotlib chrome theme (CU-139).

    The public seam through which a GUI/notebook can request a dark-styled
    ``result.plot.*`` figure without the GUI restyling the figure itself (keeps
    one action ↔ one API call). Wrap figure production::

        with plot_theme(dark=True):
            fig = result.plot.mtf()

    ``dark=False`` is a no-op (matplotlib's default light chrome). Only figure
    chrome (background, axes, text, ticks, grid) is themed; data-series colours are
    unchanged, so the figures read on either background.
    """
    if not dark:
        yield
        return
    plt = _require_matplotlib()
    with plt.rc_context(_DARK_RCPARAMS):
        yield


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

    Label placement
    ---------------
    A realistic budget is usually dominated by one term — shot noise at 100.0 %
    with every other term rounding to 0.0 % is the common case, not the corner
    case. Those sub-percent wedges subtend almost no angle, so matplotlib stacks
    their labels on top of each other at the same radius and the text becomes
    unreadable. Only wedges holding at least :data:`_PIE_LABEL_MIN_SHARE` of the
    variance are therefore labelled **on the wedge**; a legend carries **every**
    term (including the tiny ones) with the same name / σ_i / % detail, so no
    information is lost — it just moves somewhere it fits.

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
    # Sub-threshold wedges get no on-wedge text (their labels would overlap);
    # the legend below still names every one of them.
    wedge_labels = [
        label if var / total_var >= _PIE_LABEL_MIN_SHARE else ""
        for label, var in zip(labels, variances, strict=True)
    ]
    fig, ax = plt.subplots(constrained_layout=True)
    wedges, _ = ax.pie(variances, labels=wedge_labels, **kwargs)  # slices ∝ σ_i² (noise power)
    ax.set_aspect("equal")
    # One legend row per term, dominant first — the tiny terms are readable here
    # even when they are invisible on the wedge. Newlines suit the wedge labels,
    # not a legend row, so the same fields are joined inline.
    ax.legend(
        wedges,
        [label.replace("\n", " — ") for label in labels],
        title="σ per term (e- RMS) · share of σ²",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize="small",
        frameon=False,
    )
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
    span_pixels: int = _DEFAULT_PSF_SPAN_PIXELS,
    pixel_outline: bool = True,
    pixel_grid_span: int | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot an EffectivePSF as a 2D image with log scale, cropped to the PSF core.

    Parameters
    ----------
    psf:
        An :class:`EffectivePSF` object.
    pixel_grid:
        When ``True``, overlay the full **detector pixel grid** — pixel-boundary
        gridlines at the detector pixel pitch (``psf.pixel_pitch_m``) over the
        PSF (sampled at ``psf.sample_spacing_m``), so the viewer sees how the
        PSF spreads across many detector pixels. Default ``False`` draws only the
        single-pixel outline described below.
    span_pixels:
        Width of the plotted window in **detector pixels**, centred on the PSF
        peak. The PSF array spans far more of the focal plane than the PSF
        occupies — a 1024² grid at ~8 samples per pixel is ±60 pixels of mostly
        empty field — so the core rendered full-array is a small bright dot
        (owner walkthrough item 14: "PSF plot should be zoomed into like +/-5 or
        10 pixel widths"). Applies whether or not *pixel_grid* is set.
    pixel_outline:
        When ``True`` (default), outline the **one** detector pixel centred on the
        PSF peak, so the PSF is always read against the pixel that samples it
        (owner walkthrough item 20: "we should also see the outline of the
        detector pixel on the PSF plot"). Suppressed automatically when
        *pixel_grid* is set, since the grid already draws that boundary.
    pixel_grid_span:
        Deprecated alias for *span_pixels*, kept so existing callers keep working.
        When given it overrides *span_pixels* and emits a
        :class:`DeprecationWarning`.
    **kwargs:
        Passed to ``ax.imshow()``.

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    plt = _require_matplotlib()
    from matplotlib.colors import LogNorm

    if pixel_grid_span is not None:
        warnings.warn(
            "plot_psf(pixel_grid_span=...) is deprecated; use span_pixels=... "
            "(it now crops the plain PSF plot too, not only the pixel-grid one).",
            DeprecationWarning,
            stacklevel=2,
        )
        span_pixels = pixel_grid_span

    fig, ax = plt.subplots(constrained_layout=True)
    data = psf.data
    vmin = data[data > 0].min() if np.any(data > 0) else 1e-10
    defaults: dict[str, Any] = {
        "cmap": "viridis",
        "norm": LogNorm(vmin=vmin, vmax=data.max()),
        "origin": "lower",
    }
    defaults.update(kwargs)
    # CU-241: plot on the focal plane in µm, not in raw sample indices. Index axes
    # (500-560 on a 1024 grid) told the reader nothing about the physical size of
    # the blur and forced a mental conversion through the sample spacing; the
    # detector pitch is quoted in µm in the title, so the axes must share its
    # units for the comparison the plot exists to support. Coordinates are
    # measured from the array centre, which is where the PSF core sits.
    extent_um = _psf_extent_um(psf)
    if extent_um is not None:
        defaults.setdefault("extent", extent_um)
    im = ax.imshow(data, **defaults)
    # Colorbar sized so it does not eat a third of a narrow card (CU-241).
    fig.colorbar(im, ax=ax, label="PSF intensity", fraction=0.046, pad=0.04)
    if extent_um is not None:
        ax.set_xlabel("x on focal plane (µm)")
        ax.set_ylabel("y on focal plane (µm)")
    else:
        # Degenerate geometry (no sample spacing / pitch): fall back to the sample
        # grid rather than inventing a physical scale (CU-136).
        ax.set_xlabel("x (PSF samples)")
        ax.set_ylabel("y (PSF samples)")
    pitch_um = psf.pixel_pitch_m * 1e6
    if pixel_grid:
        ax.set_title(f"Effective PSF · detector pixel grid ({pitch_um:.1f} µm pitch)")
        _overlay_pixel_grid(ax, psf, span_pixels)
    else:
        ax.set_title(f"Effective PSF ({pitch_um:.1f} µm pixel outlined)")
        _crop_to_pixels(ax, psf, span_pixels)
        if pixel_outline:
            _overlay_pixel_outline(ax, psf)
    return cast("Figure", fig)


def _psf_um_per_sample(psf: EffectivePSF) -> float | None:
    """Focal-plane µm per PSF sample, or ``None`` for a degenerate grid."""
    dx = float(psf.sample_spacing_m)
    return dx * 1e6 if dx > 0.0 else None


def _psf_sample_to_um(psf: EffectivePSF, sample: float) -> float:
    """Convert a PSF sample coordinate to µm measured from the array centre.

    One transform, used by the image extent and by every overlay, so the
    gridlines and the pixel outline cannot drift off the image they annotate
    (CU-241).
    """
    um = _psf_um_per_sample(psf)
    if um is None:
        return sample
    centre = (psf.data.shape[0] - 1) / 2.0
    return float((sample - centre) * um)


def _psf_extent_um(psf: EffectivePSF) -> tuple[float, float, float, float] | None:
    """``imshow`` extent in focal-plane µm, or ``None`` for a degenerate grid."""
    if _psf_um_per_sample(psf) is None:
        return None
    n = psf.data.shape[0]
    lo = _psf_sample_to_um(psf, -0.5)
    hi = _psf_sample_to_um(psf, n - 0.5)
    return (lo, hi, lo, hi)


def _pixel_geometry(psf: EffectivePSF) -> tuple[float, float, float] | None:
    """``(samples_per_pixel, centre_sample, n_samples)``, or ``None`` if degenerate."""
    dx = psf.sample_spacing_m
    pitch = psf.pixel_pitch_m
    n = psf.data.shape[0]
    if dx <= 0.0 or pitch <= 0.0:
        return None
    return pitch / dx, (n - 1) / 2.0, float(n)


def _crop_to_pixels(ax: Any, psf: EffectivePSF, span_pixels: int) -> None:
    """Limit *ax* to ``span_pixels`` detector pixels centred on the PSF peak."""
    geometry = _pixel_geometry(psf)
    if geometry is None:
        return
    samples_per_pixel, center, n = geometry
    half = max(1, span_pixels // 2) * samples_per_pixel
    lo = _psf_sample_to_um(psf, max(-0.5, center - half))
    hi = _psf_sample_to_um(psf, min(n - 0.5, center + half))
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)


def _overlay_pixel_outline(ax: Any, psf: EffectivePSF) -> None:
    """Outline the single detector pixel centred on the PSF peak.

    Item 20's "outline of the detector pixel": the boundary of the one pixel the
    PSF core lands in, so its spread is always read against the sampling element
    rather than against bare sample indices.
    """
    from matplotlib.patches import Rectangle

    geometry = _pixel_geometry(psf)
    if geometry is None:
        return
    samples_per_pixel, center, _n = geometry
    half = samples_per_pixel / 2.0
    corner = _psf_sample_to_um(psf, center - half)
    side = samples_per_pixel * (_psf_um_per_sample(psf) or 1.0)
    ax.add_patch(
        Rectangle(
            (corner, corner),
            side,
            side,
            fill=False,
            edgecolor="white",
            linewidth=1.2,
            linestyle="--",
        )
    )


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
            pos_um = _psf_sample_to_um(psf, pos)
            ax.axvline(pos_um, color="white", lw=0.5, alpha=0.5)
            ax.axhline(pos_um, color="white", lw=0.5, alpha=0.5)
    lo = _psf_sample_to_um(psf, max(-0.5, center - half_pixels * samples_per_pixel))
    hi = _psf_sample_to_um(psf, min(n - 0.5, center + half_pixels * samples_per_pixel))
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
    nyquist_cycles_per_mrad: float | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot all MTF terms on a single axis.

    Parameters
    ----------
    mtf_terms:
        Dict mapping term name → MTF array.
    spatial_freq:
        Spatial frequency axis (cycles/mrad). If None, uses array index.
    nyquist_cycles_per_mrad:
        Detector Nyquist frequency in the plotted axis' units. When given (and
        an explicit *spatial_freq* axis is in use) it is drawn as a **red dashed
        vertical line** labelled with its value — the sampling limit against
        which every roll-off is read (owner walkthrough item 12). ``None`` omits
        the marker rather than guessing a pitch.
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

    # The detector sampling limit, marked on the axis every roll-off is read against
    # (owner walkthrough item 12). Drawn only with a real frequency axis — on the
    # index fallback the value would land at a meaningless x position.
    if nyquist_cycles_per_mrad is not None and spatial_freq is not None:
        ax.axvline(
            float(nyquist_cycles_per_mrad),
            color="red",
            linestyle="--",
            linewidth=1.2,
            label=f"Nyquist ({nyquist_cycles_per_mrad:.3g} cycles/mrad)",
        )
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


#: Which stage *adds* each PSF convolution kernel (CU-243). The kernel list on an
#: EffectivePSF is the accumulated stack, so a per-stage view that simply enumerates
#: it shows upstream kernels with no owner — correct data reading as a wrong-stage
#: bug. This is a fact about the signal chain, not about any one result, so it is
#: named here rather than discovered: the pixel aperture and charge diffusion are
#: applied by OpticsStage (deliberately front-loaded so Platform's EE_box ensquares a
#: real pixel and Strehl's reference cancels detector terms — Rules 4 and 9), jitter,
#: smear and turbulence by PlatformStage, and IPC by PerformanceStage.
_KERNEL_OWNER_STAGE: dict[str, str] = {
    "optical": "Optics",
    "pixel_aperture": "Optics",
    "charge_diffusion": "Optics",
    "jitter": "Platform",
    "smear": "Platform",
    "turbulence": "Platform",
    "ipc": "Performance",
}


def kernel_owner_stage(name: str) -> str:
    """The stage that applies the kernel called *name* (CU-243); "?" if unknown."""
    return _KERNEL_OWNER_STAGE.get(name, "?")


def plot_psf_kernels(
    psf: EffectivePSF,
    names: tuple[str, ...] | None = None,
    **kwargs: Any,
) -> Figure:
    """Plot the convolution kernels that degraded *psf*, one 2-D map per kernel.

    ``EffectivePSF.convolution_history`` names the degradations that were
    applied; :attr:`EffectivePSF.kernels` carries the arrays themselves, and this
    draws them side by side so the operator can see *what each degradation did*
    rather than only that it happened (owner walkthrough item 15: "show the PSF
    convolution kernels and post convolution PSF"; item 19 uses the same figure
    filtered to the detector terms).

    Each kernel is **cropped to its own support** before drawing. Kernels are
    built at whatever grid size their construction needed — the pixel-aperture
    kernel is a full-PSF-grid array holding an 8-sample box — so drawn at their
    stored extent most of them are a dot in an empty field. The crop keeps the
    smallest centred window holding :data:`_KERNEL_SUPPORT_FRACTION` of the
    kernel's volume, which is what makes the shapes comparable.

    Each kernel is shown on its own linear colour scale — they differ by orders
    of magnitude in peak value (a 3×3 IPC kernel against a broad turbulence one),
    so a shared scale would render all but the narrowest as blank. The extent is
    labelled in **µm on the focal plane** (kernel samples × the PSF's
    ``sample_spacing_m``), which is the physically meaningful axis, and each
    title carries the kernel's width in detector pixels.

    Parameters
    ----------
    psf:
        The :class:`EffectivePSF` whose kernels to draw.
    names:
        Restrict to these kernel names, in this order. ``None`` draws every
        retained kernel in the order it was applied.
    **kwargs:
        Passed to each ``ax.imshow()``.

    Raises
    ------
    ApiValidationError
        When the PSF retains no kernels (nothing was convolved, or it predates
        kernel retention), or when *names* selects none of them.
    """
    from radiant.api.errors import ApiValidationError

    plt = _require_matplotlib()

    kept = [(n, k) for n, k in psf.kernels if names is None or n in names]
    if names is not None:
        order = {n: i for i, n in enumerate(names)}
        kept.sort(key=lambda item: order[item[0]])
    if not kept:
        # CU-243: an empty state must say *why* it is empty, and for whose stage.
        # "Nothing here" beside a PSF that plainly has kernels reads as a bug.
        retained = [n for n, _ in psf.kernels]
        available = ", ".join(f"{n} (added by {kernel_owner_stage(n)})" for n in retained) or "none"
        raise ApiValidationError(
            "No PSF convolution kernels to plot"
            + (f" matching {list(names)}" if names is not None else "")
            + f" — the PSF retains: {available}. A degradation contributes a "
            "kernel only when it is configured non-zero, so an empty view here "
            "means this stage added none to a PSF it inherited already degraded."
        )

    fig, axes = plt.subplots(1, len(kept), constrained_layout=True, squeeze=False)
    spacing_um = psf.sample_spacing_m * 1e6
    for ax, (name, raw) in zip(axes[0], kept, strict=True):
        kernel = _crop_kernel_to_support(raw)
        half_um = kernel.shape[0] / 2.0 * spacing_um
        defaults: dict[str, Any] = {
            "cmap": "magma",
            "origin": "lower",
            "extent": (-half_um, half_um, -half_um, half_um),
        }
        defaults.update(kwargs)
        ax.imshow(kernel, **defaults)
        width_pixels = kernel.shape[0] * psf.sample_spacing_m / psf.pixel_pitch_m
        # CU-243: every kernel names the stage that applied it, so none of them
        # can read as "this stage's" merely by appearing on this stage's tab.
        ax.set_title(
            f"{name} · added by {kernel_owner_stage(name)}\n"
            f"{kernel.shape[0]}² samples ({width_pixels:.2f} px)",
            fontsize="small",
        )
        ax.set_xlabel("x (µm)", fontsize="small")
        ax.set_ylabel("y (µm)", fontsize="small")
        ax.tick_params(labelsize="small")
    return cast("Figure", fig)


def _crop_kernel_to_support(kernel: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """The smallest centred square window of *kernel* holding most of its volume.

    Kernels are stored at their construction grid, which for the pixel-aperture
    term is the whole PSF grid holding a handful of non-zero samples. Plotting
    that verbatim wastes the axes on empty field, so the drawn window is grown
    from the centre until it contains :data:`_KERNEL_SUPPORT_FRACTION` of the
    total. Returns the input unchanged when it is already tight or degenerate.
    """
    n = kernel.shape[0]
    total = float(kernel.sum())
    if n < 5 or total <= 0.0:
        return kernel
    center = n // 2
    target = _KERNEL_SUPPORT_FRACTION * total
    for half in range(1, center + 1):
        window = kernel[center - half : center + half + 1, center - half : center + half + 1]
        if float(window.sum()) >= target:
            # One sample of margin so the support is not flush against the edge.
            pad = min(half + 1, center)
            return kernel[center - pad : center + pad + 1, center - pad : center + pad + 1]
    return kernel
