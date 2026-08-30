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

import functools
import logging
import textwrap
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Final, ParamSpec, Protocol, TypeVar, cast, runtime_checkable

import numpy as np
import numpy.typing as npt

from radiant.api import plot_style

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api.sweep import Sweep2DResult, SweepResult
    from radiant.optics.psf.effective import EffectivePSF

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _styled(func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Run *func* under the RADIANT house style (owner ruling 2026-08-03).

    Wraps the whole function body — not just figure creation — in an
    ``rc_context`` built from :mod:`radiant.api.plot_style` for the active
    theme variant, so every artist the function adds (including ones that read
    ``rcParams`` mid-body) resolves against the styled values. Applied to every
    public plot builder; :func:`plot_theme` selects the light/dark variant.
    """

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        plt = _require_matplotlib()
        with plt.rc_context(plot_style.rcparams()):
            return func(*args, **kwargs)

    return wrapper


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

# Radial position of an on-wedge pie label, as a fraction of the pie radius. Inside the
# rim (< 1.0), so a wide label cannot run off the card edge — see :func:`plot_noise_pie`.
_PIE_LABEL_DISTANCE: Final[float] = 0.62

# Colorbar geometry for every 2-D map (PSF, pupil amplitude, pupil WFE). matplotlib's
# default steals ~15 % of the axes width for the bar plus its pad, which at the card
# sizes the GUI actually renders (a ~200-400 px wide plot column) left the bar wider
# than the useful part of the image and its tick labels crowding the title
# (CU-241 defects 2-3). ``fraction``/``pad`` are documented matplotlib axes-relative
# quantities, so one pair of numbers governs every map at every card size, and the
# bar shrinks with the aspect-locked image instead of spanning the whole figure.
# Presentation-only: changes no computed value.
_MAP_COLORBAR: Final[dict[str, float]] = {"fraction": 0.046, "pad": 0.04}

# Characters per line before an axes title is wrapped. A one-line title is laid out at
# its natural width; matplotlib does not shrink or wrap it, so a title longer than the
# figure is simply clipped at both canvas edges — the "SF · detector pixel grid (18.0 µ"
# symptom (CU-241). Wrapping trades height (which constrained layout redistributes) for
# width (which it cannot). 34 characters is about what a 300 px-wide card holds at the
# default title size. Presentation-only.
_TITLE_WRAP_CHARS: Final[int] = 34


def _wrapped_title(text: str) -> str:
    """Soft-wrap *text* to :data:`_TITLE_WRAP_CHARS` per line for use as an axes title.

    Existing newlines are honoured as hard breaks, so a title that already carries its
    own two-line structure keeps it.
    """
    lines: list[str] = []
    for hard_line in text.split("\n"):
        lines.extend(textwrap.wrap(hard_line, width=_TITLE_WRAP_CHARS) or [""])
    return "\n".join(lines)


@contextmanager
def plot_theme(dark: bool = False) -> Iterator[None]:
    """Context manager selecting the light or dark RADIANT plot theme (CU-139).

    The public seam through which a GUI/notebook selects the theme variant for
    ``result.plot.*`` figures (keeps one action ↔ one API call)::

        with plot_theme(dark=True):
            fig = result.plot.mtf()

    Since the 2026-08-03 owner ruling reversing the old "figures are not
    restyled" stance (arch doc §4.4), **both** variants are fully styled from
    the token-derived house style in :mod:`radiant.api.plot_style` — surfaces,
    fonts, grid, spines, and the CVD-validated series palette. ``dark=False``
    is therefore no longer a no-op: it applies the light variant, which is also
    what every ``result.plot.*`` call uses outside any context. The manager
    additionally applies the style to the surrounding ``rcParams`` context so
    figures built directly with matplotlib inside the ``with`` block (GUI
    dialogs, user scripts) inherit the same chrome.
    """
    token = plot_style.set_dark(dark)
    try:
        plt = _require_matplotlib()
        with plt.rc_context(plot_style.rcparams(dark)):
            yield
    finally:
        plot_style.reset_dark(token)


def _backend_already_selected(mpl: Any) -> bool:
    """Whether the host process has already chosen a matplotlib backend (CU-287).

    Answered **without** triggering matplotlib's auto-selection, so merely asking the
    question never selects a backend. ``get_backend(auto_select=False)`` is the
    supported spelling from matplotlib 3.10; on the 3.8/3.9 floor the pin still
    allows, an unselected backend is a private sentinel object rather than a string,
    and reading it through :meth:`dict.__getitem__` bypasses ``RcParams``'
    resolve-on-access.
    """
    try:
        return bool(mpl.get_backend(auto_select=False))
    except TypeError:  # matplotlib < 3.10 — no auto_select keyword
        return isinstance(dict.__getitem__(mpl.rcParams, "backend"), str)


def _require_matplotlib() -> Any:
    """Import and return matplotlib.pyplot, raising a helpful error if missing.

    Forces the non-interactive ``Agg`` backend **only when the host process has not
    already chosen one** (CU-287). RADIANT builds every figure pyplot-free and never
    shows one (see :func:`_subplots`), so the backend is RADIANT's business only to
    the extent of not blowing up headless: with nothing selected — a script, a bare
    CI runner — Agg is still forced, exactly as before. What no longer happens is a
    library call reconfiguring an embedder that *did* choose: a Jupyter session
    running ``%matplotlib qt``, or a Qt GUI, used to have its backend silently
    switched to Agg by the first ``result.plot.*`` call.
    """
    try:
        import matplotlib

        if not _backend_already_selected(matplotlib):
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError:
        raise ImportError(
            "matplotlib is required for plotting but is not installed.\n"
            "Install it with: pip install matplotlib"
        ) from None


def _subplots(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
    """Create a **pyplot-free** constrained-layout figure and its axes (CU-116).

    Equivalent to ``plt.subplots(constrained_layout=True, *args, **kwargs)`` except
    that the figure is **not registered with pyplot's global figure manager**
    (``Gcf``). RADIANT's figures are consumed by a caller that owns them — the GUI
    embeds them in its own ``FigureCanvasQTAgg``, a script saves or displays them —
    so pyplot's process-global registry only added two liabilities: figures stayed
    alive until an explicit ``plt.close()`` (the GUI held one per visited stage, and
    tripped matplotlib's 20-figure ``max_open_warning``), and closing them from
    inside a Qt signal handler deadlocked under the offscreen platform plugin.
    An unregistered figure is reclaimed by ordinary garbage collection when its last
    reference drops, so nothing has to be closed at all.

    The rendering behaviour is unchanged: matplotlib reads ``rcParams`` at figure and
    axes construction, so the :func:`plot_theme` dark chrome still applies (CU-139),
    and ``fig.savefig(...)`` works on a canvas-less figure.
    """
    _require_matplotlib()
    from matplotlib.figure import Figure

    fig = Figure(layout="constrained")
    return fig, fig.subplots(*args, **kwargs)


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


# Metric display names for sweep axes/titles: the metric keys are lowercase
# identifiers; the plots write the metric the way an analyst does. Unknown keys
# fall through unchanged. Presentation-only.
_METRIC_DISPLAY: Final[dict[str, str]] = {
    "snr": "SNR",
    "contrast_snr": "Contrast SNR",
    "nedt": "NEDT",
    "nedt_K": "NEDT (K)",
    "niirs": "NIIRS",
    "gsd": "GSD",
}


def _param_display(dotpath: str) -> str:
    """Human axis label for a swept parameter, with its **schema** unit.

    Resolves the :class:`~radiant.core.parameters.ParameterDef` through the
    API's own registry so the printed unit is the canonical unit the schema
    declares — never parsed out of the name (a wrong guessed unit would violate
    the units-on-everything rule). The name's trailing unit suffix is dropped
    only when it matches that schema unit (``aperture_diameter_m`` + unit
    ``m`` → "aperture diameter (m)"). Any resolution failure falls back to the
    raw dot-path, which is always truthful.
    """
    try:
        from radiant.api._param_registry import build_parameter_set

        pdef = build_parameter_set().parameter_defs()[dotpath]
        unit = str(pdef.canonical_unit)
    except Exception:  # noqa: BLE001 - presentation fallback, raw name is always valid
        return dotpath
    leaf = dotpath.rsplit(".", 1)[-1]
    suffix = "_" + unit.lower().replace("µ", "u")
    if leaf.lower().endswith(suffix):
        leaf = leaf[: -len(suffix)]
    label = leaf.replace("_", " ")
    if unit and unit not in ("", "dimensionless", "none"):
        return f"{label} ({unit})"
    return label


def _sweep_saturation_span(result: SweepResult) -> tuple[float, float] | None:
    """The swept-value span whose points ran with a clipped full well, if any.

    Reads ``well_status().status`` from the retained per-point results
    (``keep_results=True``); returns ``None`` when results were not kept, no
    point clipped, or any point predates the readout stage. Contiguity is not
    assumed — the span reported is [first clipped value, last clipped value].
    """
    if not result.results:
        return None
    try:
        clipped = [
            float(v)
            for v, r in zip(result.values, result.results, strict=True)
            if r.well_status().status == "clipped"
        ]
    except KeyError:
        return None
    if not clipped:
        return None
    return min(clipped), max(clipped)


@_styled
def plot_sweep(result: SweepResult, **kwargs: Any) -> Figure:
    """Plot a 1-D sweep result.

    The x-axis carries the swept parameter's schema unit (see
    :func:`_param_display`); the metric renders under its analyst-facing name.
    When the sweep retained per-point results and any point saturated the full
    well, that value span is shaded in the warn tint and labelled — a flat-top
    metric curve then reads as clipping, not physics (Gap 65's warning, made
    visible in the figure itself; owner-approved 2026-08-03).

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
    tokens = plot_style.tokens()
    metric = _METRIC_DISPLAY.get(result.metric_name, result.metric_name)
    fig, ax = _subplots()
    sat = _sweep_saturation_span(result)
    if sat is not None:
        ax.axvspan(sat[0], sat[1], color=tokens["warn_soft"], zorder=0)
        y0, y1 = float(np.min(result.metric_values)), float(np.max(result.metric_values))
        ax.annotate(
            "full well saturated —\nmetric clipped",
            ((sat[0] + sat[1]) / 2.0, y0 + 0.12 * (y1 - y0)),
            fontsize=8.5,
            color=tokens["warn"],
            ha="center",
            fontweight="semibold",
        )
    ax.plot(result.values, result.metric_values, "o-", **kwargs)
    ax.set_xlabel(_param_display(result.param_name))
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs. {_param_display(result.param_name)}")
    return cast("Figure", fig)


@_styled
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
    metric = _METRIC_DISPLAY.get(result.metric_name, result.metric_name)
    fig, ax = _subplots()
    v1_grid, v2_grid = np.meshgrid(result.values1, result.values2, indexing="ij")
    cs = ax.contourf(v1_grid, v2_grid, result.grid, **kwargs)
    fig.colorbar(cs, ax=ax, label=metric)
    ax.set_xlabel(_param_display(result.param1_name))
    ax.set_ylabel(_param_display(result.param2_name))
    ax.set_title(metric)
    return cast("Figure", fig)


# Analyst-facing display names for the chain's noise terms. Unknown names fall
# through as ``name.replace("_", " ")`` so a new term is never mislabelled,
# just un-prettified. Presentation-only.
_NOISE_TERM_DISPLAY: Final[dict[str, str]] = {
    "signal_shot": "Signal shot",
    "background_shot": "Background shot",
    "dark_shot": "Dark shot",
    "glow_shot": "Glow shot",
    "straylight_shot": "Straylight shot",
    "nearfield_shot": "Near-field shot",
    "read_noise": "Read noise",
    "quantization": "Quantization",
    "persistence_noise": "Persistence",
    "clutter": "Clutter",
    "dsnu": "DSNU",
    "prnu": "PRNU",
    "ktc_reset": "kTC reset",
    "flicker_1f": "1/f flicker",
    "johnson_noise": "Johnson",
    "gr_noise": "G-R",
}

# Smallest σ a log-scale noise bar renders as a bar. Terms at or below the floor
# cannot occupy meaningful log-axis length (and zero terms none at all), so they
# move to the caption, which names every one of them — no information is lost,
# it just moves where it fits (the same trade the pie's legend made, CU-241).
# Presentation-only: it changes no computed value.
_NOISE_BAR_FLOOR_E: Final[float] = 0.05


def _noise_display(name: str) -> str:
    """Analyst-facing label for a noise-term name."""
    return _NOISE_TERM_DISPLAY.get(name, name.replace("_", " "))


@_styled
def plot_noise_budget(
    noise_terms: tuple[Any, ...] | list[Any],
    scale: str = "log",
    **kwargs: Any,
) -> Figure:
    """Plot a noise budget as a horizontal bar chart, log x-axis by default.

    The chain's noise terms span decades (a shot-dominated budget runs from
    ~10³ e⁻ down to sub-e⁻ terms), so a linear axis renders every term but the
    top two or three as invisible slivers — the exact per-term readability the
    budget exists to provide. The default is therefore **logarithmic** with a
    mono value label on every bar (units on everything); ``scale="linear"``
    restores the proportional view (owner ruling 2026-08-03: switchable, log
    default). The dominant term wears the accent; all others share one neutral
    so magnitude, not hue, carries the comparison. On the log axis, terms at or
    below :data:`_NOISE_BAR_FLOOR_E` move to the caption (each named); the
    caption also carries the RSS total.

    Parameters
    ----------
    noise_terms:
        Tuple of :class:`NoiseTerm` objects.
    scale:
        ``"log"`` (default) or ``"linear"``.
    **kwargs:
        Passed to ``ax.barh()``.

    Returns
    -------
    Figure
        A matplotlib Figure.

    Raises
    ------
    ApiValidationError
        When *scale* is not ``"log"`` or ``"linear"``.
    """
    from radiant.api.errors import ApiValidationError

    if scale not in ("log", "linear"):
        raise ApiValidationError(
            f"plot_noise_budget: scale must be 'log' or 'linear', got {scale!r}."
        )
    tokens = plot_style.tokens()
    mono = plot_style.mono_family()
    pairs = sorted(
        ((str(nt.name), float(nt.value_e)) for nt in noise_terms),
        key=lambda nv: nv[1],
        reverse=True,
    )
    total_rss = float(np.sqrt(sum(v * v for _, v in pairs)))
    if scale == "log":
        shown = [(n, v) for n, v in pairs if v > _NOISE_BAR_FLOOR_E]
        hidden = [n for n, v in pairs if v <= _NOISE_BAR_FLOOR_E]
        if not shown:  # every term at/below the floor — the floor is meaningless here
            shown, hidden = pairs, []
    else:
        shown, hidden = pairs, []

    fig, ax = _subplots()
    labels = [_noise_display(n) for n, _ in shown]
    values = [v for _, v in shown]
    colors = [tokens["accent"] if i == 0 else plot_style.OTHER_LIGHT for i in range(len(values))]
    if plot_style.active_dark():
        colors = [tokens["accent"] if i == 0 else plot_style.OTHER_DARK for i in range(len(values))]
    kwargs.setdefault("color", colors)
    kwargs.setdefault("height", 0.62)
    bars = ax.barh(labels, values, **kwargs)
    if scale == "log" and values:
        ax.set_xscale("log")
        ax.set_xlim(_NOISE_BAR_FLOOR_E, max(values) * 4.0)
    ax.grid(axis="x", color=tokens["line"], linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for bar, v in zip(bars, values, strict=True):
        ax.annotate(
            f"{v:,.0f} e⁻" if v >= 10 else f"{v:.3g} e⁻",
            (v, bar.get_y() + bar.get_height() / 2.0),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            fontfamily=mono,
            color=tokens["ink"],
        )
    ax.set_xlabel("Noise (e⁻ RMS)")
    ax.set_title("Noise budget — per-term σ" + (" (log scale)" if scale == "log" else ""))
    ax.invert_yaxis()
    for tick in ax.get_xticklabels():
        tick.set_fontfamily(mono)
    caption = f"Total (RSS) {total_rss:,.0f} e⁻ RMS"
    if hidden:
        caption += "  ·  ≤ 0.05 e⁻ RMS (not drawn): " + ", ".join(_noise_display(n) for n in hidden)
    fig.get_layout_engine().set(rect=(0.0, 0.09, 1.0, 0.91))
    fig.text(
        0.01,
        0.012,
        "\n".join(textwrap.wrap(caption, 96)),
        fontsize=8.5,
        color=tokens["muted"],
    )
    return cast("Figure", fig)


@_styled
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

    .. deprecated:: 2026-08-03
        The pie is retired (owner ruling): noise terms span decades, and a
        share-of-variance chart collapses everything but the dominant term
        into invisible slivers — the common case is one wedge at ~100 %. Use
        :func:`plot_noise_budget` (log scale, the default) instead, which
        renders every term legibly with its σ in e⁻ RMS. This function warns
        and will be removed after a deprecation period.

    Raises
    ------
    ApiValidationError
        When every term's σ is zero (the variance shares are undefined — there
        is no noise power to apportion).
    """
    from radiant.api.errors import ApiValidationError

    warnings.warn(
        "plot_noise_pie is deprecated (owner ruling 2026-08-03): use "
        "plot_noise_budget instead — its default log scale shows every term's "
        "σ legibly, which the variance pie cannot.",
        DeprecationWarning,
        stacklevel=2,
    )

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
    fig, ax = _subplots()
    # On-wedge labels are drawn **inside** the pie (CU-241, second instance). Outside the
    # wedge (matplotlib's default ``labeldistance=1.1``) a label is centred just past the
    # rim and then extends ~65 px to each side, so on a 463 px-wide card the left and
    # right labels ran off both canvas edges — measured 6 px past the left edge and 9 px
    # past the right — and no amount of layout negotiation helps, because pie labels are
    # plain axes text that constrained layout does not see. Moving them inside costs the
    # pie nothing (the alternative was shrinking the pie until the labels fitted around
    # it) and a translucent box behind each label keeps it legible over any wedge colour
    # in either theme, since both the box and the text take their colour from the active
    # rcParams rather than a literal.
    plt = _require_matplotlib()
    label_box = {
        "facecolor": plt.rcParams["axes.facecolor"],
        "edgecolor": "none",
        "alpha": 0.8,
        "boxstyle": "round,pad=0.2",
    }
    wedges, _ = ax.pie(
        variances,
        labels=wedge_labels,
        labeldistance=_PIE_LABEL_DISTANCE,
        textprops={"fontsize": "small", "ha": "center", "bbox": label_box},
        **kwargs,
    )  # slices ∝ σ_i² (noise power)
    ax.set_aspect("equal")
    # One legend row per term, dominant first — the tiny terms are readable here
    # even when they are invisible on the wedge. Newlines suit the wedge labels,
    # not a legend row, so the same fields are joined inline.
    #
    # The legend sits **below** the pie, not to its right (CU-241, second instance). A
    # right-hand legend competes with the pie for the card's width: the axes is
    # aspect-locked, so every character of legend text shrinks the pie, and the
    # on-wedge labels — which extend past the wedge radius on both sides — were the
    # first thing to run off the card edge ("…gnal_shot / S (62.0%)"). Below the pie
    # the legend consumes height, which the card has to spare and which constrained
    # layout can redistribute, and each entry gets the full card width instead of a
    # ~15-character column.
    ax.legend(
        wedges,
        [label.replace("\n", " — ") for label in labels],
        title="σ per term (e- RMS) · share of σ²",
        loc="upper center",
        bbox_to_anchor=(0.5, 0.0),
        fontsize="small",
        frameon=False,
    )
    ax.set_title(_wrapped_title("Noise budget — share of variance (σ²; noise power)"))
    return cast("Figure", fig)


@_styled
def plot_mtf_budget(budget: Any, **kwargs: Any) -> Figure:
    """Plot per-contributor MTF at Nyquist as a grouped bar chart (Gap 19).

    Parameters
    ----------
    budget:
        :class:`~radiant.performance.mtf_budget.MTFBudgetResult`.
    **kwargs:
        Passed to ``ax.barh()``.
    """
    fig, ax = _subplots()
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


@_styled
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
    # Gate the direct matplotlib import below behind the actionable message.
    _require_matplotlib()
    from matplotlib.colors import LogNorm

    if pixel_grid_span is not None:
        warnings.warn(
            "plot_psf(pixel_grid_span=...) is deprecated; use span_pixels=... "
            "(it now crops the plain PSF plot too, not only the pixel-grid one).",
            DeprecationWarning,
            stacklevel=2,
        )
        span_pixels = pixel_grid_span

    fig, ax = _subplots()
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
    fig.colorbar(im, ax=ax, label="PSF intensity", **_MAP_COLORBAR)
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
        ax.set_title(
            _wrapped_title(f"Effective PSF · detector pixel grid ({pitch_um:.1f} µm pitch)")
        )
        _overlay_pixel_grid(ax, psf, span_pixels)
    else:
        ax.set_title(_wrapped_title(f"Effective PSF ({pitch_um:.1f} µm pixel outlined)"))
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


@_styled
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
    fig, ax = _subplots()
    defaults: dict[str, Any] = {
        "cmap": "viridis",
        "origin": "lower",
        "vmin": 0.0,
        "vmax": max(1.0, float(np.max(amplitude)) if amplitude.size else 1.0),
    }
    defaults.update(_pupil_axes_labels(ax, extent_m))
    defaults.update(kwargs)
    im = ax.imshow(amplitude, **defaults)
    fig.colorbar(im, ax=ax, label="transmission (dimensionless)", **_MAP_COLORBAR)
    ax.set_title(_wrapped_title("Pupil amplitude (apodization)"))
    return cast("Figure", fig)


@_styled
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
    fig, ax = _subplots()
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
    fig.colorbar(im, ax=ax, label="wavefront error (waves)", **_MAP_COLORBAR)
    ax.set_title(_wrapped_title("Pupil wavefront error"))
    return cast("Figure", fig)


@_styled
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
        an explicit *spatial_freq* axis is in use) it is drawn as a dashed
        vertical line in the ink tone, annotated in-plot with its value — the
        sampling limit against which every roll-off is read (owner walkthrough
        item 12). ``None`` omits the marker rather than guessing a pitch.
    **kwargs:
        Passed to ``ax.plot()``.

    Notes
    -----
    Contributors that sit at ≈ 1.0 across the whole plotted band (min ≥ 0.995)
    are **not drawn**: at unity they carry no budget information, and six of
    them stacked on the top gridline made the overlay unreadable (they were
    the bulk of the old ten-row legend). Every collapsed term is named in a
    caption under the axes, so nothing is hidden — it moves where it fits
    (owner-approved Tier-2 redesign, 2026-08-03). If *every* term is at unity
    the plot draws them all rather than rendering empty. When four or fewer
    curves remain they are also direct-labelled at the line; the legend stays
    (it carries the anisotropic x/y distinctions, CU-117).

    Returns
    -------
    Figure
        A matplotlib Figure.
    """
    tokens = plot_style.tokens()
    mono = plot_style.mono_family()
    fig, ax = _subplots()

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

    # Analyst-facing display for an MTF term's base name: the ``mtf_`` prefix is
    # dropped (the axes already say MTF), acronyms stay upper-case, underscores
    # become spaces. Unknown shapes fall through un-prettified, never wrong.
    _ACRONYMS = {"ipc": "IPC", "tdi": "TDI"}

    def _term_display(base: str) -> str:
        stem = base.removeprefix("mtf_")
        if stem in _ACRONYMS:
            return _ACRONYMS[stem]
        return stem.replace("_", " ").capitalize() if stem else base

    # Unity collapse (see Notes): a group is "at unity" when every one of its
    # curves stays ≥ 0.995 across the plotted band.
    def _is_unity(axes: dict[str, npt.NDArray[np.float64]]) -> bool:
        return all(float(np.min(arr)) >= 0.995 for arr in axes.values())

    unity = [base for base in order if _is_unity(grouped[base])]
    active = [base for base in order if base not in unity]
    if not active:  # everything at unity — draw them all rather than an empty plot
        active, unity = order, []

    n_labels = 0
    drawn: list[tuple[str, npt.NDArray[np.float64], npt.NDArray[np.float64], Any]] = []
    for base in active:
        axes = grouped[base]
        xa, ya = axes.get("x"), axes.get("y")
        if xa is not None and ya is not None and np.allclose(xa, ya, atol=1e-9):
            # Isotropic contributor: one curve represents both axes — a single label.
            (line,) = ax.plot(_x_axis(xa), xa, label=_term_display(base), **kwargs)
            drawn.append((_term_display(base), _x_axis(xa), xa, line))
            n_labels += 1
        elif xa is not None and ya is not None:
            # Anisotropic: keep both curves and both labels (honest — nothing merged away).
            (line_x,) = ax.plot(_x_axis(xa), xa, label=f"{_term_display(base)} (x)", **kwargs)
            (line_y,) = ax.plot(_x_axis(ya), ya, label=f"{_term_display(base)} (y)", **kwargs)
            drawn.append((f"{_term_display(base)} (x)", _x_axis(xa), xa, line_x))
            drawn.append((f"{_term_display(base)} (y)", _x_axis(ya), ya, line_y))
            n_labels += 2
        else:
            # A lone axis or an unsuffixed term (e.g. "system").
            for suffix, arr in axes.items():
                label = _term_display(base) if not suffix else f"{_term_display(base)} ({suffix})"
                (line,) = ax.plot(_x_axis(arr), arr, label=label, **kwargs)
                drawn.append((label, _x_axis(arr), arr, line))
                n_labels += 1

    # Direct labels at the line when the overlay is sparse enough to place them
    # without collisions; the legend below still carries every entry.
    if len(drawn) <= 4:
        for i, (label, xs, ys, line) in enumerate(drawn):
            j = min(len(xs) - 1, int(0.28 * len(xs)) + i * max(1, int(0.09 * len(xs))))
            ax.annotate(
                label,
                (float(xs[j]), float(ys[j])),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=9.5,
                fontweight="semibold",
                color=line.get_color(),
            )

    # The detector sampling limit, marked on the axis every roll-off is read against
    # (owner walkthrough item 12). Drawn only with a real frequency axis — on the
    # index fallback the value would land at a meaningless x position.
    if nyquist_cycles_per_mrad is not None and spatial_freq is not None:
        ax.axvline(
            float(nyquist_cycles_per_mrad),
            color=tokens["ink_2"],
            linestyle=(0, (4, 3)),
            linewidth=1.0,
            label=f"Nyquist ({nyquist_cycles_per_mrad:.3g} cycles/mrad)",
        )
        ax.annotate(
            f"Nyquist\n{float(nyquist_cycles_per_mrad):.3g} cyc/mrad",
            (float(nyquist_cycles_per_mrad), 1.0),
            xytext=(6, -2),
            textcoords="offset points",
            fontsize=8.5,
            color=tokens["ink_2"],
            va="top",
            fontfamily=mono,
        )
        n_labels += 1

    ax.set_xlabel("Spatial frequency (cycles/mrad)" if spatial_freq is not None else "Index")
    ax.set_ylabel("MTF")
    ax.set_title("MTF budget — contributor terms")
    ax.set_ylim(0, 1.05)
    if unity:
        fig.get_layout_engine().set(rect=(0.0, 0.05, 1.0, 0.95))
        fig.text(
            0.01,
            0.008,
            "≈ 1.0 across band (not drawn): " + ", ".join(_term_display(u) for u in unity),
            fontsize=8.5,
            color=tokens["muted"],
        )
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


@_styled
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
    fig, ax = _subplots()
    ax.plot(wavelength_um, radiance, **kwargs)
    ax.set_xlabel("Wavelength (\u00b5m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    return cast("Figure", fig)


@_styled
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
    fig, ax = _subplots()
    for label, y in series.items():
        ax.plot(wavelength_um, y, label=label, **kwargs)
    ax.set_xlabel("Wavelength (\u00b5m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    if len(series) > 1:
        ax.legend(fontsize="small")
    return cast("Figure", fig)


@_styled
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
    fig, ax = _subplots()
    ax.plot(wavelength_um, tau_opt, **kwargs)
    ax.set_xlabel("Wavelength (µm)")
    ax.set_ylabel("τ_opt (dimensionless)")
    ax.set_title(title)
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    return cast("Figure", fig)


@_styled
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
    fig, ax = _subplots()
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


@_styled
def plot_element_coating(
    series: dict[str, tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    *,
    element_name: str,
    eval_span_um: tuple[float, float] | None = None,
    native_grid: bool = True,
    **kwargs: Any,
) -> Figure:
    """Plot one element's coating detail — each quantity in its own autoscaled panel.

    The all-element overlay (:func:`plot_coating_spectra`) shares one fixed
    [0, 1] axis across every curve, which flattens percent-level coating
    dispersion (a 0.95→0.99 mirror curve reads as a straight line) — Gap 116.
    This detail view isolates **one** element and gives each non-trivial
    quantity (R, T, ε) its **own stacked panel with an autoscaled y-axis**, so
    the coating's spectral structure is visible at its natural scale. When the
    curves come from the coating's native source grid, the panels show the
    full stored extent; the chain's evaluation band is shaded on every panel
    so the used portion stays identifiable.

    Parameters
    ----------
    series:
        Mapping ``symbol -> (wavelength_um [µm], values [dimensionless])`` for
        the quantities to draw (e.g. ``{"R": ..., "ε": ...}``). One panel per
        entry, in mapping order; must be non-empty.
    element_name:
        Element name, drawn in the figure title.
    eval_span_um:
        Optional ``(λ_min, λ_max)`` [µm] evaluation band, shaded on every
        panel for context.
    native_grid:
        Whether the curves carry their native source grid (subtitle reads
        "native source grid") or were broadcast onto the evaluation band
        ("evaluation-band grid").
    **kwargs:
        Passed to ``ax.plot()`` for every curve.

    Returns
    -------
    Figure
        A matplotlib Figure with one x-sharing panel per quantity.
    """
    from radiant.api.errors import ApiValidationError

    if not series:
        raise ApiValidationError(
            "plot_element_coating: series is empty — at least one non-zero "
            "R/T/ε curve is required to draw a coating detail panel."
        )
    colors = plot_style.series()
    fig, axes = _subplots(len(series), 1, sharex=True, squeeze=False)
    grid_note = "native source grid" if native_grid else "evaluation-band grid"
    for i, (ax, (symbol, (wavelength_um, values))) in enumerate(
        zip(axes[:, 0], series.items(), strict=True)
    ):
        ax.plot(wavelength_um, values, color=colors[i % len(colors)], **kwargs)
        ax.set_ylabel(f"{symbol} (–)")
        ax.grid(True, alpha=0.3)
        # Autoscale with padding — the point of the detail view. A flat curve
        # still gets a visible band rather than a degenerate axis.
        vmin = float(np.min(values))
        vmax = float(np.max(values))
        pad = max(0.01, 0.08 * (vmax - vmin))
        ax.set_ylim(max(0.0, vmin - pad), min(1.05, vmax + pad))
        if eval_span_um is not None:
            ax.axvspan(
                eval_span_um[0],
                eval_span_um[1],
                alpha=0.12,
                color="grey",
                label="evaluation band" if i == 0 else None,
            )
    axes[0, 0].set_title(f"Coating detail — {element_name} ({grid_note})")
    if eval_span_um is not None:
        axes[0, 0].legend(loc="best", fontsize="small", frameon=False)
    axes[-1, 0].set_xlabel("Wavelength (µm)")
    return cast("Figure", fig)


@_styled
def plot_atmosphere_spectral(
    wavelength_um: npt.NDArray[np.float64],
    tau_atm: npt.NDArray[np.float64],
    l_path: npt.NDArray[np.float64],
    *,
    title: str = "Atmospheric Transmittance and Path Radiance",
    **kwargs: Any,
) -> Figure:
    """Plot atmospheric transmittance and path radiance vs wavelength.

    Transmittance (dimensionless, [0, 1]) and path radiance (W/m\u00b2/sr/\u00b5m)
    carry different units, so each renders in its **own stacked panel** on the
    shared wavelength axis, unit-labelled (R-UNITS). The old twin-y-axis
    rendering was retired by owner ruling 2026-08-03: two unrelated scales
    overlaid on one plot invite reading the curves' crossings, which mean
    nothing. Each curve is direct-labelled in its own colour; no legend is
    needed.

    Parameters
    ----------
    wavelength_um:
        Shared 1-D wavelength grid [\u00b5m].
    tau_atm:
        Atmospheric transmittance \u03c4_atm(\u03bb) [dimensionless].
    l_path:
        Atmospheric path radiance L_path(\u03bb) [W/m\u00b2/sr/\u00b5m].
    title:
        Plot title (drawn over the top panel).
    **kwargs:
        Passed to ``ax.plot()`` for both curves.

    Returns
    -------
    Figure
        A matplotlib Figure with two stacked, x-sharing axes.
    """
    series = plot_style.series()
    fig, axes = _subplots(2, 1, sharex=True)
    ax_tau, ax_lp = axes
    ax_tau.plot(wavelength_um, tau_atm, color=series[0], **kwargs)
    ax_tau.set_ylabel("\u03c4_atm (\u2013)")
    ax_tau.set_ylim(0.0, 1.05)
    ax_tau.set_title(title)
    mid = len(wavelength_um) // 2
    ax_tau.annotate(
        "\u03c4_atm",
        (float(wavelength_um[mid]), float(tau_atm[mid])),
        xytext=(0, 8),
        textcoords="offset points",
        fontsize=9.5,
        fontweight="semibold",
        color=series[0],
        ha="center",
    )
    ax_lp.plot(wavelength_um, l_path, color=series[1], **kwargs)
    ax_lp.set_ylabel("L_path (W/m\u00b2/sr/\u00b5m)")
    ax_lp.set_xlabel("Wavelength (\u00b5m)")
    k = int(len(wavelength_um) * 0.7)
    ax_lp.annotate(
        "L_path",
        (float(wavelength_um[k]), float(l_path[k])),
        xytext=(-4, 10),
        textcoords="offset points",
        fontsize=9.5,
        fontweight="semibold",
        color=series[1],
        ha="right",
    )
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


@_styled
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

    fig, axes = _subplots(1, len(kept), squeeze=False)
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
