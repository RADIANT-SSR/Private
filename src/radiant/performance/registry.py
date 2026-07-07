"""Metric registry — declares dependencies and determines computability.

Implements §6 of ``docs/architecture/RADIANT_Metrics.md`` and §5 of
``docs/architecture/RADIANT_Metric_Dependencies.md``.

Each metric declares:
- ``requires``: set of ChainState keys that must be present
- ``regimes``: set of RadiometricRegime values where the metric applies

``can_compute(metric, state)`` checks whether all dependencies are
satisfied. ``available_metrics(state)`` returns the set of metrics
that can be computed for the given chain state.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiant.core.chain import ChainState


@dataclass(frozen=True)
class MetricSpec:
    """Specification for a metric's requirements.

    Parameters
    ----------
    name:
        Metric identifier (e.g., "snr", "nedt", "niirs").
    requires_frames:
        Frame names that must exist in ``state.frames``.
    requires_stage_outputs:
        Tuples of ``(stage_name, key)`` that must be in ``state.stage_outputs``.
    requires_noise_terms:
        If True, at least one NoiseTerm must be present.
    requires_metrics:
        Metric names that must already be computed (dependencies on other metrics).
    regimes:
        Set of regime strings where this metric applies.
        Empty set means "all regimes".
    """

    name: str
    requires_frames: frozenset[str] = frozenset()
    requires_stage_outputs: frozenset[tuple[str, str]] = frozenset()
    requires_noise_terms: bool = False
    requires_metrics: frozenset[str] = frozenset()
    regimes: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Built-in metric specifications
# ---------------------------------------------------------------------------

METRIC_SPECS: dict[str, MetricSpec] = {}


def _register(spec: MetricSpec) -> MetricSpec:
    METRIC_SPECS[spec.name] = spec
    return spec


# §4.1 — SNR
_register(
    MetricSpec(
        name="snr",
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
    )
)

# §4.1 — Contrast SNR
_register(
    MetricSpec(
        name="contrast_snr",
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
        requires_stage_outputs=frozenset({("spectral_integration", "contrast_e")}),
    )
)

# §4.2 — NEDT
_register(
    MetricSpec(
        name="nedt",
        requires_noise_terms=True,
        requires_stage_outputs=frozenset(
            {
                ("spectral_integration", "signal_e"),
            }
        ),
        regimes=frozenset({"extended"}),
    )
)

# §4.3 — NEDL
_register(
    MetricSpec(
        name="nedl",
        requires_metrics=frozenset({"snr"}),
    )
)

# §4.4 — NEDR
_register(
    MetricSpec(
        name="nedr",
        requires_metrics=frozenset({"snr"}),
    )
)

# §4.5 — CSNR (alias for contrast_snr)
_register(
    MetricSpec(
        name="csnr",
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
        requires_stage_outputs=frozenset({("spectral_integration", "contrast_e")}),
        regimes=frozenset({"sub_pixel", "point_source"}),
    )
)

# §4.6 — NIIRS
_register(
    MetricSpec(
        name="niirs",
        requires_metrics=frozenset({"snr"}),
        requires_stage_outputs=frozenset({("optics", "effective_psf")}),
    )
)

# §4.7 — RER
_register(
    MetricSpec(
        name="rer",
        requires_stage_outputs=frozenset({("optics", "effective_psf")}),
    )
)

# §4.8 — Edge slope
_register(
    MetricSpec(
        name="edge_slope",
        requires_stage_outputs=frozenset({("optics", "effective_psf")}),
    )
)

# §4.9 — MTF at frequency
_register(
    MetricSpec(
        name="mtf_at_nyquist",
        requires_stage_outputs=frozenset({("optics", "effective_psf")}),
    )
)

# §4.10 — Ensquared Energy
_register(
    MetricSpec(
        name="ee",
        requires_stage_outputs=frozenset({("optics", "effective_psf")}),
    )
)

# §4.11 — Strehl ratio (PSF-derived, Rule 4: degraded-PSF peak over the
# diffraction-limited reference PSF)
_register(
    MetricSpec(
        name="strehl",
        requires_stage_outputs=frozenset(
            {
                ("optics", "effective_psf"),
                ("optics", "reference_psf"),
            }
        ),
    )
)

# §4.11b — Marechal Strehl diagnostic (analytic small-aberration
# approximation from WFE RMS; ignores obscuration, defocus, jitter, smear)
_register(
    MetricSpec(
        name="strehl_marechal",
        requires_stage_outputs=frozenset({("optics", "wavefront_error")}),
    )
)

# §4.12 — Detection range
_register(
    MetricSpec(
        name="detection_range",
        requires_metrics=frozenset({"snr"}),
        requires_stage_outputs=frozenset({("source", "range_m")}),
        regimes=frozenset({"point_source"}),
    )
)

# §4.13 — Saturation margin
_register(
    MetricSpec(
        name="saturation_margin",
        requires_stage_outputs=frozenset(
            {
                ("readout", "well_status"),
                ("readout", "signal_dn_pre_coadd"),
            }
        ),
    )
)

# §4.14 — Dynamic range
_register(
    MetricSpec(
        name="dynamic_range",
        requires_noise_terms=True,
    )
)


def can_compute(metric_name: str, state: ChainState) -> bool:
    """Check if a metric can be computed from the given chain state.

    Parameters
    ----------
    metric_name:
        Name of the metric (must be registered in METRIC_SPECS).
    state:
        Current chain state after running stages.

    Returns
    -------
    bool
        True if all dependencies are satisfied.

    Raises
    ------
    KeyError
        If ``metric_name`` is not in the registry.
    """
    spec = METRIC_SPECS[metric_name]

    # Check required frames
    for frame_name in spec.requires_frames:
        if frame_name not in state.frames:
            return False

    # Check required stage outputs
    for stage_name, key in spec.requires_stage_outputs:
        stage_out = state.stage_outputs.get(stage_name, {})
        if key not in stage_out:
            return False

    # Check noise terms
    if spec.requires_noise_terms and len(state.noise_terms) == 0:
        return False

    # Check required metrics (computed by prior metric functions)
    for req_metric in spec.requires_metrics:
        if req_metric not in state.metrics:
            return False

    # Regime check (if specified)
    if spec.regimes:
        optics_out = state.stage_outputs.get("optics", {})
        regime = optics_out.get("regime")
        if regime is not None:
            regime_str = regime.value if hasattr(regime, "value") else str(regime)
            if regime_str not in spec.regimes:
                return False

    return True


def available_metrics(state: ChainState) -> set[str]:
    """Return the set of metrics that can be computed from the given state."""
    return {name for name in METRIC_SPECS if can_compute(name, state)}


def missing_for(metric_name: str, state: ChainState) -> dict[str, list[str]]:
    """Return what's missing to compute a metric.

    Returns
    -------
    dict
        Keys: ``"frames"``, ``"stage_outputs"``, ``"noise_terms"``,
        ``"metrics"``. Each maps to a list of missing items.
        Empty dict if metric can be computed.
    """
    spec = METRIC_SPECS[metric_name]
    missing: dict[str, list[str]] = {}

    missing_frames = [f for f in spec.requires_frames if f not in state.frames]
    if missing_frames:
        missing["frames"] = missing_frames

    missing_so = []
    for stage_name, key in spec.requires_stage_outputs:
        if key not in state.stage_outputs.get(stage_name, {}):
            missing_so.append(f"{stage_name}.{key}")
    if missing_so:
        missing["stage_outputs"] = missing_so

    if spec.requires_noise_terms and len(state.noise_terms) == 0:
        missing["noise_terms"] = ["at least one NoiseTerm required"]

    missing_metrics = [m for m in spec.requires_metrics if m not in state.metrics]
    if missing_metrics:
        missing["metrics"] = missing_metrics

    return missing
