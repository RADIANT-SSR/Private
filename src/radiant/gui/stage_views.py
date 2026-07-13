"""Per-stage default-visualization mapping (arch doc §4.4).

When a signal-chain stage is selected in the strip (GUI plan Phase 4), the central
canvas swaps to that stage's *default visualization*. This module is the single,
Qt-free source of that mapping: it names, for each chain namespace, **which existing
``result.plot.*`` figure** the canvas should render — one GUI action ↔ one API call
(GUI plan §4.1). No plotting logic lives here or in GUI code; the canvas simply calls
the named accessor on :class:`radiant.api.inspect.ResultPlotNamespace`.

The ``result.plot`` surface exposes exactly four figures — ``mtf``, ``noise_budget``,
``psf`` and ``mtf_budget``. Where the §4.4 table names a figure that surface does
**not** carry (the *spectral-domain* radiance figures for Source, Atmosphere and
Spectral Integration), the stage maps to a **gap** view rather than a faked figure
(ground rule §4.1): the canvas shows a themed "visualization not yet available"
panel keyed to :data:`SPECTRAL_FIGURE_GAP` (Gap 86 in ``docs/tracking/gaps.md``).
Geometry maps to a bespoke **readout** of ``stage_outputs["geometry"]`` (the derived
angles/ranges), the arch-doc "angle summary" — there is no ``result.plot`` figure for
it and the 3D viewer is GUI plan Phases 6–7.

Being pure (no Qt, no matplotlib), the mapping is unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# The single gaps.md entry (Gap 86) covering every stage whose §4.4 default figure is
# a spectral-radiance plot the ``result.plot`` surface does not expose. Each gap view
# carries this number plus a stage-specific description of the missing figure.
SPECTRAL_FIGURE_GAP: Final[int] = 86

# View kinds a stage can resolve to.
KIND_PLOT: Final[str] = "plot"  # render result.plot.<method>()
KIND_GEOMETRY: Final[str] = "geometry"  # render the geometry stage-output readout
KIND_GAP: Final[str] = "gap"  # render the themed "not yet available (Gap N)" panel


@dataclass(frozen=True, slots=True)
class StageView:
    """How the central canvas should visualize one selected stage.

    Attributes
    ----------
    kind:
        One of :data:`KIND_PLOT`, :data:`KIND_GEOMETRY`, :data:`KIND_GAP`.
    plot_method:
        For :data:`KIND_PLOT`, the ``result.plot.*`` accessor name to call
        (``"mtf"`` / ``"noise_budget"`` / …); ``None`` otherwise.
    gap_number:
        For :data:`KIND_GAP`, the ``docs/tracking/gaps.md`` gap number; ``None``
        otherwise.
    gap_detail:
        For :data:`KIND_GAP`, a one-line description of the figure that is missing
        (shown in the themed gap panel); ``None`` otherwise.
    """

    kind: str
    plot_method: str | None = None
    gap_number: int | None = None
    gap_detail: str | None = None


# The default figure shown post-evaluate when *no* stage is selected: the MTF overlay
# (arch doc §4.4 "As shipped" note — the on-spec Performance-row figure that visibly
# responds to the D2 aperture edit). Selecting a stage overrides it.
DEFAULT_VIEW: Final[StageView] = StageView(kind=KIND_PLOT, plot_method="mtf")

# namespace -> default visualization, row-by-row from the §4.4 table. Keys are the
# real chain namespaces (matching ``RadiantSession.stage_names`` /
# ``Sensor.parameter_defs()`` — note ``spectral_integration``, not ``spectral``;
# CU-106). Stages whose §4.4 row names *only* a spectral-radiance figure the
# ``result.plot`` surface lacks resolve to a gap view; stages whose row names a
# figure that surface *does* carry (MTF curve, noise-budget bar chart) render it.
STAGE_VIEWS: Final[dict[str, StageView]] = {
    # Angle summary — a readout of the derived geometry stage outputs (no plot).
    "geometry": StageView(kind=KIND_GEOMETRY),
    # L_src(λ): no spectral accessor on result.plot → gap.
    "source": StageView(
        kind=KIND_GAP,
        gap_number=SPECTRAL_FIGURE_GAP,
        gap_detail="Source spectral radiance L_src(λ) [W/m²/sr/µm]",
    ),
    # τ_atm(λ), L_path(λ), L_atm(λ) overlay: no spectral accessor → gap.
    "atmosphere": StageView(
        kind=KIND_GAP,
        gap_number=SPECTRAL_FIGURE_GAP,
        gap_detail="Atmosphere transmittance τ(λ) with path/emission radiance overlay",
    ),
    # §4.4 Optics row names an "MTF curve" — result.plot.mtf() carries it.
    "optics": StageView(kind=KIND_PLOT, plot_method="mtf"),
    # §4.4 Platform row: "smear/jitter MTF terms" — the MTF overlay shows every term.
    "platform": StageView(kind=KIND_PLOT, plot_method="mtf"),
    # In-band integrated radiance per frame: no accessor → gap.
    "spectral_integration": StageView(
        kind=KIND_GAP,
        gap_number=SPECTRAL_FIGURE_GAP,
        gap_detail="In-band integrated radiance per frame",
    ),
    # §4.4 Detector row names a "noise budget bar chart" — result.plot.noise_budget().
    "detector": StageView(kind=KIND_PLOT, plot_method="noise_budget"),
    # §4.4 Readout row: "noise budget table + bar chart" — the bar chart accessor.
    "readout": StageView(kind=KIND_PLOT, plot_method="noise_budget"),
    # §4.4 Performance row: "system MTF" — the MTF overlay.
    "performance": StageView(kind=KIND_PLOT, plot_method="mtf"),
}


def view_for(namespace: str | None) -> StageView:
    """The default :class:`StageView` for *namespace* (``None`` → :data:`DEFAULT_VIEW`).

    An unknown namespace also falls back to :data:`DEFAULT_VIEW` — a stage the chain
    grows without a §4.4 row still shows *something* real rather than erroring.
    """
    if namespace is None:
        return DEFAULT_VIEW
    return STAGE_VIEWS.get(namespace, DEFAULT_VIEW)


__all__ = [
    "SPECTRAL_FIGURE_GAP",
    "KIND_PLOT",
    "KIND_GEOMETRY",
    "KIND_GAP",
    "StageView",
    "DEFAULT_VIEW",
    "STAGE_VIEWS",
    "view_for",
]
