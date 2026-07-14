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


def plot_psf(psf: EffectivePSF, **kwargs: Any) -> Figure:
    """Plot an EffectivePSF as a 2D image with log scale.

    Parameters
    ----------
    psf:
        An :class:`EffectivePSF` object.
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
    ax.set_title("Effective PSF")
    ax.set_xlabel("x (pixels)")
    ax.set_ylabel("y (pixels)")
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
    ax_tau.set_ylabel("Transmittance \u03c4_atm (dimensionless)", color="C0")
    ax_tau.tick_params(axis="y", labelcolor="C0")
    ax_tau.set_ylim(0.0, 1.05)
    ax_tau.grid(True, alpha=0.3)

    ax_lp = ax_tau.twinx()
    (line_lp,) = ax_lp.plot(wavelength_um, l_path, color="C1", label="L_path", **kwargs)
    ax_lp.set_ylabel("Path radiance L_path (W/m\u00b2/sr/\u00b5m)", color="C1")
    ax_lp.tick_params(axis="y", labelcolor="C1")

    ax_tau.set_title(title)
    ax_tau.legend([line_tau, line_lp], ["\u03c4_atm", "L_path"], fontsize="small", loc="best")
    return cast("Figure", fig)
