"""Per-stage default-visualization mapping (arch doc §4.4).

When a signal-chain stage is selected in the strip (GUI plan Phase 4), the central
canvas swaps to that stage's *default visualization*. This module is the single,
Qt-free source of that mapping: it names, for each chain namespace, **which existing
``result.plot.*`` figure** the canvas should render — one GUI action ↔ one API call
(GUI plan §4.1). No plotting logic lives here or in GUI code; the canvas simply calls
the named accessor on :class:`radiant.api.inspect.ResultPlotNamespace`.

The ``result.plot`` surface now exposes seven figures — ``mtf``, ``noise_budget``,
``psf``, ``mtf_budget`` and the three spectral-radiance accessors added for Gap 86
(``spectral_source``, ``spectral_atmosphere``, ``spectral_inband``). Every §4.4 row
now maps to a real accessor: the Source / Atmosphere / Spectral-Integration rows that
previously fell back to a "Gap 86" panel now render their spectral-radiance figures
(GUI plan Phase 4 Task B, remapping the accessors landed in ``api`` commit f678dfd).
Geometry maps to a bespoke **readout** of ``stage_outputs["geometry"]`` (the derived
angles/ranges), the arch-doc "angle summary" — there is no ``result.plot`` figure for
it and the 3D viewer is GUI plan Phases 6–7.

Being pure (no Qt, no matplotlib), the mapping is unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# View kinds a stage can resolve to.
KIND_PLOT: Final[str] = "plot"  # render result.plot.<method>()
KIND_GEOMETRY: Final[str] = "geometry"  # render the geometry stage-output readout


@dataclass(frozen=True, slots=True)
class StageView:
    """How the central canvas should visualize one selected stage.

    Attributes
    ----------
    kind:
        One of :data:`KIND_PLOT`, :data:`KIND_GEOMETRY`.
    plot_method:
        For :data:`KIND_PLOT`, the ``result.plot.*`` accessor name to call
        (``"mtf"`` / ``"noise_budget"`` / ``"spectral_source"`` / …); ``None``
        otherwise.
    """

    kind: str
    plot_method: str | None = None


# The default figure shown post-evaluate when *no* stage is selected: the MTF overlay
# (arch doc §4.4 "As shipped" note — the on-spec Performance-row figure that visibly
# responds to the D2 aperture edit). Selecting a stage overrides it.
DEFAULT_VIEW: Final[StageView] = StageView(kind=KIND_PLOT, plot_method="mtf")

# namespace -> default visualization, row-by-row from the §4.4 table. Keys are the
# real chain namespaces (matching ``RadiantSession.stage_names`` /
# ``Sensor.parameter_defs()`` — note ``spectral_integration``, not ``spectral``;
# CU-106). Every row now names a real ``result.plot`` accessor.
STAGE_VIEWS: Final[dict[str, StageView]] = {
    # Angle summary — a readout of the derived geometry stage outputs (no plot).
    "geometry": StageView(kind=KIND_GEOMETRY),
    # L_src(λ) at aperture — result.plot.spectral_source() (Gap 86, resolved).
    "source": StageView(kind=KIND_PLOT, plot_method="spectral_source"),
    # τ_atm(λ) + L_path(λ) overlay — result.plot.spectral_atmosphere() (Gap 86).
    "atmosphere": StageView(kind=KIND_PLOT, plot_method="spectral_atmosphere"),
    # §4.4 Optics row names an "MTF curve" — result.plot.mtf() carries it.
    "optics": StageView(kind=KIND_PLOT, plot_method="mtf"),
    # §4.4 Platform row: "smear/jitter MTF terms" — the MTF overlay shows every term.
    "platform": StageView(kind=KIND_PLOT, plot_method="mtf"),
    # In-band integrand (post-optics) radiance — result.plot.spectral_inband() (Gap 86).
    "spectral_integration": StageView(kind=KIND_PLOT, plot_method="spectral_inband"),
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
    "KIND_PLOT",
    "KIND_GEOMETRY",
    "StageView",
    "DEFAULT_VIEW",
    "STAGE_VIEWS",
    "view_for",
]
