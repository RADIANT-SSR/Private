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
    fig, ax = plt.subplots()
    ax.plot(result.values, result.metric_values, "o-", **kwargs)
    ax.set_xlabel(result.param_name)
    ax.set_ylabel(result.metric_name)
    ax.set_title(f"{result.metric_name} vs {result.param_name}")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
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
    fig, ax = plt.subplots()
    v1_grid, v2_grid = np.meshgrid(result.values1, result.values2, indexing="ij")
    cs = ax.contourf(v1_grid, v2_grid, result.grid, **kwargs)
    fig.colorbar(cs, ax=ax, label=result.metric_name)
    ax.set_xlabel(result.param1_name)
    ax.set_ylabel(result.param2_name)
    ax.set_title(f"{result.metric_name}")
    fig.tight_layout()
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
    fig, ax = plt.subplots()
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
    fig.tight_layout()
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

    fig, ax = plt.subplots()
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
    fig.tight_layout()
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
    fig, ax = plt.subplots()
    for name, mtf_arr in sorted(mtf_terms.items()):
        x = spatial_freq if spatial_freq is not None else np.arange(len(mtf_arr))
        ax.plot(x, mtf_arr, label=name, **kwargs)
    ax.set_xlabel("Spatial frequency (cycles/mrad)" if spatial_freq is not None else "Index")
    ax.set_ylabel("MTF")
    ax.set_title("MTF Budget")
    ax.legend(fontsize="small")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
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
    fig, ax = plt.subplots()
    ax.plot(wavelength_um, radiance, **kwargs)
    ax.set_xlabel("Wavelength (\u00b5m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return cast("Figure", fig)
