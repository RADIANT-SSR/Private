"""Metric registry — units, descriptions, dependencies, computability.

Implements §6 of ``docs/architecture/RADIANT_Metrics.md``.

The registry is the single source of metric metadata (Gap 71): every
key that ``PerformanceStage`` can write into ``state.metrics`` has a
:class:`MetricSpec` carrying a **non-empty human-readable unit** (the
project hard rule: every displayed value carries units), a description,
and a value kind. ``ChainResult.metric_records()`` consumes it to
render unit-labelled metric tables; GUI panels bind to the same
surface.

Reconciliation contract (CU-078): the spec catalog matches what the
performance stage actually computes — enforced by
``tests/integration/test_metric_registry_reconciliation.py``, which
fails if a chain run produces a metric key without a spec. Metrics that
are designed but not yet computed in-chain (NEΔL, NEΔρ, edge slope,
detection range — Gaps 77/78) are **not** registered; they enter the
catalog with the commit that computes them.

Each spec declares state-level dependencies (frames, stage outputs,
noise terms, prior metrics, MTF terms) consumed by
``can_compute``/``available_metrics``/``missing_for``. Several metrics
are additionally parameter-gated (e.g. GSD needs a positive altitude);
state-level computability is therefore necessary but not sufficient —
``missing_for`` reports the state-side blockers only.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiant.core.chain import ChainState
from radiant.core.exceptions import CoreValidationError

# Value kinds: how to interpret the float in state.metrics.
_KINDS = ("float", "flag", "code")


@dataclass(frozen=True)
class MetricSpec:
    """Metadata + dependency specification for one metric key.

    Parameters
    ----------
    name:
        Exact key written into ``state.metrics``.
    unit:
        Non-empty human-readable unit ("K", "m", "dB", "µrad",
        "dimensionless", "fraction", ...). Never blank (Gap 71).
    description:
        One-line meaning of the metric.
    kind:
        "float" (physical value), "flag" (0.0/1.0 boolean), or "code"
        (enumeration encoded as float; description names the levels).
    requires_frames:
        Frame names that must exist in ``state.frames``.
    requires_stage_outputs:
        ``(stage_name, key)`` tuples that must be present.
    requires_noise_terms:
        If True, at least one NoiseTerm must be present.
    requires_metrics:
        Metric keys that must already be computed.
    requires_mtf_terms:
        If True, ``state.mtf_terms`` must be non-empty and the shared
        spatial-frequency grid set.
    regimes:
        Regime strings where the metric applies. Empty = all regimes.
    """

    name: str
    unit: str
    description: str
    kind: str = "float"
    requires_frames: frozenset[str] = frozenset()
    requires_stage_outputs: frozenset[tuple[str, str]] = frozenset()
    requires_noise_terms: bool = False
    requires_metrics: frozenset[str] = frozenset()
    requires_mtf_terms: bool = False
    regimes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.unit:
            raise CoreValidationError(
                f"MetricSpec '{self.name}': unit must be a non-empty string "
                "(project hard rule — every displayed value carries units)."
            )
        if self.kind not in _KINDS:
            raise CoreValidationError(f"MetricSpec '{self.name}': kind must be one of {_KINDS}.")


# ---------------------------------------------------------------------------
# Built-in metric catalog — one entry per key PerformanceStage can write
# ---------------------------------------------------------------------------

METRIC_SPECS: dict[str, MetricSpec] = {}


def _register(spec: MetricSpec) -> MetricSpec:
    METRIC_SPECS[spec.name] = spec
    return spec


_PSF = frozenset({("optics", "effective_psf")})

# -- Radiometric ------------------------------------------------------------

_register(
    MetricSpec(
        name="snr",
        unit="dimensionless",
        description="Signal-to-noise ratio: in-band signal electrons over total noise RMS.",
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
    )
)
_register(
    MetricSpec(
        name="contrast_snr",
        unit="dimensionless",
        description="Contrast SNR: target-minus-background differential signal over total noise.",
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
        requires_stage_outputs=frozenset({("spectral_integration", "contrast_e")}),
    )
)
_register(
    MetricSpec(
        name="scnr",
        unit="dimensionless",
        description=(
            "Signal-to-clutter-plus-noise ratio: target contrast over the "
            "clutter-inclusive total noise √(σ_temporal² + σ_spatial²) — the "
            "detection figure of merit (Gap 77)."
        ),
        requires_frames=frozenset({"photoelectrons"}),
        requires_noise_terms=True,
        requires_stage_outputs=frozenset({("spectral_integration", "contrast_e")}),
    )
)
_register(
    MetricSpec(
        name="detection_range_m",
        unit="m",
        description=(
            "Point-source detection range: the range at which SNR falls to "
            "performance.detection_snr_threshold, inverse-square with constant "
            "atmospheric extinction (Gap 77). Point-source regime only."
        ),
        requires_metrics=frozenset({"snr"}),
        requires_stage_outputs=frozenset({("source", "range_m")}),
        regimes=frozenset({"point_source"}),
    )
)
_register(
    MetricSpec(
        name="nedt_K",
        unit="K",
        description="Noise-equivalent differential temperature.",
        requires_noise_terms=True,
        requires_stage_outputs=frozenset({("spectral_integration", "signal_e")}),
        regimes=frozenset({"extended"}),
    )
)
_register(
    MetricSpec(
        name="mrt_at_nyquist_K",
        unit="K",
        description="Minimum resolvable temperature at Nyquist: NEDT / MTF(f_Ny).",
        requires_metrics=frozenset({"nedt_K", "mtf_at_nyquist"}),
        regimes=frozenset({"extended"}),
    )
)

# -- Spatial (PSF path — Rule 4: all from the same EffectivePSF) ------------

_register(
    MetricSpec(
        name="fwhm_x_m",
        unit="m",
        description="PSF full width at half maximum at the focal plane, cross-track.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="fwhm_y_m",
        unit="m",
        description="PSF full width at half maximum at the focal plane, along-track.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="rer",
        unit="dimensionless",
        description="Relative edge response (GIQE input) from the degraded PSF's edge spread.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="ee_1x1",
        unit="fraction",
        description="Ensquared energy within 1×1 pixel of the degraded PSF.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="ee_3x3",
        unit="fraction",
        description="Ensquared energy within 3×3 pixels of the degraded PSF.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="mtf_at_nyquist",
        unit="dimensionless",
        description="MTF of the degraded PSF evaluated at the detector Nyquist frequency.",
        requires_stage_outputs=_PSF,
    )
)
_register(
    MetricSpec(
        name="strehl",
        unit="dimensionless",
        description=(
            "Strehl ratio: degraded-PSF peak over the diffraction-limited "
            "reference-PSF peak (same detector kernels on both)."
        ),
        requires_stage_outputs=frozenset(
            {("optics", "effective_psf"), ("optics", "reference_psf")}
        ),
    )
)
_register(
    MetricSpec(
        name="strehl_marechal",
        unit="dimensionless",
        description=(
            "Maréchal Strehl diagnostic: analytic small-aberration estimate "
            "from WFE RMS (ignores obscuration, jitter, smear)."
        ),
        requires_stage_outputs=frozenset({("optics", "wavefront_error")}),
    )
)

# -- MTF product path -------------------------------------------------------

_register(
    MetricSpec(
        name="mtf_system_at_nyquist_x",
        unit="dimensionless",
        description="System MTF product at Nyquist, cross-track.",
        requires_mtf_terms=True,
    )
)
_register(
    MetricSpec(
        name="mtf_system_at_nyquist_y",
        unit="dimensionless",
        description="System MTF product at Nyquist, along-track.",
        requires_mtf_terms=True,
    )
)
_register(
    MetricSpec(
        name="mtf_folded_at_nyquist",
        unit="dimensionless",
        description="Aliasing-folded MTF at Nyquist (folded response summed into baseband).",
        requires_mtf_terms=True,
    )
)
_register(
    MetricSpec(
        name="alias_fraction_at_nyquist",
        unit="fraction",
        description="Fraction of post-Nyquist energy folded into baseband at Nyquist.",
        requires_mtf_terms=True,
    )
)

# -- Imagery quality --------------------------------------------------------

_register(
    MetricSpec(
        name="niirs",
        unit="NIIRS level",
        description="GIQE-5 National Imagery Interpretability Rating Scale prediction.",
        requires_metrics=frozenset({"snr", "rer", "gsd_along_track_m", "gsd_cross_track_m"}),
    )
)
_register(
    MetricSpec(
        name="niirs_extrapolated",
        unit="0/1 flag",
        description="1.0 when GSD or SNR is outside the GIQE-5 calibration range.",
        kind="flag",
        requires_metrics=frozenset({"niirs"}),
    )
)

# -- Saturation / dynamic range ---------------------------------------------

_register(
    MetricSpec(
        name="well_margin_dB",
        unit="dB",
        description="Headroom from final signal electrons to full-well capacity.",
        requires_stage_outputs=frozenset({("readout", "signal_e_final")}),
    )
)
_register(
    MetricSpec(
        name="adc_margin_dB",
        unit="dB",
        description="Headroom from pre-coadd signal DN to ADC full scale.",
        requires_stage_outputs=frozenset({("readout", "signal_dn_pre_coadd")}),
    )
)
_register(
    MetricSpec(
        name="dynamic_range_dB",
        unit="dB",
        description="Full-well capacity over the temporal noise floor.",
        requires_stage_outputs=frozenset({("readout", "sigma_temporal_e")}),
    )
)

# -- Geometry / sampling ----------------------------------------------------

_register(
    MetricSpec(
        name="gsd_cross_track_m",
        unit="m",
        description="Ground sample distance, cross-track (parameter-gated: needs altitude).",
    )
)
_register(
    MetricSpec(
        name="gsd_along_track_m",
        unit="m",
        description="Ground sample distance, along-track (parameter-gated: needs altitude).",
    )
)
_register(
    MetricSpec(
        name="gsd_geometric_mean_m",
        unit="m",
        description="Geometric-mean GSD (GIQE input).",
        requires_metrics=frozenset({"gsd_cross_track_m", "gsd_along_track_m"}),
    )
)
_register(
    MetricSpec(
        name="ground_range_m",
        unit="m",
        description="Ground distance from nadir to the target point.",
    )
)
_register(
    MetricSpec(
        name="swath_width_m",
        unit="m",
        description="Cross-track swath width: GSD_cross × detector pixels cross-track.",
        requires_metrics=frozenset({"gsd_cross_track_m"}),
    )
)
_register(
    MetricSpec(
        name="access_rate_m2_s",
        unit="m²/s",
        description="Area collection rate: swath width × ground speed.",
        requires_metrics=frozenset({"swath_width_m"}),
    )
)
_register(
    MetricSpec(
        name="q_center",
        unit="dimensionless",
        description="Sampling parameter Q = λF#/pitch at the band-center wavelength.",
    )
)
_register(
    MetricSpec(
        name="q_min",
        unit="dimensionless",
        description="Sampling parameter Q at the band-minimum wavelength.",
    )
)
_register(
    MetricSpec(
        name="q_max",
        unit="dimensionless",
        description="Sampling parameter Q at the band-maximum wavelength.",
    )
)
_register(
    MetricSpec(
        name="sampling_regime_code",
        unit="code",
        description=(
            "Sampling regime from Q_center: 0 = detector-limited (Q<1), "
            "1 = near-critical (1≤Q≤2), 2 = diffraction-limited (Q>2)."
        ),
        kind="code",
        requires_metrics=frozenset({"q_center"}),
    )
)
_register(
    MetricSpec(
        name="diffraction_limit_angular_urad",
        unit="µrad",
        description="Diffraction-limited angular resolution 1.22 λ/D at band center.",
    )
)
_register(
    MetricSpec(
        name="diffraction_limit_ground_m",
        unit="m",
        description="Diffraction-limited ground resolution (angular limit × range).",
        requires_metrics=frozenset({"diffraction_limit_angular_urad"}),
    )
)
_register(
    MetricSpec(
        name="max_integration_time_s",
        unit="s",
        description=(
            "Longest per-line integration keeping along-track smear ≤ one "
            "ground sample (GSD_along / ground_velocity) — the pushbroom/TDI "
            "dwell feasibility limit (parameter-gated: needs a ground velocity)."
        ),
        requires_metrics=frozenset({"gsd_along_track_m"}),
    )
)


def metric_info(name: str) -> MetricSpec:
    """Return the :class:`MetricSpec` for *name*.

    Raises ``KeyError`` naming the known metrics when *name* is not
    registered.
    """
    try:
        return METRIC_SPECS[name]
    except KeyError:
        known = ", ".join(sorted(METRIC_SPECS))
        raise KeyError(f"Unknown metric '{name}'. Registered metrics: {known}") from None


def can_compute(metric_name: str, state: ChainState) -> bool:
    """Check if a metric's state-level dependencies are satisfied.

    Necessary but not sufficient: several metrics are additionally
    parameter-gated (see the module docstring).

    Raises
    ------
    KeyError
        If ``metric_name`` is not in the registry.
    """
    spec = metric_info(metric_name)

    for frame_name in spec.requires_frames:
        if frame_name not in state.frames:
            return False

    for stage_name, key in spec.requires_stage_outputs:
        stage_out = state.stage_outputs.get(stage_name, {})
        if key not in stage_out:
            return False

    if spec.requires_noise_terms and len(state.noise_terms) == 0:
        return False

    if spec.requires_mtf_terms and (
        len(state.mtf_terms) == 0 or state.spatial_freq_cycles_per_mrad is None
    ):
        return False

    for req_metric in spec.requires_metrics:
        if req_metric not in state.metrics:
            return False

    if spec.regimes:
        optics_out = state.stage_outputs.get("optics", {})
        regime = optics_out.get("regime")
        if regime is not None:
            regime_str = regime.value if hasattr(regime, "value") else str(regime)
            if regime_str not in spec.regimes:
                return False

    return True


def available_metrics(state: ChainState) -> set[str]:
    """Return the set of metrics whose state-level dependencies are met."""
    return {name for name in METRIC_SPECS if can_compute(name, state)}


def missing_for(metric_name: str, state: ChainState) -> dict[str, list[str]]:
    """Return the state-side blockers for a metric.

    Returns
    -------
    dict
        Keys: ``"frames"``, ``"stage_outputs"``, ``"noise_terms"``,
        ``"mtf_terms"``, ``"metrics"``. Each maps to a list of missing
        items. Empty dict if state-level dependencies are satisfied.
    """
    spec = metric_info(metric_name)
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

    if spec.requires_mtf_terms and (
        len(state.mtf_terms) == 0 or state.spatial_freq_cycles_per_mrad is None
    ):
        missing["mtf_terms"] = ["MTF terms and spatial-frequency grid required"]

    missing_metrics = [m for m in spec.requires_metrics if m not in state.metrics]
    if missing_metrics:
        missing["metrics"] = missing_metrics

    return missing
